"""
n8n Analysis Webhook Routes — receives analysis results from n8n workflows.

Flow:
  1. Vapi webhook stores transcript → triggers n8n
  2. n8n AI Agent 1: segments conversation, classifies intent
  3. n8n AI Agent 2: sentiment + quality scoring
  4. n8n posts results back here → stored in call_analysis + embeddings
"""

import os
import sys
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import get_db
import models

# Make ai_pipeline importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from ai_pipeline.evaluator import chunk_transcript, embed_chunks

router = APIRouter(prefix="/n8n", tags=["n8n"])

N8N_AUTH_TOKEN = os.getenv("N8N_AUTH_TOKEN", "")


# ── Auth helper ───────────────────────────────────────────────────────────────

def _verify_n8n_token(request: Request):
    """Simple bearer token check for n8n callbacks."""
    if not N8N_AUTH_TOKEN:
        return  # skip if not configured
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer ") or auth[7:] != N8N_AUTH_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid n8n auth token")


# ── Schemas ───────────────────────────────────────────────────────────────────

class SegmentationResult(BaseModel):
    """Result from n8n AI Agent 1 — conversation segmentation."""
    call_id: int
    segments: list[dict] = Field(default_factory=list)
    # Each segment: {phase, text, speaker_turns, start_seq, end_seq}
    intent: str = "General Inquiry"
    topics: list[str] = Field(default_factory=list)
    entities: dict = Field(default_factory=dict)
    # entities: {account_numbers: [], product_names: [], dates: []}
    language_detected: str = "en"


class SentimentResult(BaseModel):
    """Result from n8n AI Agent 2 — full sentiment + quality analysis."""
    call_id: int
    sentiment: str = "Neutral"                # Positive / Neutral / Negative
    emotion: str = "Calm"                     # Calm / Frustrated / Angry / etc.
    summary: str = ""
    issue_category: str = "General Inquiry"
    resolution_status: str = "Not Resolved"   # Resolved / Partially / Not Resolved
    quality_score: int = 50                   # 0–100 overall
    agent_professionalism: int = 3            # 1–5
    customer_frustration: int = 2             # 1–5
    communication_score: Optional[int] = None   # 0–30
    problem_solving_score: Optional[int] = None # 0–25
    empathy_score: Optional[int] = None         # 0–20
    compliance_score: Optional[int] = None      # 0–15
    closing_score: Optional[int] = None         # 0–10
    tags: list[str] = Field(default_factory=list)
    # Additional fields from segmentation (can be piped through)
    segments: list[dict] = Field(default_factory=list)
    per_segment_sentiment: list[dict] = Field(default_factory=list)


class FullAnalysisResult(BaseModel):
    """Combined single-shot result — if n8n sends everything at once."""
    call_id: int
    sentiment: str = "Neutral"
    emotion: str = "Calm"
    summary: str = ""
    issue_category: str = "General Inquiry"
    resolution_status: str = "Not Resolved"
    quality_score: int = 50
    agent_professionalism: int = 3
    customer_frustration: int = 2
    communication_score: Optional[int] = None
    problem_solving_score: Optional[int] = None
    empathy_score: Optional[int] = None
    compliance_score: Optional[int] = None
    closing_score: Optional[int] = None
    tags: list[str] = Field(default_factory=list)
    segments: list[dict] = Field(default_factory=list)
    per_segment_sentiment: list[dict] = Field(default_factory=list)
    language_detected: str = "en"
    intent: str = "General Inquiry"
    topics: list[str] = Field(default_factory=list)
    entities: dict = Field(default_factory=dict)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/segments")
def receive_segments(
    body: SegmentationResult,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    n8n AI Agent 1 posts segmentation results here.
    Stores segment data as tags + updates call metadata.
    """
    _verify_n8n_token(request)

    call = db.query(models.Call).filter(models.Call.id == body.call_id).first()
    if not call:
        raise HTTPException(status_code=404, detail=f"Call {body.call_id} not found")

    # Store topics as tags
    for topic in body.topics:
        existing = db.query(models.CallTag).filter(
            models.CallTag.call_id == call.id,
            models.CallTag.tag == topic[:100],
        ).first()
        if not existing:
            db.add(models.CallTag(call_id=call.id, tag=topic[:100]))

    # Store intent as a tag too
    if body.intent:
        existing = db.query(models.CallTag).filter(
            models.CallTag.call_id == call.id,
            models.CallTag.tag == f"intent:{body.intent[:90]}",
        ).first()
        if not existing:
            db.add(models.CallTag(call_id=call.id, tag=f"intent:{body.intent[:90]}"))

    db.commit()

    print(f"[n8n] Segments stored for call #{body.call_id}: {len(body.segments)} segments, {len(body.topics)} topics")
    return {"status": "ok", "call_id": body.call_id, "segments_count": len(body.segments)}


@router.post("/sentiment")
def receive_sentiment(
    body: SentimentResult,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    n8n AI Agent 2 posts sentiment + quality analysis here.
    Stores/updates call_analysis, generates embeddings, marks call complete.
    """
    _verify_n8n_token(request)

    call = db.query(models.Call).filter(models.Call.id == body.call_id).first()
    if not call:
        raise HTTPException(status_code=404, detail=f"Call {body.call_id} not found")

    # Upsert CallAnalysis
    analysis = db.query(models.CallAnalysis).filter(
        models.CallAnalysis.call_id == call.id
    ).first()

    if not analysis:
        analysis = models.CallAnalysis(
            call_id=call.id,
            company_id=call.company_id,
        )
        db.add(analysis)

    # Update all fields
    analysis.sentiment = body.sentiment
    analysis.emotion = body.emotion
    analysis.summary = body.summary
    analysis.issue = body.issue_category
    analysis.resolution_status = body.resolution_status
    analysis.score = max(0, min(100, body.quality_score))
    analysis.agent_professionalism = max(1, min(5, body.agent_professionalism))
    analysis.customer_frustration = max(1, min(5, body.customer_frustration))
    analysis.communication_score = body.communication_score
    analysis.problem_solving_score = body.problem_solving_score
    analysis.empathy_score = body.empathy_score
    analysis.compliance_score = body.compliance_score
    analysis.closing_score = body.closing_score

    # Store tags
    for tag in body.tags:
        existing = db.query(models.CallTag).filter(
            models.CallTag.call_id == call.id,
            models.CallTag.tag == tag[:100],
        ).first()
        if not existing:
            db.add(models.CallTag(call_id=call.id, tag=tag[:100]))

    # Mark call complete
    call.status = "complete"

    # Update live session status too
    session = db.query(models.LiveSession).filter(
        models.LiveSession.call_id == call.id
    ).first()
    if session:
        session.status = "complete"

    db.commit()

    # Generate embeddings for RAG (async-safe, runs inline)
    _generate_embeddings(call, db)

    print(f"[n8n] Sentiment stored for call #{body.call_id}: {body.sentiment}, score={body.quality_score}")

    return {
        "status": "ok",
        "call_id": body.call_id,
        "sentiment": body.sentiment,
        "score": body.quality_score,
    }


@router.post("/result")
def receive_full_result(
    body: FullAnalysisResult,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Single endpoint for n8n to POST the complete analysis at once.
    Handles segmentation + sentiment + scoring + embedding in one call.
    """
    _verify_n8n_token(request)

    call = db.query(models.Call).filter(models.Call.id == body.call_id).first()
    if not call:
        raise HTTPException(status_code=404, detail=f"Call {body.call_id} not found")

    # Upsert CallAnalysis
    analysis = db.query(models.CallAnalysis).filter(
        models.CallAnalysis.call_id == call.id
    ).first()

    if not analysis:
        analysis = models.CallAnalysis(
            call_id=call.id,
            company_id=call.company_id,
        )
        db.add(analysis)

    analysis.sentiment = body.sentiment
    analysis.emotion = body.emotion
    analysis.summary = body.summary
    analysis.issue = body.issue_category
    analysis.resolution_status = body.resolution_status
    analysis.score = max(0, min(100, body.quality_score))
    analysis.agent_professionalism = max(1, min(5, body.agent_professionalism))
    analysis.customer_frustration = max(1, min(5, body.customer_frustration))
    analysis.communication_score = body.communication_score
    analysis.problem_solving_score = body.problem_solving_score
    analysis.empathy_score = body.empathy_score
    analysis.compliance_score = body.compliance_score
    analysis.closing_score = body.closing_score

    # Store all tags (topics + entities + custom tags)
    all_tags = set(body.tags + body.topics)
    if body.intent:
        all_tags.add(f"intent:{body.intent}")
    if body.language_detected and body.language_detected != "en":
        all_tags.add(f"lang:{body.language_detected}")
    for tag in all_tags:
        existing = db.query(models.CallTag).filter(
            models.CallTag.call_id == call.id,
            models.CallTag.tag == tag[:100],
        ).first()
        if not existing:
            db.add(models.CallTag(call_id=call.id, tag=tag[:100]))

    # Mark call complete
    call.status = "complete"

    # Update live session
    session = db.query(models.LiveSession).filter(
        models.LiveSession.call_id == call.id
    ).first()
    if session:
        session.status = "complete"

    db.commit()

    # Generate embeddings for RAG
    _generate_embeddings(call, db)

    print(f"[n8n] Full result stored for call #{body.call_id}: {body.sentiment}, score={body.quality_score}")

    return {
        "status": "ok",
        "call_id": body.call_id,
        "sentiment": body.sentiment,
        "score": body.quality_score,
        "tags_count": len(all_tags),
    }


# ── Health check for n8n to verify connectivity ──────────────────────────────

@router.get("/health")
def n8n_health():
    return {"status": "ok", "service": "n8n-webhook"}


# ── Embedding helper ──────────────────────────────────────────────────────────

def _generate_embeddings(call: models.Call, db: Session):
    """Generate and store transcript chunk embeddings for RAG retrieval."""
    if not call.conversation:
        return

    try:
        # Remove old embeddings
        db.query(models.CallEmbedding).filter(
            models.CallEmbedding.call_id == call.id
        ).delete()

        # Chunk + embed
        chunks = chunk_transcript(call.conversation)
        embeddings = embed_chunks(chunks)

        for i, (chunk, emb) in enumerate(zip(chunks, embeddings)):
            db.add(models.CallEmbedding(
                call_id=call.id,
                company_id=call.company_id,
                chunk_index=i,
                chunk_text=chunk,
                embedding=emb,
            ))

        db.commit()
        print(f"[n8n] Generated {len(chunks)} embeddings for call #{call.id}")
    except Exception as e:
        print(f"[n8n] Embedding generation failed for call #{call.id}: {e}")
        db.rollback()
