"""
Vapi AI Webhook Route — receives call events + transcripts from Vapi AI.

Flow:
  1. Customer calls the Vapi AI phone number
  2. Vapi AI agent converses with customer (multi-language)
  3. On call end, Vapi sends webhook with full transcript
  4. We store transcript in DB → trigger n8n for analysis
"""

import hashlib
import hmac
import os
import httpx
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional
import sys

from database import get_db
import models

# Make ai_pipeline importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from ai_pipeline.evaluator import evaluate_call_full, chunk_transcript, embed_chunks

router = APIRouter(prefix="/vapi", tags=["vapi"])

VAPI_SECRET = os.getenv("VAPI_WEBHOOK_SECRET", "")
N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL", "")
DEFAULT_COMPANY_ID = int(os.getenv("DEFAULT_COMPANY_ID", "1"))


# ── Helpers ───────────────────────────────────────────────────────────────────

def _verify_vapi_signature(payload: bytes, signature: str) -> bool:
    """Verify Vapi webhook signature using HMAC-SHA256."""
    if not VAPI_SECRET:
        return True  # skip verification if no secret configured
    expected = hmac.new(
        VAPI_SECRET.encode(), payload, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def _build_transcript_text(messages: list[dict]) -> str:
    """Convert Vapi message list into readable transcript text."""
    lines = []
    for msg in messages:
        role = msg.get("role", "unknown")
        content = msg.get("message", msg.get("content", ""))
        if role in ("bot", "assistant"):
            speaker = "Agent"
        elif role in ("user", "customer"):
            speaker = "Customer"
        else:
            speaker = role.capitalize()
        if content and content.strip():
            lines.append(f"{speaker}: {content.strip()}")
    return "\n".join(lines)


def _extract_duration_minutes(vapi_data: dict) -> float:
    """Extract call duration in minutes from Vapi payload."""
    # Vapi sends startedAt/endedAt as ISO strings or duration in seconds
    duration_sec = vapi_data.get("duration", 0)
    if not duration_sec:
        started = vapi_data.get("startedAt") or vapi_data.get("started_at")
        ended = vapi_data.get("endedAt") or vapi_data.get("ended_at")
        if started and ended:
            try:
                s = datetime.fromisoformat(started.replace("Z", "+00:00"))
                e = datetime.fromisoformat(ended.replace("Z", "+00:00"))
                duration_sec = (e - s).total_seconds()
            except (ValueError, TypeError):
                duration_sec = 0
    return round(duration_sec / 60, 2)


async def _trigger_n8n(payload: dict):
    """POST to n8n webhook for analysis. Returns True if successful."""
    if not N8N_WEBHOOK_URL:
        print("[vapi] N8N_WEBHOOK_URL not set — skipping n8n trigger")
        return False
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(N8N_WEBHOOK_URL, json=payload)
            print(f"[vapi] n8n triggered: {resp.status_code}")
            return resp.status_code == 200
    except Exception as e:
        print(f"[vapi] n8n trigger failed: {e}")
        return False


def _run_direct_analysis(call_id: int, transcript_text: str, db: Session):
    """Run analysis directly using Groq LLM when n8n is unavailable."""
    print(f"[vapi] Running direct LLM analysis for call #{call_id}")
    try:
        result = evaluate_call_full(transcript_text)

        # Upsert CallAnalysis
        analysis = db.query(models.CallAnalysis).filter(
            models.CallAnalysis.call_id == call_id
        ).first()
        call = db.query(models.Call).filter(models.Call.id == call_id).first()

        if not analysis:
            analysis = models.CallAnalysis(
                call_id=call_id,
                company_id=call.company_id if call else DEFAULT_COMPANY_ID,
            )
            db.add(analysis)

        analysis.sentiment = result["sentiment"]
        analysis.emotion = result["emotion"]
        analysis.summary = result["summary"]
        analysis.issue = result["issue_category"]
        analysis.resolution_status = result["resolution_status"]
        analysis.score = result["quality_score"]
        analysis.agent_professionalism = result["agent_professionalism"]
        analysis.customer_frustration = result["customer_frustration"]
        analysis.communication_score = result.get("communication_score")
        analysis.problem_solving_score = result.get("problem_solving_score")
        analysis.empathy_score = result.get("empathy_score")
        analysis.compliance_score = result.get("compliance_score")
        analysis.closing_score = result.get("closing_score")

        # Store tags
        for tag in result.get("tags", []):
            existing = db.query(models.CallTag).filter(
                models.CallTag.call_id == call_id,
                models.CallTag.tag == tag[:100],
            ).first()
            if not existing:
                db.add(models.CallTag(call_id=call_id, tag=tag[:100]))

        # Generate embeddings
        try:
            chunks = chunk_transcript(transcript_text)
            vectors = embed_chunks(chunks)
            for idx, (chunk_text, vec) in enumerate(zip(chunks, vectors)):
                db.add(models.CallEmbedding(
                    call_id=call_id,
                    company_id=call.company_id if call else DEFAULT_COMPANY_ID,
                    chunk_index=idx,
                    chunk_text=chunk_text,
                    embedding=vec,
                ))
        except Exception as emb_err:
            print(f"[vapi] Embedding generation failed: {emb_err}")

        # Mark call and session complete
        if call:
            call.status = "complete"
        session = db.query(models.LiveSession).filter(
            models.LiveSession.call_id == call_id
        ).first()
        if session:
            session.status = "complete"

        db.commit()
        print(f"[vapi] Direct analysis complete for call #{call_id}: score={result['quality_score']}, sentiment={result['sentiment']}")
        return True
    except Exception as e:
        print(f"[vapi] Direct analysis failed: {e}")
        import traceback
        traceback.print_exc()
        return False


# ── Webhook endpoint — Vapi sends events here ────────────────────────────────

@router.post("/webhook")
async def vapi_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Main Vapi AI webhook. Handles these event types:
      - end-of-call-report : full transcript + metadata after call ends
      - status-update      : call status changes (ringing, in-progress, ended)
      - transcript         : partial/streaming transcript updates
    """
    body = await request.body()
    signature = request.headers.get("x-vapi-signature", "")

    if VAPI_SECRET and not _verify_vapi_signature(body, signature):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    data = await request.json()
    message = data.get("message", data)
    event_type = message.get("type", "")

    print(f"[vapi] Received event: {event_type}")

    if event_type == "end-of-call-report":
        return await _handle_end_of_call(message, db)
    elif event_type == "status-update":
        return await _handle_status_update(message, db)
    elif event_type == "transcript":
        return _handle_live_transcript(message, db)

    # Acknowledge unknown events gracefully
    return {"status": "ok", "event": event_type}


# ── Event handlers ────────────────────────────────────────────────────────────

async def _handle_end_of_call(data: dict, db: Session):
    """
    Process the full end-of-call report from Vapi.
    Creates Call + LiveSession + LiveMessages in DB, triggers n8n.
    """
    vapi_call_id = data.get("call", {}).get("id") or data.get("callId", "")
    messages = data.get("messages", data.get("transcript", []))
    phone = data.get("call", {}).get("customer", {}).get("number", "")
    assistant_name = data.get("call", {}).get("assistant", {}).get("name", "Vapi Agent")

    # Build full transcript
    transcript_text = _build_transcript_text(messages)
    if not transcript_text:
        return {"status": "ok", "detail": "empty transcript, skipped"}

    duration_min = _extract_duration_minutes(data.get("call", data))

    # Detect language from Vapi metadata
    detected_language = (
        data.get("call", {}).get("assistant", {}).get("transcriber", {}).get("language")
        or data.get("language")
        or "en"
    )

    now = datetime.now(timezone.utc)

    # 1. Create Call record
    call = models.Call(
        company_id=DEFAULT_COMPANY_ID,
        contact_id=vapi_call_id[:100] if vapi_call_id else f"vapi-{now.strftime('%Y%m%d%H%M%S')}",
        agent_id="VAPI-AI",
        agent_name=assistant_name,
        conversation=transcript_text,
        duration=duration_min,
        source="ai_agent",
        call_type="inbound",
        phone_number=phone[:30] if phone else None,
        status="analyzing",
        uploaded_at=now,
    )
    db.add(call)
    db.flush()  # get call.id

    # 2. Create LiveSession
    session = models.LiveSession(
        company_id=DEFAULT_COMPANY_ID,
        call_id=call.id,
        agent_id="VAPI-AI",
        agent_name=assistant_name,
        contact_id=call.contact_id,
        phone_number=phone[:30] if phone else None,
        status="analyzing",
        started_at=now,
        ended_at=now,
        duration_sec=int(duration_min * 60),
    )
    db.add(session)
    db.flush()

    # 3. Create LiveMessages (one per transcript turn)
    for seq, msg in enumerate(messages, 1):
        role = msg.get("role", "unknown")
        content = msg.get("message", msg.get("content", ""))
        if not content or not content.strip():
            continue
        speaker = "agent" if role in ("bot", "assistant") else "customer" if role in ("user", "customer") else "system"
        db.add(models.LiveMessage(
            session_id=session.id,
            seq=seq,
            speaker=speaker,
            text=content.strip(),
        ))

    db.commit()
    db.refresh(call)
    db.refresh(session)

    print(f"[vapi] Stored call #{call.id} session #{session.id} — {len(messages)} messages")

    # 4. Trigger n8n for analysis (with direct fallback)
    n8n_payload = {
        "call_id": call.id,
        "company_id": DEFAULT_COMPANY_ID,
        "session_id": session.id,
        "vapi_call_id": vapi_call_id,
        "transcript": transcript_text,
        "agent_name": assistant_name,
        "phone_number": phone,
        "duration_minutes": duration_min,
        "language": detected_language,
        "message_count": len(messages),
    }
    n8n_ok = await _trigger_n8n(n8n_payload)

    # If n8n failed, run analysis directly via Groq LLM
    if not n8n_ok:
        print(f"[vapi] n8n unavailable — falling back to direct LLM analysis")
        _run_direct_analysis(call.id, transcript_text, db)

    return {
        "status": "ok",
        "call_id": call.id,
        "session_id": session.id,
        "messages_stored": len(messages),
        "n8n_triggered": n8n_ok,
        "direct_analysis": not n8n_ok,
    }


async def _handle_status_update(data: dict, db: Session):
    """Handle status changes (ringing, in-progress, ended)."""
    status = data.get("status", "")
    vapi_call_id = data.get("call", {}).get("id", "")
    print(f"[vapi] Status update: {status} for {vapi_call_id}")

    # If call started, create a live session in 'active' state
    if status == "in-progress" and vapi_call_id:
        phone = data.get("call", {}).get("customer", {}).get("number", "")
        assistant_name = data.get("call", {}).get("assistant", {}).get("name", "Vapi Agent")

        existing = db.query(models.LiveSession).filter(
            models.LiveSession.contact_id == vapi_call_id[:100]
        ).first()
        if not existing:
            session = models.LiveSession(
                company_id=DEFAULT_COMPANY_ID,
                agent_id="VAPI-AI",
                agent_name=assistant_name,
                contact_id=vapi_call_id[:100],
                phone_number=phone[:30] if phone else None,
                status="active",
            )
            db.add(session)
            db.commit()
            print(f"[vapi] Created active session for {vapi_call_id}")

    return {"status": "ok"}


def _handle_live_transcript(data: dict, db: Session):
    """Handle streaming transcript updates during the call."""
    vapi_call_id = data.get("call", {}).get("id", "")
    transcript_part = data.get("transcript", "")
    role = data.get("role", "unknown")

    if not transcript_part or not vapi_call_id:
        return {"status": "ok"}

    # Find the active session
    session = db.query(models.LiveSession).filter(
        models.LiveSession.contact_id == vapi_call_id[:100],
        models.LiveSession.status == "active",
    ).first()

    if session:
        # Get next sequence number
        max_seq = db.query(models.LiveMessage).filter(
            models.LiveMessage.session_id == session.id
        ).count()
        speaker = "agent" if role in ("bot", "assistant") else "customer" if role in ("user", "customer") else "system"
        db.add(models.LiveMessage(
            session_id=session.id,
            seq=max_seq + 1,
            speaker=speaker,
            text=transcript_part.strip(),
        ))
        db.commit()

    return {"status": "ok"}


# ── Manual trigger: re-send a call to n8n for re-analysis ────────────────────

class RetriggerRequest(BaseModel):
    call_id: int


@router.post("/retrigger-analysis")
async def retrigger_analysis(body: RetriggerRequest, db: Session = Depends(get_db)):
    """Re-send an existing call's transcript to n8n for re-analysis."""
    call = db.query(models.Call).filter(models.Call.id == body.call_id).first()
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")

    session = db.query(models.LiveSession).filter(
        models.LiveSession.call_id == call.id
    ).first()

    payload = {
        "call_id": call.id,
        "company_id": call.company_id,
        "session_id": session.id if session else None,
        "transcript": call.conversation,
        "agent_name": call.agent_name,
        "phone_number": call.phone_number,
        "duration_minutes": call.duration,
        "language": "en",
        "message_count": 0,
    }
    await _trigger_n8n(payload)

    return {"status": "ok", "call_id": call.id, "n8n_triggered": bool(N8N_WEBHOOK_URL)}
