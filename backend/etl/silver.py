"""
Silver Layer — Clean, validate, normalise bronze records.

For each un-processed bronze_raw_calls row:
  1. Parse & validate fields (contact_id, agent_id, duration, conversation)
  2. Normalise transcript whitespace
  3. Count words & conversation turns
  4. Extract entities (tickets TKT-*, accounts ACC-*, error codes E-*, emails, dollar amounts)
  5. Detect refund / escalation keywords
  6. Upsert silver_agents directory
  7. Write silver_calls, silver_interactions, silver_extracted_entities
  8. Mark bronze row as processed
"""

import re
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import func as sqlfunc

from etl.warehouse_models import (
    BronzeRawCall,
    SilverCall,
    SilverAgent,
    SilverInteraction,
    SilverExtractedEntity,
)

# ── Regex patterns for entity extraction ──────────────────────────────────────
_RE_TICKET   = re.compile(r"\b(TKT-\d{4,})\b", re.I)
_RE_ACCOUNT  = re.compile(r"\b(ACC-\d{4,})\b", re.I)
_RE_ERROR    = re.compile(r"\b(E-\d{4,})\b", re.I)
_RE_EMAIL    = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b")
_RE_AMOUNT   = re.compile(r"\$[\d,]+\.?\d{0,2}")
_RE_PRIV_REF = re.compile(r"\b(PRIV-\d{4,})\b", re.I)
_RE_INC_REF  = re.compile(r"\b(INC-\d{4,})\b", re.I)
_RE_SEC_REF  = re.compile(r"\b(SEC-\d{4,})\b", re.I)
_RE_RNW_REF  = re.compile(r"\b(RNW-\d{4,})\b", re.I)

# Keywords that signal escalation or refund
_ESCALATION_KW = {"escalat", "supervisor", "manager", "priority-1", "priority 1", "formal complaint"}
_REFUND_KW     = {"refund", "credit", "reimburse", "money back", "reversal"}


def _parse_turns(transcript: str) -> list[dict]:
    """Split 'Agent: … \\nCustomer: …' into turns."""
    turns = []
    pattern = re.compile(r"(Agent|Customer):\s*", re.I)
    parts = pattern.split(transcript)

    # parts = ['', 'Agent', 'text...', 'Customer', 'text...', ...]
    i = 1
    turn_num = 0
    while i < len(parts) - 1:
        speaker = parts[i].strip().capitalize()
        text = parts[i + 1].strip()
        if text:
            turn_num += 1
            turns.append({
                "turn_number": turn_num,
                "speaker": speaker,
                "text": text,
                "word_count": len(text.split()),
            })
        i += 2
    return turns


def _extract_entities(text: str) -> list[dict]:
    """Pull structured entities from full transcript."""
    entities = []
    for m in _RE_TICKET.findall(text):
        entities.append({"entity_type": "ticket", "entity_value": m.upper()})
    for m in _RE_ACCOUNT.findall(text):
        entities.append({"entity_type": "account", "entity_value": m.upper()})
    for m in _RE_ERROR.findall(text):
        entities.append({"entity_type": "error_code", "entity_value": m.upper()})
    for m in _RE_EMAIL.findall(text):
        entities.append({"entity_type": "email", "entity_value": m.lower()})
    for m in _RE_AMOUNT.findall(text):
        entities.append({"entity_type": "amount", "entity_value": m})
    for m in _RE_PRIV_REF.findall(text):
        entities.append({"entity_type": "privacy_ref", "entity_value": m.upper()})
    for m in _RE_INC_REF.findall(text):
        entities.append({"entity_type": "incident_ref", "entity_value": m.upper()})
    for m in _RE_SEC_REF.findall(text):
        entities.append({"entity_type": "security_ref", "entity_value": m.upper()})
    for m in _RE_RNW_REF.findall(text):
        entities.append({"entity_type": "renewal_ref", "entity_value": m.upper()})
    # de-dup
    seen = set()
    unique = []
    for e in entities:
        key = (e["entity_type"], e["entity_value"])
        if key not in seen:
            seen.add(key)
            unique.append(e)
    return unique


def _has_keywords(text: str, keywords: set[str]) -> bool:
    lower = text.lower()
    return any(kw in lower for kw in keywords)


# ── Main Silver transform ────────────────────────────────────────────────────

def transform_to_silver(db: Session, *, batch_id: Optional[str] = None) -> dict:
    """
    Process unprocessed bronze rows → silver tables.
    If batch_id given, only process that batch.
    """
    query = db.query(BronzeRawCall).filter(BronzeRawCall.is_processed == False)
    if batch_id:
        query = query.filter(BronzeRawCall.batch_id == batch_id)

    bronze_rows = query.order_by(BronzeRawCall.id).all()
    if not bronze_rows:
        print("[silver] No unprocessed bronze rows.")
        return {"processed": 0}

    print(f"[silver] Processing {len(bronze_rows)} bronze rows …")
    processed = 0
    agents_seen: dict[str, str] = {}   # agent_id → agent_name

    for br in bronze_rows:
        raw = br.raw_json
        contact_id = raw.get("contact_id", f"UNKNOWN-{br.id}")
        agent_id   = raw.get("agent_id", "UNKNOWN")
        agent_name = raw.get("agent_name", "Unknown Agent")
        duration   = raw.get("duration")
        transcript = raw.get("conversation", "") or ""

        # Clean transcript
        clean_text = " ".join(transcript.split())  # normalise whitespace

        # Parse turns
        turns = _parse_turns(transcript)
        turn_count = len(turns)
        word_count = sum(t["word_count"] for t in turns) if turns else len(clean_text.split())

        # Extract entities
        entities = _extract_entities(transcript)
        ticket_ids  = [e["entity_value"] for e in entities if e["entity_type"] == "ticket"]
        account_ids = [e["entity_value"] for e in entities if e["entity_type"] == "account"]

        # Flags
        has_refund     = _has_keywords(transcript, _REFUND_KW)
        has_escalation = _has_keywords(transcript, _ESCALATION_KW)

        # ── Write SilverCall ──────────────────────────────────────────────────
        sc = SilverCall(
            bronze_id=br.id,
            batch_id=br.batch_id,
            contact_id=contact_id,
            agent_id=agent_id,
            agent_name=agent_name,
            duration_minutes=duration,
            transcript_clean=clean_text,
            word_count=word_count,
            turn_count=turn_count,
            has_ticket=bool(ticket_ids),
            ticket_ids=ticket_ids or None,
            has_account_ref=bool(account_ids),
            account_ids=account_ids or None,
            has_refund=has_refund,
            has_escalation=has_escalation,
        )
        db.add(sc)
        db.flush()  # get sc.id

        # ── Write SilverInteractions ──────────────────────────────────────────
        for t in turns:
            db.add(SilverInteraction(
                silver_call_id=sc.id,
                turn_number=t["turn_number"],
                speaker=t["speaker"],
                text=t["text"],
                word_count=t["word_count"],
            ))

        # ── Write SilverExtractedEntities ─────────────────────────────────────
        for ent in entities:
            db.add(SilverExtractedEntity(
                silver_call_id=sc.id,
                entity_type=ent["entity_type"],
                entity_value=ent["entity_value"],
            ))

        # ── Track agent ───────────────────────────────────────────────────────
        agents_seen[agent_id] = agent_name

        # ── Mark bronze as processed ──────────────────────────────────────────
        br.is_processed = True
        processed += 1

    # ── Upsert SilverAgents ───────────────────────────────────────────────────
    for aid, aname in agents_seen.items():
        existing = db.query(SilverAgent).filter(SilverAgent.agent_id == aid).first()
        if existing:
            existing.agent_name = aname
            existing.call_count = (
                db.query(sqlfunc.count(SilverCall.id))
                .filter(SilverCall.agent_id == aid)
                .scalar()
            )
            existing.last_seen = datetime.now(timezone.utc)
        else:
            cnt = db.query(sqlfunc.count(SilverCall.id)).filter(SilverCall.agent_id == aid).scalar()
            db.add(SilverAgent(agent_id=aid, agent_name=aname, call_count=cnt))

    db.commit()
    print(f"[silver] Done — {processed} calls cleaned, {len(agents_seen)} agents tracked")
    return {"processed": processed, "agents": len(agents_seen)}
