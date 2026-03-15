"""
ReViewSense AI — FastAPI Backend
All routes required by the Vite+React frontend.
"""

import io
import json
import os
import random
import sys
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import pandas as pd
from fastapi import Body, Depends, FastAPI, File, HTTPException, Query, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import case, func, Integer
from sqlalchemy.orm import Session

# Make ai_pipeline importable from the project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from ai_pipeline.evaluator import chunk_transcript, embed_chunks, evaluate_call

from auth import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from database import Base, engine, get_db
import models
from routes.chatbot import router as chatbot_router
from routes.vapi import router as vapi_router
from routes.n8n_webhook import router as n8n_router

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(title="ReViewSense AI")

# Default company ID used by Vapi webhook (matches routes/vapi.py)
DEFAULT_COMPANY_ID = int(os.getenv("DEFAULT_COMPANY_ID", "1"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create all DB tables on startup
Base.metadata.create_all(bind=engine)

# ── Chatbot routes ────────────────────────────────────────────────────────────
app.include_router(chatbot_router)

# ── Vapi AI + n8n webhook routes ──────────────────────────────────────────────
app.include_router(vapi_router)
app.include_router(n8n_router)


# ── Filter helper — applies common filters to a Call+CallAnalysis query ────────
def _apply_filters(
    q,
    cid: int,
    agent: Optional[str] = None,
    issue: Optional[str] = None,
    sentiment: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
):
    """Apply standard dashboard filters to any query that joins Call + CallAnalysis."""
    q = q.filter(models.Call.company_id == cid)
    if agent:
        q = q.filter(models.Call.agent_id == agent)
    if issue:
        q = q.filter(models.CallAnalysis.issue == issue)
    if sentiment:
        q = q.filter(models.CallAnalysis.sentiment == sentiment)
    if date_from:
        q = q.filter(models.Call.uploaded_at >= date_from)
    if date_to:
        q = q.filter(models.Call.uploaded_at <= date_to + " 23:59:59")
    return q


def _time_ago(dt):
    """Human-readable relative time."""
    if not dt:
        return "just now"
    now = datetime.now(timezone.utc)
    # Ensure dt is timezone-aware; assume UTC if naive
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    delta = (now - dt).total_seconds()
    if delta < 60:
        return f"{int(delta)}s ago"
    if delta < 3600:
        return f"{int(delta // 60)}m ago"
    if delta < 86400:
        return f"{int(delta // 3600)}h ago"
    return f"{int(delta // 86400)}d ago"


# ── Auth routes ───────────────────────────────────────────────────────────────
class RegisterRequest(BaseModel):
    company_name: str
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


@app.post("/register")
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    if db.query(models.Company).filter(models.Company.email == body.email).first():
        raise HTTPException(status_code=400, detail="Email already registered.")
    company = models.Company(name=body.company_name, email=body.email)
    db.add(company)
    db.flush()
    user = models.User(
        company_id=company.id,
        email=body.email,
        password_hash=hash_password(body.password),
        role="company_owner",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token(user.id, company.id, user.role)
    return {"access_token": token, "company": {"id": company.id, "name": company.name}}


@app.post("/login")
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == body.email).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    company = db.query(models.Company).filter(models.Company.id == user.company_id).first()
    token = create_access_token(user.id, user.company_id, user.role)
    return {"access_token": token, "company": {"id": company.id, "name": company.name}}


# ── Filter options (dynamic dropdowns) ────────────────────────────────────────
@app.get("/filters/options")
def filter_options(
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return distinct agent IDs and issue categories for filter dropdowns."""
    cid = user.company_id
    agents = (
        db.query(models.Call.agent_id, models.Call.agent_name)
        .filter(models.Call.company_id == cid)
        .distinct()
        .all()
    )
    issues = (
        db.query(models.CallAnalysis.issue)
        .filter(models.CallAnalysis.company_id == cid)
        .distinct()
        .all()
    )
    return {
        "agents": [{"id": a.agent_id, "name": a.agent_name} for a in agents if a.agent_id],
        "issues": [i.issue for i in issues if i.issue],
    }


# ── Dashboard metrics ─────────────────────────────────────────────────────────
@app.get("/dashboard/metrics")
def dashboard_metrics(
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    agent: Optional[str] = Query(None),
    issue: Optional[str] = Query(None),
    sentiment: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
):
    cid = user.company_id

    # Base query: Call + Analysis joined
    base = db.query(models.Call).join(
        models.CallAnalysis, models.CallAnalysis.call_id == models.Call.id, isouter=True
    )
    base = _apply_filters(base, cid, agent, issue, sentiment, date_from, date_to)

    total_calls = base.count()
    if total_calls == 0:
        return {
            "empty": True,
            "cards": [
                {"title": "Total Calls", "value": "0", "trend": "—", "trendUp": True},
                {"title": "Avg Quality Score", "value": "—", "trend": "—", "trendUp": True},
                {"title": "Positive Sentiment", "value": "—", "trend": "—", "trendUp": True},
                {"title": "Open Issues", "value": "0", "trend": "—", "trendUp": False},
            ],
        }

    # Current period stats
    analyses = (
        db.query(models.CallAnalysis)
        .join(models.Call, models.Call.id == models.CallAnalysis.call_id)
    )
    analyses = _apply_filters(analyses, cid, agent, issue, sentiment, date_from, date_to)
    all_analyses = analyses.all()

    avg_score = round(sum(a.score for a in all_analyses) / len(all_analyses)) if all_analyses else 0
    positive = sum(1 for a in all_analyses if a.sentiment == "Positive")
    pos_pct = round(positive / len(all_analyses) * 100) if all_analyses else 0
    negative = sum(1 for a in all_analyses if a.sentiment == "Negative")

    # Previous period (last 7 days vs 7 days before that) for trend calc
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)
    two_weeks_ago = now - timedelta(days=14)

    curr_q = (
        db.query(models.CallAnalysis)
        .join(models.Call, models.Call.id == models.CallAnalysis.call_id)
        .filter(models.Call.company_id == cid, models.Call.uploaded_at >= week_ago)
    )
    prev_q = (
        db.query(models.CallAnalysis)
        .join(models.Call, models.Call.id == models.CallAnalysis.call_id)
        .filter(models.Call.company_id == cid, models.Call.uploaded_at >= two_weeks_ago, models.Call.uploaded_at < week_ago)
    )
    curr_all = curr_q.all()
    prev_all = prev_q.all()

    # Trends: call count
    curr_count = len(curr_all)
    prev_count = len(prev_all)
    if prev_count > 0:
        calls_pct = round((curr_count - prev_count) / prev_count * 100)
    elif curr_count > 0:
        calls_pct = 100
    else:
        calls_pct = 0

    # Trends: avg score
    curr_avg = round(sum(a.score for a in curr_all) / len(curr_all)) if curr_all else 0
    prev_avg = round(sum(a.score for a in prev_all) / len(prev_all)) if prev_all else 0
    score_diff = curr_avg - prev_avg

    # Trends: positive sentiment %
    curr_pos = round(sum(1 for a in curr_all if a.sentiment == "Positive") / len(curr_all) * 100) if curr_all else 0
    prev_pos = round(sum(1 for a in prev_all if a.sentiment == "Positive") / len(prev_all) * 100) if prev_all else 0
    pos_diff = curr_pos - prev_pos

    # Trends: negative (open issues)
    curr_neg = sum(1 for a in curr_all if a.sentiment == "Negative")
    prev_neg = sum(1 for a in prev_all if a.sentiment == "Negative")
    if prev_neg > 0:
        neg_pct = round((curr_neg - prev_neg) / prev_neg * 100)
    elif curr_neg > 0:
        neg_pct = 100
    else:
        neg_pct = 0

    def _trend_str(val, suffix="%"):
        return f"+{val}{suffix}" if val >= 0 else f"{val}{suffix}"

    return {
        "empty": False,
        "cards": [
            {"title": "Total Calls", "value": str(total_calls), "trend": _trend_str(calls_pct), "trendUp": calls_pct >= 0},
            {"title": "Avg Quality Score", "value": str(avg_score), "trend": _trend_str(score_diff, "pts"), "trendUp": score_diff >= 0},
            {"title": "Positive Sentiment", "value": f"{pos_pct}%", "trend": _trend_str(pos_diff), "trendUp": pos_diff >= 0},
            {"title": "Open Issues", "value": str(negative), "trend": _trend_str(neg_pct), "trendUp": neg_pct <= 0},
        ],
    }


# ── Upload calls ──────────────────────────────────────────────────────────────
@app.post("/upload-calls")
def upload_calls(
    file: UploadFile = File(...),
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    raw = file.file.read()
    fname = (file.filename or "").lower()

    # ── Unwrap nested JSON  ──────────────────────────────────────────────────
    WRAPPER_KEYS = ["calls", "data", "records", "results", "transcripts",
                    "items", "conversations", "rows", "entries"]

    # ── Helper: flatten nested conversation structures into plain text ────────
    def _flatten_value(val: Any) -> str:
        """
        Recursively convert nested conversation structures to plain text.
        Handles: list of message dicts, nested Transcript objects, etc.
        """
        if val is None:
            return ""
        if isinstance(val, str):
            return val.strip()
        if isinstance(val, list):
            parts = []
            for item in val:
                if isinstance(item, dict):
                    # Message-style: {"role": "Agent", "content": "Hello"}
                    role = (item.get("role") or item.get("Role") or
                            item.get("participant") or item.get("Participant") or
                            item.get("participantRole") or item.get("ParticipantRole") or
                            item.get("speaker") or item.get("Speaker") or
                            item.get("from") or item.get("sender") or "")
                    text = (item.get("content") or item.get("Content") or
                            item.get("text") or item.get("Text") or
                            item.get("message") or item.get("Message") or
                            item.get("body") or item.get("Body") or
                            item.get("transcript") or item.get("Transcript") or
                            item.get("utterance") or item.get("Utterance") or "")
                    if text:
                        parts.append(f"{role}: {text}" if role else str(text))
                    else:
                        # No known text key — try all string values
                        for v in item.values():
                            if isinstance(v, str) and len(v) > 10:
                                parts.append(v)
                elif isinstance(item, str):
                    parts.append(item)
            return "\n".join(parts)
        if isinstance(val, dict):
            # Nested structure like {"Segments": [...]} or {"transcript": "..."}
            for k in ["segments", "Segments", "turns", "Turns", "messages",
                       "Messages", "utterances", "Utterances", "content", "Content",
                       "text", "Text", "transcript", "Transcript", "body", "Body"]:
                if k in val:
                    return _flatten_value(val[k])
            # Try the longest nested value
            best = ""
            for v in val.values():
                flat = _flatten_value(v)
                if len(flat) > len(best):
                    best = flat
            return best
        return str(val).strip()

    try:
        if fname.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(raw))
        elif fname.endswith(".json"):
            data = json.loads(raw)
            if isinstance(data, dict):
                # Try to unwrap common wrapper keys (case-insensitive)
                lower_keys = {k.lower(): k for k in data.keys()}
                unwrapped = False
                for wk in WRAPPER_KEYS:
                    orig_key = lower_keys.get(wk)
                    if orig_key and isinstance(data[orig_key], list):
                        data = data[orig_key]
                        unwrapped = True
                        break
                if not unwrapped:
                    data = [data]   # single-object JSON
            df = pd.DataFrame(data)
        else:
            raise HTTPException(status_code=400, detail="Only .csv and .json files are supported.")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not parse file: {exc}")

    df.columns = [c.lower().strip().replace(" ", "_") for c in df.columns]
    print(f"[upload] Parsed {len(df)} rows. Columns: {list(df.columns)}")

    # ── Auto-detect transcript field ─────────────────────────────────────────
    TRANSCRIPT_KEYS = [
        "conversation", "transcript", "text", "body", "content",
        "dialog", "dialogue", "message", "messages", "call_text", "chat",
        "call_transcript", "call_content", "segments", "turns",
        "utterances", "call_body", "notes", "call_notes",
        "interaction", "call_conversation", "recording_transcript",
    ]

    def extract_transcript(row: Any) -> str:
        # 1. Try known field names — flatten nested values
        for key in TRANSCRIPT_KEYS:
            raw_val = row.get(key, None)
            if raw_val is None:
                continue
            # Handle pandas NaN
            try:
                if pd.isna(raw_val):
                    continue
            except (TypeError, ValueError):
                pass  # not a scalar NaN — it's a dict/list, which is fine
            flat = _flatten_value(raw_val)
            if flat and len(flat) > 5:
                print(f"[upload] Transcript found in field '{key}' ({len(flat)} chars)")
                return flat

        # 2. Fall back: check ALL columns, flatten any nested value > 50 chars
        candidates = []
        for k, v in row.items():
            if k in ("id", "contact_id", "contactid", "agent_id", "agentid",
                      "duration", "timestamp", "date", "created_at"):
                continue  # skip metadata fields
            flat = _flatten_value(v)
            if len(flat) > 50:
                candidates.append((k, flat))

        if candidates:
            best_key, best_val = max(candidates, key=lambda x: len(x[1]))
            print(f"[upload] Transcript fallback: using field '{best_key}' ({len(best_val)} chars)")
            return best_val

        # 3. Last resort: concatenate ALL string-like values
        all_text = []
        for k, v in row.items():
            flat = _flatten_value(v)
            if flat and len(flat) > 10:
                all_text.append(flat)
        if all_text:
            combined = "\n".join(all_text)
            print(f"[upload] Transcript last-resort: combined all fields ({len(combined)} chars)")
            return combined

        print(f"[upload] WARNING: No transcript found. Columns: {list(row.index)}")
        return ""

    results = []
    notifications = []

    for _, row in df.iterrows():
        conversation = extract_transcript(row)
        contact_id   = str(row.get("contact_id", row.get("contactid", f"C{random.randint(1000,9999)}")))
        agent_id     = str(row.get("agent_id",   row.get("agentid",   "unknown")))
        agent_name   = str(row.get("agent_name", row.get("agentname", "Unknown Agent")))
        duration     = float(row.get("duration", random.uniform(3, 25)))

        # ── Duplicate Check ───────────────────────────────────────────────────
        existing_call = db.query(models.Call).filter(
            models.Call.company_id == user.company_id,
            models.Call.contact_id == contact_id
        ).first()

        if existing_call:
            print(f"[upload] Skipping duplicate call {contact_id}")
            results.append({
                "contactId": contact_id,
                "status": "skipped",
                "message": "This call recording is a repeat so not added in database"
            })
            continue

        # ── LLM Evaluation via Groq ───────────────────────────────────────────
        llm = evaluate_call(conversation) if conversation.strip() else {}
        sentiment   = llm.get("sentiment", "Neutral")
        issue       = llm.get("issue_category", "Other")
        score       = llm.get("quality_score", 50)

        # ── Save call ────────────────────────────────────────────────────────
        call = models.Call(
            company_id=user.company_id,
            contact_id=contact_id,
            agent_id=agent_id,
            agent_name=agent_name,
            conversation=conversation,
            duration=duration,
        )
        db.add(call)
        db.flush()

        # ── Save analysis with all 8 LLM fields ──────────────────────────────
        analysis = models.CallAnalysis(
            call_id=call.id,
            company_id=user.company_id,
            sentiment=sentiment,
            issue=issue,
            score=score,
            summary=llm.get("summary", ""),
            emotion=llm.get("emotion"),
            resolution_status=llm.get("resolution_status"),
            agent_professionalism=llm.get("agent_professionalism"),
            customer_frustration=llm.get("customer_frustration"),
        )
        db.add(analysis)

        # ── RAG: chunk + embed + store ────────────────────────────────────────
        if conversation.strip():
            chunks     = chunk_transcript(conversation)
            embeddings = embed_chunks(chunks)
            for idx, (chunk_text, emb) in enumerate(zip(chunks, embeddings)):
                db.add(models.CallEmbedding(
                    call_id=call.id,
                    company_id=user.company_id,
                    chunk_index=idx,
                    chunk_text=chunk_text,
                    embedding=emb,
                ))

        results.append({
            "contactId": contact_id, 
            "status": "success",
            "sentiment": sentiment, 
            "quality_score": score
        })

        # ── Check for recurring issue risk ────────────────────────────────────
        if issue and issue.lower() not in ("other", "none", "unknown"):
            issue_count = db.query(models.CallAnalysis).filter(
                models.CallAnalysis.company_id == user.company_id,
                models.CallAnalysis.issue == issue
            ).count()

            # Include the current issue in count if it's new (already added to session)
            if issue_count >= 3:
                msg = f"Issue '{issue}' has occurred {issue_count} times. This is a risk for future."
                if msg not in notifications:
                    notifications.append(msg)

    db.commit()
    return {
        "total": len(results), 
        "calls": results,
        "notifications": notifications
    }


# ── Analyze single transcript ─────────────────────────────────────────────────
class TranscriptRequest(BaseModel):
    text: str


@app.post("/analyze-transcript")
def analyze_transcript(
    body: TranscriptRequest,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    text = body.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Transcript text is required.")

    # ── LLM Evaluation via Groq ───────────────────────────────────────────────
    llm       = evaluate_call(text)
    sentiment = llm["sentiment"]
    issue     = llm["issue_category"]
    score     = llm["quality_score"]

    # ── Save call ─────────────────────────────────────────────────────────────
    call = models.Call(
        company_id=user.company_id,
        contact_id="manual-paste",
        agent_id="manual",
        agent_name="Manual Entry",
        conversation=text,
        duration=round(len(text) / 800, 1),
    )
    db.add(call)
    db.flush()

    # ── Save analysis with all 8 LLM fields ──────────────────────────────────
    analysis = models.CallAnalysis(
        call_id=call.id,
        company_id=user.company_id,
        sentiment=sentiment,
        issue=issue,
        score=score,
        summary=llm["summary"],
        emotion=llm["emotion"],
        resolution_status=llm["resolution_status"],
        agent_professionalism=llm["agent_professionalism"],
        customer_frustration=llm["customer_frustration"],
    )
    db.add(analysis)

    # ── RAG: chunk + embed + store ────────────────────────────────────────────
    chunks     = chunk_transcript(text)
    embeddings = embed_chunks(chunks)
    for idx, (chunk_text, emb) in enumerate(zip(chunks, embeddings)):
        db.add(models.CallEmbedding(
            call_id=call.id,
            company_id=user.company_id,
            chunk_index=idx,
            chunk_text=chunk_text,
            embedding=emb,
        ))

    db.commit()

    return {
        "quality_score": score,
        "sentiment":     sentiment,
        "insights": {
            "summary":              llm["summary"],
            "emotion":              llm["emotion"],
            "resolution_status":    llm["resolution_status"],
            "agent_professionalism":llm["agent_professionalism"],
            "customer_frustration": llm["customer_frustration"],
        },
    }


# ── Last call insight (CallInsights page) ─────────────────────────────────────
@app.get("/calls/last-insight")
def last_call_insight(
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Find the latest call that has analysis completed
    latest = (
        db.query(models.Call)
        .join(models.CallAnalysis, models.CallAnalysis.call_id == models.Call.id)
        .filter(models.Call.company_id == user.company_id)
        .order_by(models.Call.uploaded_at.desc())
        .first()
    )

    if not latest:
        return {"empty": True}

    analysis = latest.analysis
    if not analysis:
        return {"empty": True}

    sentiment = analysis.sentiment or "Neutral"
    score     = analysis.score or 0
    issue     = analysis.issue or "General Inquiry"
    summary   = analysis.summary or "No summary available."
    emotion   = analysis.emotion or "Neutral"
    resolution = analysis.resolution_status or ("Resolved" if sentiment == "Positive" else "Pending")

    # ── Transcript: prefer LiveMessages, fall back to conversation text ──────
    transcript = []
    session = (
        db.query(models.LiveSession)
        .filter(models.LiveSession.call_id == latest.id)
        .first()
    )
    if session:
        msgs = (
            db.query(models.LiveMessage)
            .filter(models.LiveMessage.session_id == session.id)
            .order_by(models.LiveMessage.seq)
            .all()
        )
        for m in msgs:
            highlight = None
            ll = m.text.lower()
            if any(w in ll for w in ("complaint", "angry", "terrible", "frustrated", "frustrat")):
                highlight = "complaint"
            elif any(w in ll for w in ("thank", "appreciate", "great", "wonderful")):
                highlight = "empathy"
            elif any(w in ll for w in ("resolv", "fixed", "sorted", "reset", "logged in")):
                highlight = "resolution"
            transcript.append({
                "speaker": "Agent" if m.speaker == "agent" else "Customer",
                "text": m.text,
                "highlight": highlight,
            })
    elif latest.conversation:
        raw_lines = latest.conversation.split("\n")
        for i, line in enumerate(raw_lines[:20]):
            line = line.strip()
            if not line:
                continue
            speaker = "Agent" if i % 2 == 0 else "Customer"
            highlight = None
            ll = line.lower()
            if any(w in ll for w in ("complaint", "angry", "terrible", "frustrated")):
                highlight = "complaint"
            elif any(w in ll for w in ("thank", "appreciate", "great")):
                highlight = "empathy"
            elif any(w in ll for w in ("resolv", "fixed", "sorted")):
                highlight = "resolution"
            transcript.append({"speaker": speaker, "text": line, "highlight": highlight})

    if not transcript:
        return {"empty": True}

    # ── Score breakdown: use real sub-scores if available ─────────────────────
    comm  = analysis.communication_score
    prob  = analysis.problem_solving_score
    emp   = analysis.empathy_score
    comp  = analysis.compliance_score
    close = analysis.closing_score

    if comm is not None:
        score_breakdown = [
            {"label": "Communication",   "score": comm,  "max": 30},
            {"label": "Problem Solving", "score": prob or 0,  "max": 25},
            {"label": "Empathy",         "score": emp or 0,   "max": 20},
            {"label": "Compliance",      "score": comp or 0,  "max": 15},
            {"label": "Closing",         "score": close or 0, "max": 10},
        ]
    else:
        # Fallback estimate from overall score
        score_breakdown = [
            {"label": "Communication",   "score": min(round(score * 0.30), 30), "max": 30},
            {"label": "Problem Solving", "score": min(round(score * 0.25), 25), "max": 25},
            {"label": "Empathy",         "score": min(round(score * 0.20), 20), "max": 20},
            {"label": "Compliance",      "score": min(round(score * 0.15), 15), "max": 15},
            {"label": "Closing",         "score": min(round(score * 0.10), 10), "max": 10},
        ]

    # ── Tags from DB ─────────────────────────────────────────────────────────
    tags = [t.tag for t in (latest.tags or [])]

    # ── Coaching: dynamic based on actual scores ─────────────────────────────
    strengths = []
    improvements = []

    if comm is not None and comm >= 25:
        strengths.append("Excellent communication skills — clear and professional throughout.")
    elif comm is not None and comm < 20:
        improvements.append("Communication could be clearer — consider structured responses.")

    if prob is not None and prob >= 20:
        strengths.append("Strong problem-solving — issue identified and addressed efficiently.")
    elif prob is not None and prob < 15:
        improvements.append("Problem resolution was slow — use knowledge base for faster answers.")

    if emp is not None and emp >= 16:
        strengths.append("Showed genuine empathy and understanding of customer frustration.")
    elif emp is not None and emp < 12:
        improvements.append("Could show more empathy — acknowledge customer feelings explicitly.")

    if comp is not None and comp >= 12:
        strengths.append("Followed compliance and procedural guidelines well.")
    elif comp is not None and comp < 10:
        improvements.append("Review compliance checklist — some steps may have been missed.")

    if close is not None and close >= 8:
        strengths.append("Professional closing with clear next steps for the customer.")
    elif close is not None and close < 6:
        improvements.append("Improve call closing — confirm resolution and offer follow-up.")

    if resolution == "Resolved":
        strengths.append("Successfully resolved the customer's issue.")
    else:
        improvements.append("Issue was not fully resolved — consider escalation procedures.")

    if not strengths:
        strengths.append("Agent handled the call adequately.")
    if not improvements:
        improvements.append("Continue maintaining current quality standards.")

    # ── Confidence: derive from data completeness ────────────────────────────
    has_sub_scores = comm is not None
    has_emotion    = analysis.emotion is not None
    has_summary    = analysis.summary is not None and len(analysis.summary) > 20

    confidence = [
        {"label": "Sentiment Detection",  "confidence": 95 if has_emotion else 75},
        {"label": "Issue Classification",  "confidence": 90 if issue != "General Inquiry" else 65},
        {"label": "Quality Score",         "confidence": 95 if has_sub_scores else 70},
        {"label": "Coaching Relevance",    "confidence": 88 if has_sub_scores else 60},
    ]

    return {
        "quality_score": score,
        "transcript": transcript,
        "insights": {
            "Primary Issue":     issue,
            "Sentiment":         sentiment,
            "Emotion":           emotion,
            "Summary":           summary,
            "Resolution Status": resolution,
        },
        "score_breakdown": score_breakdown,
        "coaching": {
            "strengths": strengths,
            "improvements": improvements,
        },
        "confidence": confidence,
        "tags": tags,
    }


# ── Charts ────────────────────────────────────────────────────────────────────
@app.get("/charts/top-issues")
def chart_top_issues(
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    agent: Optional[str] = Query(None),
    sentiment: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
):
    q = (
        db.query(models.CallAnalysis.issue, func.count(models.CallAnalysis.id).label("count"))
        .join(models.Call, models.Call.id == models.CallAnalysis.call_id)
    )
    q = _apply_filters(q, user.company_id, agent, None, sentiment, date_from, date_to)
    rows = q.group_by(models.CallAnalysis.issue).order_by(func.count(models.CallAnalysis.id).desc()).limit(7).all()
    if not rows:
        return {"data": []}
    return {"data": [{"issue": r.issue, "count": r.count} for r in rows]}


@app.get("/charts/sentiment")
def chart_sentiment(
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    agent: Optional[str] = Query(None),
    issue: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
):
    q = (
        db.query(models.CallAnalysis.sentiment, func.count(models.CallAnalysis.id).label("count"))
        .join(models.Call, models.Call.id == models.CallAnalysis.call_id)
    )
    q = _apply_filters(q, user.company_id, agent, issue, None, date_from, date_to)
    rows = q.group_by(models.CallAnalysis.sentiment).all()
    color_map = {
        "Positive": "hsl(142,71%,45%)",
        "Neutral":  "hsl(38,92%,50%)",
        "Negative": "hsl(0,84%,60%)",
    }
    if not rows:
        return {"data": []}
    return {"data": [
        {"name": r.sentiment, "value": r.count, "color": color_map.get(r.sentiment, "#888")}
        for r in rows
    ]}


@app.get("/charts/quality-trend")
def chart_quality_trend(
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    agent: Optional[str] = Query(None),
    issue: Optional[str] = Query(None),
    sentiment: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
):
    week_expr = func.to_char(models.CallAnalysis.created_at, 'IYYY-"W"IW')
    q = (
        db.query(
            week_expr.label("week"),
            func.avg(models.CallAnalysis.score).label("score"),
        )
        .join(models.Call, models.Call.id == models.CallAnalysis.call_id)
    )
    q = _apply_filters(q, user.company_id, agent, issue, sentiment, date_from, date_to)
    rows = (
        q.group_by(week_expr)
        .order_by(week_expr)
        .limit(8)
        .all()
    )
    if not rows:
        return {"data": []}
    return {"data": [{"week": r.week, "score": round(r.score, 1)} for r in rows]}


@app.get("/charts/agent-score-dist")
def chart_agent_score_dist(
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    agent: Optional[str] = Query(None),
    issue: Optional[str] = Query(None),
    sentiment: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
):
    q = (
        db.query(models.CallAnalysis.score)
        .join(models.Call, models.Call.id == models.CallAnalysis.call_id)
    )
    q = _apply_filters(q, user.company_id, agent, issue, sentiment, date_from, date_to)
    analyses = q.all()
    if not analyses:
        return {"data": []}
    buckets = {"0-49": 0, "50-64": 0, "65-74": 0, "75-84": 0, "85-94": 0, "95-100": 0}
    for (s,) in analyses:
        if s < 50:       buckets["0-49"] += 1
        elif s < 65:     buckets["50-64"] += 1
        elif s < 75:     buckets["65-74"] += 1
        elif s < 85:     buckets["75-84"] += 1
        elif s < 95:     buckets["85-94"] += 1
        else:            buckets["95-100"] += 1
    return {"data": [{"range": k, "count": v} for k, v in buckets.items()]}


# ── Agents table ─────────────────────────────────────────────────────────────
@app.get("/agents")
def agents_table(
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    issue: Optional[str] = Query(None),
    sentiment: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
):
    q = (
        db.query(
            models.Call.agent_id,
            models.Call.agent_name,
            func.count(models.Call.id).label("calls"),
            func.avg(models.CallAnalysis.score).label("avg_score"),
            # Real dominant sentiment via most-common
            func.sum(case((models.CallAnalysis.sentiment == "Positive", 1), else_=0)).label("pos"),
            func.sum(case((models.CallAnalysis.sentiment == "Negative", 1), else_=0)).label("neg"),
            func.sum(case((models.CallAnalysis.sentiment == "Neutral", 1), else_=0)).label("neu"),
        )
        .join(models.CallAnalysis, models.CallAnalysis.call_id == models.Call.id, isouter=True)
    )
    q = _apply_filters(q, user.company_id, None, issue, sentiment, date_from, date_to)
    rows = q.group_by(models.Call.agent_id, models.Call.agent_name).order_by(func.avg(models.CallAnalysis.score).desc()).limit(20).all()

    if not rows:
        return {"agents": []}

    # Compute real trends from last 2 weeks
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)
    two_weeks_ago = now - timedelta(days=14)

    result = []
    for r in rows:
        score = round(r.avg_score or 0)
        # Real sentiment = whichever is highest
        dom_sent = "Neutral"
        if (r.pos or 0) >= (r.neg or 0) and (r.pos or 0) >= (r.neu or 0):
            dom_sent = "Positive"
        elif (r.neg or 0) >= (r.pos or 0) and (r.neg or 0) >= (r.neu or 0):
            dom_sent = "Negative"

        # Real trend: avg score this week vs last week
        curr_score = (
            db.query(func.avg(models.CallAnalysis.score))
            .join(models.Call, models.Call.id == models.CallAnalysis.call_id)
            .filter(models.Call.company_id == user.company_id, models.Call.agent_id == r.agent_id, models.Call.uploaded_at >= week_ago)
            .scalar()
        )
        prev_score = (
            db.query(func.avg(models.CallAnalysis.score))
            .join(models.Call, models.Call.id == models.CallAnalysis.call_id)
            .filter(models.Call.company_id == user.company_id, models.Call.agent_id == r.agent_id,
                    models.Call.uploaded_at >= two_weeks_ago, models.Call.uploaded_at < week_ago)
            .scalar()
        )
        if curr_score and prev_score:
            trend = "up" if curr_score >= prev_score else "down"
        else:
            trend = "up" if score >= 70 else "down"

        result.append({
            "id": r.agent_id,
            "name": r.agent_name,
            "calls": r.calls,
            "score": score,
            "sentiment": dom_sent,
            "trend": trend,
        })
    return {"agents": result}


# ── AI Insights panel ─────────────────────────────────────────────────────────
@app.get("/ai-insights")
def ai_insights(
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    agent: Optional[str] = Query(None),
    issue: Optional[str] = Query(None),
    sentiment: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
):
    cid = user.company_id
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)
    two_weeks_ago = now - timedelta(days=14)

    total = (
        db.query(func.count(models.Call.id))
        .join(models.CallAnalysis, models.CallAnalysis.call_id == models.Call.id, isouter=True)
    )
    total = _apply_filters(total, cid, agent, issue, sentiment, date_from, date_to).scalar() or 0

    if total == 0:
        return {"insights": []}

    # 1. Quality trend — real comparison
    curr_avg = (
        db.query(func.avg(models.CallAnalysis.score))
        .join(models.Call, models.Call.id == models.CallAnalysis.call_id)
        .filter(models.Call.company_id == cid, models.Call.uploaded_at >= week_ago)
        .scalar()
    ) or 0
    prev_avg = (
        db.query(func.avg(models.CallAnalysis.score))
        .join(models.Call, models.Call.id == models.CallAnalysis.call_id)
        .filter(models.Call.company_id == cid, models.Call.uploaded_at >= two_weeks_ago, models.Call.uploaded_at < week_ago)
        .scalar()
    ) or 0
    score_diff = round(curr_avg - prev_avg, 1)
    if score_diff >= 0:
        trend_insight = {
            "icon": "TrendingUp",
            "color": "bg-primary/10 text-primary",
            "title": "Quality trending upward",
            "desc": f"Average quality score improved by {score_diff} pts this week across {total} calls.",
        }
    else:
        trend_insight = {
            "icon": "TrendingUp",
            "color": "bg-warning/10 text-warning",
            "title": "Quality trending downward",
            "desc": f"Average quality score dropped by {abs(score_diff)} pts this week. Review recent calls for patterns.",
        }

    # 2. Top issue spike — real detection
    curr_issues = dict(
        db.query(models.CallAnalysis.issue, func.count(models.CallAnalysis.id))
        .join(models.Call, models.Call.id == models.CallAnalysis.call_id)
        .filter(models.Call.company_id == cid, models.Call.uploaded_at >= week_ago)
        .group_by(models.CallAnalysis.issue).all()
    )
    prev_issues = dict(
        db.query(models.CallAnalysis.issue, func.count(models.CallAnalysis.id))
        .join(models.Call, models.Call.id == models.CallAnalysis.call_id)
        .filter(models.Call.company_id == cid, models.Call.uploaded_at >= two_weeks_ago, models.Call.uploaded_at < week_ago)
        .group_by(models.CallAnalysis.issue).all()
    )
    # Find biggest increase
    spike_issue = None
    spike_pct = 0
    for iss, count in curr_issues.items():
        prev = prev_issues.get(iss, 0)
        if prev > 0:
            pct = round((count - prev) / prev * 100)
            if pct > spike_pct:
                spike_pct = pct
                spike_issue = iss
        elif count >= 3:
            spike_issue = iss
            spike_pct = 100

    if spike_issue and spike_pct > 0:
        issue_insight = {
            "icon": "AlertTriangle",
            "color": "bg-warning/10 text-warning",
            "title": f"{spike_issue} spike detected",
            "desc": f"{spike_issue} calls up {spike_pct}% this week ({curr_issues[spike_issue]} calls) — consider proactive measures.",
        }
    else:
        top_issue = max(curr_issues.items(), key=lambda x: x[1]) if curr_issues else ("General", 0)
        issue_insight = {
            "icon": "AlertTriangle",
            "color": "bg-primary/10 text-primary",
            "title": f"Top issue: {top_issue[0]}",
            "desc": f"{top_issue[0]} accounts for {top_issue[1]} calls this week.",
        }

    # 3. Top agent — real query
    top_agent_row = (
        db.query(
            models.Call.agent_name,
            func.count(models.Call.id).label("calls"),
            func.avg(models.CallAnalysis.score).label("avg_score"),
        )
        .join(models.CallAnalysis, models.CallAnalysis.call_id == models.Call.id)
        .filter(models.Call.company_id == cid)
        .group_by(models.Call.agent_name)
        .order_by(func.avg(models.CallAnalysis.score).desc())
        .first()
    )
    if top_agent_row and top_agent_row.agent_name:
        # Resolution rate
        resolved = (
            db.query(func.count(models.CallAnalysis.id))
            .join(models.Call, models.Call.id == models.CallAnalysis.call_id)
            .filter(models.Call.company_id == cid, models.Call.agent_name == top_agent_row.agent_name,
                    models.CallAnalysis.resolution_status == "Resolved")
            .scalar() or 0
        )
        res_pct = round(resolved / top_agent_row.calls * 100) if top_agent_row.calls > 0 else 0
        agent_insight = {
            "icon": "Zap",
            "color": "bg-success/10 text-success",
            "title": f"Top agent: {top_agent_row.agent_name}",
            "desc": f"Avg score {round(top_agent_row.avg_score)} across {top_agent_row.calls} calls. {res_pct}% resolution rate.",
        }
    else:
        agent_insight = {
            "icon": "Zap",
            "color": "bg-success/10 text-success",
            "title": "Top agent identified",
            "desc": "Upload more calls to identify your top-performing agents.",
        }

    # 4. At-risk customers — real count
    neg_count = (
        db.query(func.count(models.CallAnalysis.id))
        .join(models.Call, models.Call.id == models.CallAnalysis.call_id)
    )
    neg_count = _apply_filters(neg_count, cid, agent, issue, None, date_from, date_to)
    neg_count = neg_count.filter(models.CallAnalysis.sentiment == "Negative").scalar() or 0

    risk_insight = {
        "icon": "BrainCircuit",
        "color": "bg-danger/10 text-danger" if neg_count > 0 else "bg-success/10 text-success",
        "title": f"{neg_count} at-risk customers" if neg_count > 0 else "No at-risk customers",
        "desc": f"{neg_count} negative sentiment calls detected. Recommend proactive outreach within 48 hours." if neg_count > 0
                else "All customers showing positive or neutral sentiment — keep up the good work!",
    }

    return {"insights": [trend_insight, issue_insight, agent_insight, risk_insight]}


# ── Evaluation Framework ──────────────────────────────────────────────────────
DEFAULT_FRAMEWORK = [
    {
        "id": "communication", "name": "Communication Skills", "weight": 30,
        "criteria": [
            {"id": "greeting",    "label": "Professional Greeting",   "weight": 10, "enabled": True},
            {"id": "clarity",     "label": "Clear & Concise Language", "weight": 10, "enabled": True},
            {"id": "tone",        "label": "Positive Tone",            "weight": 10, "enabled": True},
        ],
    },
    {
        "id": "problem_solving", "name": "Problem Solving", "weight": 25,
        "criteria": [
            {"id": "diagnosis",   "label": "Issue Identified Quickly",  "weight": 10, "enabled": True},
            {"id": "resolution",  "label": "First Call Resolution",     "weight": 15, "enabled": True},
        ],
    },
    {
        "id": "empathy", "name": "Empathy & Rapport", "weight": 20,
        "criteria": [
            {"id": "acknowledge", "label": "Acknowledges Frustration",  "weight": 10, "enabled": True},
            {"id": "personalise", "label": "Personalises Interaction",  "weight": 10, "enabled": True},
        ],
    },
    {
        "id": "compliance", "name": "Compliance & Process", "weight": 15,
        "criteria": [
            {"id": "verify",      "label": "Identity Verification",     "weight": 7, "enabled": True},
            {"id": "data",        "label": "Data Privacy Adherence",    "weight": 8, "enabled": True},
        ],
    },
    {
        "id": "close", "name": "Call Closing", "weight": 10,
        "criteria": [
            {"id": "summary",     "label": "Summarises Resolution",     "weight": 5, "enabled": True},
            {"id": "satisfaction","label": "Asks for Satisfaction",     "weight": 5, "enabled": True},
        ],
    },
]


@app.get("/evaluation-framework")
def get_framework(
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    fw = (
        db.query(models.EvaluationFrameworkModel)
        .filter(models.EvaluationFrameworkModel.company_id == user.company_id)
        .first()
    )
    if fw:
        return {"sections": fw.config}
    return {"sections": DEFAULT_FRAMEWORK}


@app.put("/evaluation-framework")
def save_framework(
    sections: list[Any],
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from sqlalchemy.orm.attributes import flag_modified
    fw = (
        db.query(models.EvaluationFrameworkModel)
        .filter(models.EvaluationFrameworkModel.company_id == user.company_id)
        .first()
    )
    if fw:
        fw.config = sections
        flag_modified(fw, "config")
    else:
        fw = models.EvaluationFrameworkModel(company_id=user.company_id, config=sections)
        db.add(fw)
    db.commit()
    return {"status": "saved"}


# ── Live Call Monitor  GET /calls/live ───────────────────────────────────────
@app.get("/calls/live")
def live_calls(
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns the 8 most recent live sessions + recent calls, with analysis data.
    Fully dynamic from the database — no hardcoded fallback.
    """
    now = datetime.now(timezone.utc)

    result = []

    # 1. Live sessions (AI agent conversations)
    sessions = (
        db.query(models.LiveSession)
        .filter(models.LiveSession.company_id == user.company_id)
        .order_by(models.LiveSession.started_at.desc())
        .limit(8)
        .all()
    )
    seen_ids = set()
    for s in sessions:
        # Get last message preview
        last_msg = (
            db.query(models.LiveMessage)
            .filter(models.LiveMessage.session_id == s.id)
            .order_by(models.LiveMessage.seq.desc())
            .first()
        )
        # Get analysis if linked to a call
        analysis = None
        if s.call_id:
            analysis = db.query(models.CallAnalysis).filter(models.CallAnalysis.call_id == s.call_id).first()

        cid = s.contact_id or f"LS-{s.id}"
        seen_ids.add(cid)
        result.append({
            "callId": cid,
            "agentId": s.agent_id or "AI-Agent",
            "agentName": s.agent_name or "AI Agent",
            "duration": s.duration_sec or int((now - s.started_at).total_seconds()) if s.started_at else 0,
            "status": s.status or "complete",
            "sentiment": analysis.sentiment if analysis else None,
            "score": analysis.score if analysis else None,
            "lastMessage": (last_msg.text[:80] + "…" if len(last_msg.text) > 80 else last_msg.text) if last_msg else None,
            "lastSpeaker": last_msg.speaker if last_msg else None,
            "startedAt": s.started_at.isoformat() if s.started_at else None,
            "timeAgo": _time_ago(s.started_at),
            "source": "live_session",
        })

    # 2. Fill remaining slots with recent uploaded/analyzed calls
    remaining = 8 - len(result)
    if remaining > 0:
        q = db.query(models.Call).filter(
            models.Call.company_id == user.company_id,
        )
        if seen_ids:
            q = q.filter(models.Call.contact_id.notin_(seen_ids))
        recent = (
            q.order_by(models.Call.uploaded_at.desc())
            .limit(remaining)
            .all()
        )
        for call in recent:
            analysis = db.query(models.CallAnalysis).filter(models.CallAnalysis.call_id == call.id).first()
            # Preview: first 80 chars of conversation
            preview = None
            if call.conversation:
                preview = call.conversation[:80] + ("…" if len(call.conversation) > 80 else "")
            result.append({
                "callId": call.contact_id or f"C-{call.id}",
                "agentId": call.agent_id or "unknown",
                "agentName": call.agent_name or "Unknown Agent",
                "duration": int((call.duration or 0) * 60),
                "status": call.status or "complete",
                "sentiment": analysis.sentiment if analysis else None,
                "score": analysis.score if analysis else None,
                "lastMessage": preview,
                "lastSpeaker": None,
                "startedAt": call.uploaded_at.isoformat() if call.uploaded_at else None,
                "timeAgo": _time_ago(call.uploaded_at),
                "source": call.source or "upload",
            })

    return {"calls": result}


# ── Live Transcript Analyzer  GET /calls/live-analysis ────────────────────────
@app.get("/calls/live-analysis")
def live_analysis(
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns all live AI-agent calls with full transcript, analysis, and segments.
    Used by the Live Transcript Analyzer frontend page.
    """
    # Include both the user's company AND the DEFAULT_COMPANY_ID (used by Vapi webhooks)
    # so phone calls received via Vapi always appear regardless of which account is logged in.
    company_ids = list({user.company_id, DEFAULT_COMPANY_ID})
    sessions = (
        db.query(models.LiveSession)
        .filter(models.LiveSession.company_id.in_(company_ids))
        .order_by(models.LiveSession.started_at.desc())
        .limit(50)
        .all()
    )

    calls_list = []
    for s in sessions:
        # Get all messages
        messages = (
            db.query(models.LiveMessage)
            .filter(models.LiveMessage.session_id == s.id)
            .order_by(models.LiveMessage.seq.asc())
            .all()
        )

        # Get linked call + analysis
        call = db.query(models.Call).filter(models.Call.id == s.call_id).first() if s.call_id else None
        analysis = db.query(models.CallAnalysis).filter(models.CallAnalysis.call_id == s.call_id).first() if s.call_id else None
        tags = [t.tag for t in db.query(models.CallTag).filter(models.CallTag.call_id == s.call_id).all()] if s.call_id else []

        calls_list.append({
            "sessionId": s.id,
            "callId": s.call_id,
            "contactId": s.contact_id,
            "agentName": s.agent_name or "AI Agent",
            "phone": s.phone_number,
            "status": s.status or "complete",
            "startedAt": s.started_at.isoformat() if s.started_at else None,
            "endedAt": s.ended_at.isoformat() if s.ended_at else None,
            "durationSec": s.duration_sec or 0,
            "timeAgo": _time_ago(s.started_at),
            "transcript": [
                {"seq": m.seq, "speaker": m.speaker, "text": m.text}
                for m in messages
            ],
            "analysis": {
                "sentiment": analysis.sentiment if analysis else None,
                "emotion": analysis.emotion if analysis else None,
                "summary": analysis.summary if analysis else None,
                "issue": analysis.issue if analysis else None,
                "resolutionStatus": analysis.resolution_status if analysis else None,
                "score": analysis.score if analysis else None,
                "agentProfessionalism": analysis.agent_professionalism if analysis else None,
                "customerFrustration": analysis.customer_frustration if analysis else None,
                "communicationScore": analysis.communication_score if analysis else None,
                "problemSolvingScore": analysis.problem_solving_score if analysis else None,
                "empathyScore": analysis.empathy_score if analysis else None,
                "complianceScore": analysis.compliance_score if analysis else None,
                "closingScore": analysis.closing_score if analysis else None,
            } if analysis else None,
            "tags": tags,
        })

    return {"calls": calls_list}


# ── Risk Alerts  GET /calls/risk-alerts ──────────────────────────────────────
@app.get("/calls/risk-alerts")
def risk_alerts(
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    agent: Optional[str] = Query(None),
    issue: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
):
    """Flags from real DB: angry/negative calls, low scores, unresolved."""
    q = (
        db.query(models.CallAnalysis, models.Call)
        .join(models.Call, models.Call.id == models.CallAnalysis.call_id)
    )
    q = _apply_filters(q, user.company_id, agent, issue, None, date_from, date_to)
    analyses = q.order_by(models.CallAnalysis.created_at.desc()).limit(50).all()

    if not analyses:
        return {"alerts": []}

    alerts = []
    for analysis, call in analyses:
        cid = call.contact_id or f"C-{call.id}"
        aid = call.agent_id or "unknown"
        time_str = _time_ago(analysis.created_at)

        # Angry / frustrated customers
        emotion = (analysis.emotion or "").lower()
        if emotion in ("angry", "frustrated") or analysis.sentiment == "Negative":
            alerts.append({
                "id": f"r-angry-{call.id}",
                "type": "angry",
                "callId": cid,
                "agentId": aid,
                "message": f"Customer sentiment: {analysis.emotion or 'Negative'} — possible escalation risk",
                "time": time_str,
            })

        # Low score
        if analysis.score is not None and analysis.score < 50:
            alerts.append({
                "id": f"r-score-{call.id}",
                "type": "lowScore",
                "callId": cid,
                "agentId": aid,
                "message": f"Quality score {analysis.score}/100 — below threshold",
                "time": time_str,
            })

        # Unresolved
        if (analysis.resolution_status or "") == "Not Resolved":
            alerts.append({
                "id": f"r-unres-{call.id}",
                "type": "unresolved",
                "callId": cid,
                "agentId": aid,
                "message": "Issue not resolved — follow-up required",
                "time": time_str,
            })

        if len(alerts) >= 6:
            break

    if not alerts:
        return {"alerts": [
            {"id": "ok", "type": "lowScore", "callId": "—", "agentId": "—",
             "message": "No active alerts — all calls within acceptable parameters", "time": "now"}
        ]}
    return {"alerts": alerts}


# ── Issue Heatmap  GET /heatmap ───────────────────────────────────────────────
@app.get("/heatmap")
def issue_heatmap(
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    agent: Optional[str] = Query(None),
    sentiment: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
):
    """Issue × day-of-week call count from real uploaded_at timestamps."""
    # PostgreSQL: extract(dow from ...) returns 0=Sunday, 1=Monday, ..., 6=Saturday
    day_col = func.cast(func.extract('dow', models.Call.uploaded_at), Integer)
    q = (
        db.query(
            models.CallAnalysis.issue,
            day_col.label("dow"),
            func.count(models.CallAnalysis.id).label("cnt"),
        )
        .join(models.Call, models.Call.id == models.CallAnalysis.call_id)
    )
    q = _apply_filters(q, user.company_id, agent, None, sentiment, date_from, date_to)
    rows = q.group_by(models.CallAnalysis.issue, day_col).all()

    if not rows:
        return {"data": []}

    # Build issue -> {day: count}
    day_map = {1: "mon", 2: "tue", 3: "wed", 4: "thu", 5: "fri", 6: "sat", 0: "sun"}
    issue_data: dict[str, dict[str, int]] = {}
    for r in rows:
        iss = r.issue or "Other"
        if iss not in issue_data:
            issue_data[iss] = {"mon": 0, "tue": 0, "wed": 0, "thu": 0, "fri": 0, "sat": 0, "sun": 0}
        day_key = day_map.get(int(r.dow), "mon")
        issue_data[iss][day_key] = r.cnt

    # Sort by total descending, limit to 6
    sorted_issues = sorted(issue_data.items(), key=lambda x: sum(x[1].values()), reverse=True)[:6]
    return {"data": [{"issue": iss, **counts} for iss, counts in sorted_issues]}


# ── Agent Leaderboard  GET /agents/leaderboard ────────────────────────────────
@app.get("/agents/leaderboard")
def agent_leaderboard(
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    issue: Optional[str] = Query(None),
    sentiment: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
):
    """Returns top 3 and bottom 2 agents with real trend percentages."""
    q = (
        db.query(
            models.Call.agent_id,
            models.Call.agent_name,
            func.count(models.Call.id).label("calls"),
            func.avg(models.CallAnalysis.score).label("avg_score"),
        )
        .join(models.CallAnalysis, models.CallAnalysis.call_id == models.Call.id, isouter=True)
    )
    q = _apply_filters(q, user.company_id, None, issue, sentiment, date_from, date_to)
    rows = q.group_by(models.Call.agent_id, models.Call.agent_name).order_by(func.avg(models.CallAnalysis.score).desc()).all()

    if not rows:
        return {"top": [], "needs_improvement": []}

    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)
    two_weeks_ago = now - timedelta(days=14)

    ranked = []
    for i, r in enumerate(rows):
        score = round(r.avg_score or 0)
        # Real trend: compare this week vs last week avg score
        curr = (
            db.query(func.avg(models.CallAnalysis.score))
            .join(models.Call, models.Call.id == models.CallAnalysis.call_id)
            .filter(models.Call.company_id == user.company_id, models.Call.agent_id == r.agent_id,
                    models.Call.uploaded_at >= week_ago)
            .scalar()
        )
        prev = (
            db.query(func.avg(models.CallAnalysis.score))
            .join(models.Call, models.Call.id == models.CallAnalysis.call_id)
            .filter(models.Call.company_id == user.company_id, models.Call.agent_id == r.agent_id,
                    models.Call.uploaded_at >= two_weeks_ago, models.Call.uploaded_at < week_ago)
            .scalar()
        )
        if curr and prev and prev > 0:
            trend_pct = round((curr - prev) / prev * 100)
        else:
            trend_pct = 0

        ranked.append({
            "id": r.agent_id or f"AG-{i+1:03}",
            "name": r.agent_name or "Unknown",
            "calls": r.calls,
            "score": score,
            "rank": i + 1,
            "trend_pct": trend_pct,
        })

    top  = [a for a in ranked if a["score"] >= 70][:3]
    poor = [a for a in ranked if a["score"] < 70][-2:]
    return {"top": top, "needs_improvement": poor}


# ── Recent Summaries  GET /calls/recent-summaries ─────────────────────────────
@app.get("/calls/recent-summaries")
def recent_summaries(
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    agent: Optional[str] = Query(None),
    issue: Optional[str] = Query(None),
    sentiment: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
):
    """Returns the 5 most recent AI-analysed call summaries."""
    q = (
        db.query(models.CallAnalysis, models.Call)
        .join(models.Call, models.Call.id == models.CallAnalysis.call_id)
    )
    q = _apply_filters(q, user.company_id, agent, issue, sentiment, date_from, date_to)
    rows = q.order_by(models.CallAnalysis.created_at.desc()).limit(5).all()

    if not rows:
        return {"summaries": []}

    result = []
    for analysis, call in rows:
        result.append({
            "callId": call.contact_id or f"C-{call.id}",
            "agent": call.agent_name or "Unknown",
            "score": analysis.score or 0,
            "summary": analysis.summary or "No summary available.",
            "time": _time_ago(call.uploaded_at),
        })
    return {"summaries": result}


# ── Live Session Detail  GET /live-sessions/{id} ─────────────────────────────
@app.get("/live-sessions/{session_id}")
def get_live_session(session_id: int, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    session = (
        db.query(models.LiveSession)
        .filter(models.LiveSession.id == session_id, models.LiveSession.company_id == user.company_id)
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    messages = [
        {"seq": m.seq, "speaker": m.speaker, "text": m.text, "timestamp": m.timestamp.isoformat() if m.timestamp else None}
        for m in session.messages
    ]
    return {
        "id": session.id,
        "agentId": session.agent_id,
        "agentName": session.agent_name,
        "contactId": session.contact_id,
        "phone": session.phone_number,
        "status": session.status,
        "startedAt": session.started_at.isoformat() if session.started_at else None,
        "endedAt": session.ended_at.isoformat() if session.ended_at else None,
        "durationSec": session.duration_sec,
        "messages": messages,
    }


# ── Live Sessions List  GET /live-sessions ────────────────────────────────────
@app.get("/live-sessions")
def list_live_sessions(user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    sessions = (
        db.query(models.LiveSession)
        .filter(models.LiveSession.company_id == user.company_id)
        .order_by(models.LiveSession.started_at.desc())
        .limit(20)
        .all()
    )
    return {"sessions": [
        {
            "id": s.id,
            "agentId": s.agent_id,
            "agentName": s.agent_name,
            "contactId": s.contact_id,
            "status": s.status,
            "durationSec": s.duration_sec,
            "startedAt": s.started_at.isoformat() if s.started_at else None,
            "messageCount": len(s.messages),
        }
        for s in sessions
    ]}


# ── Agents Detail  GET /agents/{agent_code} ──────────────────────────────────
@app.get("/agents/{agent_code}")
def agent_detail(agent_code: str, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    agent = (
        db.query(models.Agent)
        .filter(models.Agent.company_id == user.company_id, models.Agent.agent_code == agent_code)
        .first()
    )
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    call_count = db.query(models.Call).filter(models.Call.company_id == user.company_id, models.Call.agent_id == agent_code).count()
    avg_score = (
        db.query(func.avg(models.CallAnalysis.score))
        .join(models.Call, models.Call.id == models.CallAnalysis.call_id)
        .filter(models.Call.agent_id == agent_code, models.Call.company_id == user.company_id)
        .scalar()
    )
    return {
        "id": agent.id,
        "code": agent.agent_code,
        "name": agent.name,
        "email": agent.email,
        "department": agent.department,
        "shift": agent.shift,
        "isActive": agent.is_active,
        "calls": call_count,
        "avgScore": round(avg_score) if avg_score else 0,
    }


# ── Export data  GET /export-data ──────────────────────────────────────────────
@app.get("/export-data")
def export_data(
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    agent: Optional[str] = Query(None),
    issue: Optional[str] = Query(None),
    sentiment: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
):
    """Return all call+analysis data for export."""
    q = (
        db.query(models.Call, models.CallAnalysis)
        .join(models.CallAnalysis, models.CallAnalysis.call_id == models.Call.id, isouter=True)
    )
    q = _apply_filters(q, user.company_id, agent, issue, sentiment, date_from, date_to)
    rows = q.order_by(models.Call.uploaded_at.desc()).limit(500).all()
    return {"data": [
        {
            "callId": c.contact_id or f"C-{c.id}",
            "agent": c.agent_name or "Unknown",
            "score": a.score if a else 0,
            "sentiment": a.sentiment if a else "Unknown",
            "issue": a.issue if a else "Unknown",
            "resolved": (a.resolution_status or "") == "Resolved" if a else False,
            "duration": round(c.duration or 0, 1),
            "date": c.uploaded_at.strftime("%Y-%m-%d %H:%M") if c.uploaded_at else "",
        }
        for c, a in rows
    ]}


# ── Generate demo data  POST /generate-demo ──────────────────────────────────
@app.post("/generate-demo")
def generate_demo(
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate sample calls in the DB for demo purposes."""
    agents = [
        ("AG-001", "Sarah Mitchell"), ("AG-002", "James Okafor"), ("AG-003", "Priya Sharma"),
        ("AG-004", "Carlos Rivera"), ("AG-005", "Emily Zhang"), ("AG-006", "David Kim"),
    ]
    issues = ["Billing Issue", "Technical Problem", "Account Access", "Service Outage", "Refund Request", "Product Query"]
    sentiments = ["Positive", "Positive", "Positive", "Neutral", "Neutral", "Negative"]
    templates = [
        "Customer called about {issue}. Agent handled the call professionally and resolved the issue.",
        "Customer had a question about {issue}. Agent provided clear information and assisted effectively.",
        "Customer was frustrated about {issue}. Agent showed empathy but could not fully resolve.",
        "Customer reported {issue}. Agent escalated to specialist team for further investigation.",
        "Customer complained about {issue}. Agent attempted resolution but customer remained dissatisfied.",
    ]

    now = datetime.now(timezone.utc)
    created = 0
    for i in range(50):
        agent_id, agent_name = random.choice(agents)
        iss = random.choice(issues)
        sent = random.choice(sentiments)
        score = random.randint(75, 98) if sent == "Positive" else random.randint(55, 74) if sent == "Neutral" else random.randint(25, 54)
        tpl = random.choice(templates).format(issue=iss.lower())
        days_ago = random.randint(0, 55)

        call = models.Call(
            company_id=user.company_id,
            contact_id=f"DEMO-{now.strftime('%m%d')}-{i+1:03d}",
            agent_id=agent_id,
            agent_name=agent_name,
            conversation=tpl,
            duration=round(random.uniform(2, 20), 1),
            source="upload",
            uploaded_at=now - timedelta(days=days_ago, hours=random.randint(0, 23)),
        )
        db.add(call)
        db.flush()
        analysis = models.CallAnalysis(
            call_id=call.id,
            company_id=user.company_id,
            sentiment=sent,
            issue=iss,
            score=score,
            summary=tpl,
            emotion="Calm" if sent == "Positive" else "Frustrated" if sent == "Negative" else "Neutral",
            resolution_status="Resolved" if score >= 70 else "Partially Resolved" if score >= 50 else "Not Resolved",
            created_at=call.uploaded_at,
        )
        db.add(analysis)
        created += 1

    db.commit()
    return {"created": created, "message": f"{created} demo calls generated successfully"}


# ── Simulate Call for Testing (no phone needed) ─────────────────────────────
from fastapi import Body

@app.post("/calls/simulate")
def simulate_call(
    transcript: str = Body(None, embed=True),
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Simulate a call: runs the analysis pipeline on a sample transcript.
    Creates a Call + LiveSession + LiveMessages so it appears in the
    Live Transcript Analyzer page alongside real Vapi calls.
    If transcript is not provided, uses a built-in sample conversation.
    """
    if not transcript:
        transcript = (
            "Agent: Hello! Thank you for calling ReviewSense. How can I help you today?\n"
            "Customer: Hi, I have been having issues with my account. I cannot log in and it keeps showing an error.\n"
            "Agent: I am sorry about that. Can you tell me what error you are seeing?\n"
            "Customer: It says invalid credentials but my password is correct. I have tried for 2 days and I am really frustrated.\n"
            "Agent: I completely understand your frustration. Let me check your account. What is your registered email?\n"
            "Customer: john.doe@example.com\n"
            "Agent: Your account was locked due to multiple failed attempts. I have reset it and sent a password reset link to your email.\n"
            "Customer: Oh great, I can see the email now. Yes I am logged in! Thank you so much!\n"
            "Agent: Wonderful! Is there anything else I can help you with?\n"
            "Customer: No, that's all. Have a great day!\n"
            "Agent: You too! Goodbye."
        )

    now = datetime.now(timezone.utc)

    # ── 1. Create Call record ─────────────────────────────────────────────────
    # Bug fix: field is phone_number, not phone
    call = models.Call(
        company_id=user.company_id,
        agent_id="sim-agent",
        agent_name="Simulated Agent",
        contact_id=f"sim-{now.strftime('%Y%m%d%H%M%S')}",
        phone_number="+10000000000",
        uploaded_at=now,
        conversation=transcript,
        source="ai_agent",
        status="analyzing",
    )
    db.add(call)
    db.flush()  # get call.id without committing

    # ── 2. Parse transcript into (speaker, text) turns ────────────────────────
    turns = []
    for line in transcript.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        if line.lower().startswith("agent:"):
            turns.append(("agent", line[6:].strip()))
        elif line.lower().startswith("customer:"):
            turns.append(("customer", line[9:].strip()))
        else:
            turns.append(("system", line))

    # ── 3. Create LiveSession so it shows in Live Transcript Analyzer ─────────
    # Bug fix: without LiveSession the simulated call never appears on the page
    session = models.LiveSession(
        company_id=user.company_id,
        call_id=call.id,
        agent_id="sim-agent",
        agent_name="Simulated Agent",
        contact_id=call.contact_id,
        phone_number="+10000000000",
        status="analyzing",
        started_at=now,
        ended_at=now,
        duration_sec=len(turns) * 8,  # rough estimate
    )
    db.add(session)
    db.flush()  # get session.id

    # ── 4. Create LiveMessages (one per transcript turn) ─────────────────────
    for seq, (speaker, text) in enumerate(turns, 1):
        db.add(models.LiveMessage(
            session_id=session.id,
            seq=seq,
            speaker=speaker,
            text=text,
        ))

    db.commit()
    db.refresh(call)
    db.refresh(session)

    # ── 5. Run LLM analysis pipeline ─────────────────────────────────────────
    from ai_pipeline.evaluator import evaluate_call_full
    analysis_data = evaluate_call_full(transcript)

    # Bug fix: evaluator returns 'issue_category', not 'issue'
    analysis = models.CallAnalysis(
        call_id=call.id,
        company_id=user.company_id,
        sentiment=analysis_data.get("sentiment"),
        summary=analysis_data.get("summary"),
        issue=analysis_data.get("issue_category", analysis_data.get("issue", "General Inquiry")),
        score=analysis_data.get("quality_score", analysis_data.get("score", 0)),
        emotion=analysis_data.get("emotion"),
        resolution_status=analysis_data.get("resolution_status"),
        agent_professionalism=analysis_data.get("agent_professionalism"),
        customer_frustration=analysis_data.get("customer_frustration"),
        communication_score=analysis_data.get("communication_score"),
        problem_solving_score=analysis_data.get("problem_solving_score"),
        empathy_score=analysis_data.get("empathy_score"),
        compliance_score=analysis_data.get("compliance_score"),
        closing_score=analysis_data.get("closing_score"),
    )
    db.add(analysis)

    # ── 6. Mark session + call as complete ────────────────────────────────────
    call.status = "complete"
    session.status = "complete"
    db.commit()

    return {"status": "ok", "call_id": call.id, "session_id": session.id, "analysis": analysis_data}


# ═════════════════════════════════════════════════════════════════════════════
# WAREHOUSE / ETL ENDPOINTS
# ═════════════════════════════════════════════════════════════════════════════
from etl.warehouse_models import (
    BronzeRawCall, SilverCall, SilverAgent, SilverInteraction, SilverExtractedEntity,
    DimDate, DimAgent, DimIssue, DimSentiment, DimResolution, DimCallSource,
    FactCall, FactAgentDaily, FactDailySummary, FactIssueResolution,
)


@app.get("/warehouse/summary")
def warehouse_summary(db: Session = Depends(get_db), _user=Depends(get_current_user)):
    """Overall warehouse counts and health check."""
    return {
        "bronze_raw_calls": db.query(BronzeRawCall).count(),
        "silver_calls": db.query(SilverCall).count(),
        "silver_agents": db.query(SilverAgent).count(),
        "silver_interactions": db.query(SilverInteraction).count(),
        "silver_entities": db.query(SilverExtractedEntity).count(),
        "dim_date": db.query(DimDate).count(),
        "dim_agent": db.query(DimAgent).count(),
        "dim_issue": db.query(DimIssue).count(),
        "dim_sentiment": db.query(DimSentiment).count(),
        "dim_resolution": db.query(DimResolution).count(),
        "dim_call_source": db.query(DimCallSource).count(),
        "fact_calls": db.query(FactCall).count(),
        "fact_agent_daily": db.query(FactAgentDaily).count(),
        "fact_daily_summary": db.query(FactDailySummary).count(),
        "fact_issue_resolution": db.query(FactIssueResolution).count(),
    }


@app.get("/warehouse/fact-calls")
def warehouse_fact_calls(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    agent_id: Optional[str] = None,
    sentiment: Optional[str] = None,
    issue: Optional[str] = None,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Paginated fact_calls with optional filters."""
    q = (
        db.query(
            FactCall,
            DimAgent.agent_name,
            DimIssue.issue_category,
            DimSentiment.sentiment_label,
            DimResolution.resolution_status,
        )
        .outerjoin(DimAgent, FactCall.agent_key == DimAgent.agent_key)
        .outerjoin(DimIssue, FactCall.issue_key == DimIssue.issue_key)
        .outerjoin(DimSentiment, FactCall.sentiment_key == DimSentiment.sentiment_key)
        .outerjoin(DimResolution, FactCall.resolution_key == DimResolution.resolution_key)
    )
    if agent_id:
        q = q.filter(DimAgent.agent_id == agent_id)
    if sentiment:
        q = q.filter(DimSentiment.sentiment_label == sentiment)
    if issue:
        q = q.filter(DimIssue.issue_category == issue)

    total = q.count()
    rows = q.order_by(FactCall.call_key.desc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "data": [
            {
                "call_key": fc.call_key,
                "contact_id": fc.contact_id,
                "agent_name": agent_name,
                "issue": issue_cat,
                "sentiment": sent,
                "resolution": res,
                "quality_score": fc.quality_score,
                "duration_minutes": fc.duration_minutes,
                "communication_score": fc.communication_score,
                "problem_solving_score": fc.problem_solving_score,
                "empathy_score": fc.empathy_score,
                "compliance_score": fc.compliance_score,
                "closing_score": fc.closing_score,
                "word_count": fc.word_count,
                "turn_count": fc.turn_count,
                "has_ticket": fc.has_ticket,
                "has_refund": fc.has_refund,
                "has_escalation": fc.has_escalation,
            }
            for fc, agent_name, issue_cat, sent, res in rows
        ],
    }


@app.get("/warehouse/agent-performance")
def warehouse_agent_performance(
    db: Session = Depends(get_db), _user=Depends(get_current_user)
):
    """Per-agent performance from fact_agent_daily rolled up."""
    rows = (
        db.query(
            DimAgent.agent_id,
            DimAgent.agent_name,
            func.sum(FactAgentDaily.total_calls).label("total_calls"),
            func.avg(FactAgentDaily.avg_quality_score).label("avg_quality"),
            func.avg(FactAgentDaily.avg_duration).label("avg_duration"),
            func.sum(FactAgentDaily.positive_calls).label("positive"),
            func.sum(FactAgentDaily.negative_calls).label("negative"),
            func.sum(FactAgentDaily.neutral_calls).label("neutral"),
            func.sum(FactAgentDaily.resolved_calls).label("resolved"),
            func.sum(FactAgentDaily.escalated_calls).label("escalated"),
            func.sum(FactAgentDaily.refund_calls).label("refunds"),
        )
        .join(FactAgentDaily, FactAgentDaily.agent_key == DimAgent.agent_key)
        .group_by(DimAgent.agent_id, DimAgent.agent_name)
        .order_by(func.avg(FactAgentDaily.avg_quality_score).desc())
        .all()
    )
    return [
        {
            "agent_id": r.agent_id,
            "agent_name": r.agent_name,
            "total_calls": int(r.total_calls or 0),
            "avg_quality": round(float(r.avg_quality or 0), 1),
            "avg_duration": round(float(r.avg_duration or 0), 1),
            "positive_calls": int(r.positive or 0),
            "negative_calls": int(r.negative or 0),
            "neutral_calls": int(r.neutral or 0),
            "resolved_calls": int(r.resolved or 0),
            "escalated_calls": int(r.escalated or 0),
            "refund_calls": int(r.refunds or 0),
        }
        for r in rows
    ]


@app.get("/warehouse/issue-breakdown")
def warehouse_issue_breakdown(
    db: Session = Depends(get_db), _user=Depends(get_current_user)
):
    """Issue category breakdown from gold layer."""
    rows = (
        db.query(
            DimIssue.issue_category,
            DimIssue.issue_group,
            func.count(FactCall.call_key).label("total"),
            func.avg(FactCall.quality_score).label("avg_score"),
            func.avg(FactCall.duration_minutes).label("avg_duration"),
        )
        .join(FactCall, FactCall.issue_key == DimIssue.issue_key)
        .group_by(DimIssue.issue_category, DimIssue.issue_group)
        .order_by(func.count(FactCall.call_key).desc())
        .all()
    )
    return [
        {
            "issue": r.issue_category,
            "group": r.issue_group,
            "total_calls": r.total,
            "avg_quality": round(float(r.avg_score or 0), 1),
            "avg_duration": round(float(r.avg_duration or 0), 1),
        }
        for r in rows
    ]


@app.get("/warehouse/sentiment-distribution")
def warehouse_sentiment_distribution(
    db: Session = Depends(get_db), _user=Depends(get_current_user)
):
    """Sentiment distribution from gold fact table."""
    rows = (
        db.query(
            DimSentiment.sentiment_label,
            func.count(FactCall.call_key).label("count"),
        )
        .join(FactCall, FactCall.sentiment_key == DimSentiment.sentiment_key)
        .group_by(DimSentiment.sentiment_label)
        .all()
    )
    return {r.sentiment_label: r.count for r in rows}


@app.get("/warehouse/daily-summary")
def warehouse_daily_summary(
    db: Session = Depends(get_db), _user=Depends(get_current_user)
):
    """Daily summary from pre-aggregated fact table."""
    rows = (
        db.query(FactDailySummary, DimDate.full_date)
        .join(DimDate, FactDailySummary.date_key == DimDate.date_key)
        .order_by(DimDate.full_date.desc())
        .limit(90)
        .all()
    )
    return [
        {
            "date": str(dt),
            "total_calls": fs.total_calls,
            "avg_quality": fs.avg_quality_score,
            "avg_duration": fs.avg_duration,
            "positive": fs.positive_calls,
            "negative": fs.negative_calls,
            "neutral": fs.neutral_calls,
            "top_issue": fs.top_issue,
            "unique_agents": fs.unique_agents,
            "escalations": fs.total_escalations,
            "refunds": fs.total_refunds,
        }
        for fs, dt in rows
    ]


@app.get("/warehouse/silver-entities")
def warehouse_silver_entities(
    entity_type: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Extracted entities from silver layer (tickets, accounts, emails, etc)."""
    q = db.query(
        SilverExtractedEntity.entity_type,
        SilverExtractedEntity.entity_value,
        func.count(SilverExtractedEntity.id).label("count"),
    ).group_by(SilverExtractedEntity.entity_type, SilverExtractedEntity.entity_value)

    if entity_type:
        q = q.filter(SilverExtractedEntity.entity_type == entity_type)

    rows = q.order_by(func.count(SilverExtractedEntity.id).desc()).limit(limit).all()
    return [{"type": r.entity_type, "value": r.entity_value, "count": r.count} for r in rows]


@app.get("/warehouse/etl-run")
def warehouse_etl_trigger(
    db: Session = Depends(get_db), _user=Depends(get_current_user)
):
    """Trigger a full ETL pipeline run (bronze → silver → gold)."""
    from etl.bronze import ingest_raw_files
    from etl.silver import transform_to_silver
    from etl.gold import populate_dimensions, build_facts

    bronze = ingest_raw_files(db)
    batch_id = bronze.get("batch_id")

    silver = transform_to_silver(db, batch_id=batch_id)

    populate_dimensions(db)
    gold = build_facts(db, batch_id=batch_id)

    return {
        "bronze": bronze,
        "silver": silver,
        "gold": gold,
    }


# ── Health ────────────────────────────────────────────────────────────────────
@app.get("/")
def root():
    return {"message": "ReViewSense AI backend running ✓"}


# ── Dev runner ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000, reload=False)

