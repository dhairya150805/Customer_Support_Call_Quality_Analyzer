"""
Gold Layer — Build dimension & fact tables from silver layer.

Runs the existing AI pipeline (Groq LLM) on silver transcripts,
then populates the star-schema gold tables.

Steps:
  1. Populate / refresh dim_date (calendar table)
  2. Populate dim_agent, dim_issue, dim_sentiment, dim_resolution, dim_call_source
  3. For each silver_call without a fact_calls row:
     a. Run LLM evaluation → get sentiment, issue, score, etc.
     b. Insert into the existing calls + call_analysis tables (so dashboard stays live)
     c. Insert into fact_calls with dimension keys
  4. Roll up fact_agent_daily and fact_daily_summary
"""

import os
import sys
from datetime import date, datetime, timedelta, timezone
from collections import defaultdict
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import func as sqlfunc, case

# Make ai_pipeline importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from etl.warehouse_models import (
    SilverCall,
    DimDate,
    DimAgent,
    DimIssue,
    DimSentiment,
    DimResolution,
    DimCallSource,
    FactCall,
    FactAgentDaily,
    FactDailySummary,
    FactIssueResolution,
)

# Import existing models so we also write to the operational DB tables
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import models
from ai_pipeline.evaluator import evaluate_call, chunk_transcript, embed_chunks


# ═══════════════════════════════════════════════════════════════════════════════
# 1. DIMENSION BUILDERS
# ═══════════════════════════════════════════════════════════════════════════════

_MONTH_NAMES = [
    "", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]
_DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def populate_dim_date(db: Session, start_year: int = 2024, end_year: int = 2027):
    """Fill dim_date with calendar rows from start_year to end_year."""
    existing = db.query(sqlfunc.count(DimDate.date_key)).scalar()
    if existing > 0:
        return  # already populated

    print("[gold] Populating dim_date …")
    current = date(start_year, 1, 1)
    end = date(end_year, 12, 31)
    rows = []
    while current <= end:
        rows.append(DimDate(
            date_key=int(current.strftime("%Y%m%d")),
            full_date=current,
            year=current.year,
            quarter=(current.month - 1) // 3 + 1,
            month=current.month,
            month_name=_MONTH_NAMES[current.month],
            day=current.day,
            day_of_week=current.weekday(),   # 0=Mon
            day_name=_DAY_NAMES[current.weekday()],
            week_of_year=current.isocalendar()[1],
            is_weekend=current.weekday() >= 5,
        ))
        current += timedelta(days=1)

    db.bulk_save_objects(rows)
    db.commit()
    print(f"[gold]  ✓ {len(rows)} date rows inserted")


def _ensure_dim_row(db: Session, model, unique_col_name: str, value: str, **extra):
    """Get-or-create a dimension row; returns the primary key."""
    col = getattr(model, unique_col_name)
    row = db.query(model).filter(col == value).first()
    if row:
        return getattr(row, list(model.__table__.primary_key.columns.keys())[0])
    new = model(**{unique_col_name: value, **extra})
    db.add(new)
    db.flush()
    return getattr(new, list(model.__table__.primary_key.columns.keys())[0])


def populate_dimensions(db: Session):
    """Seed static dimension rows."""
    populate_dim_date(db)

    # Ensure at least the core sentiment options exist
    for label in ("Positive", "Negative", "Neutral"):
        _ensure_dim_row(db, DimSentiment, "sentiment_label", label)

    for status in ("Resolved", "Partially Resolved", "Not Resolved", "Pending"):
        _ensure_dim_row(db, DimResolution, "resolution_status", status)

    for src in ("upload", "live", "ai_agent", "manual"):
        _ensure_dim_row(db, DimCallSource, "source_label", src)

    db.commit()
    print("[gold] Dimensions seeded")


# ═══════════════════════════════════════════════════════════════════════════════
# 2. FACT BUILDER — process silver → gold + operational tables
# ═══════════════════════════════════════════════════════════════════════════════

def _issue_group(issue: str) -> str:
    """Classify issue into a broader group."""
    lower = issue.lower()
    if any(w in lower for w in ("billing", "charge", "refund", "invoice", "payment", "pricing")):
        return "billing"
    if any(w in lower for w in ("technical", "bug", "crash", "error", "integration", "api")):
        return "technical"
    if any(w in lower for w in ("account", "login", "password", "2fa", "security", "access")):
        return "account"
    if any(w in lower for w in ("cancel", "downgrade", "upgrade", "plan", "subscription")):
        return "subscription"
    return "general"


def build_facts(db: Session, company_id: int = 1, *, batch_id: Optional[str] = None) -> dict:
    """
    For each silver_call not yet in fact_calls:
      - Run LLM evaluation
      - Write to operational tables (calls, call_analysis)
      - Write to fact_calls
    """
    # Auto-detect company_id from DB if default doesn't exist
    company = db.query(models.Company).filter(models.Company.id == company_id).first()
    if not company:
        company = db.query(models.Company).first()
        if company:
            company_id = company.id
            print(f"[gold] Using company_id={company_id} ({company.name})")
        else:
            print("[gold] ⚠ No company found — creating default")
            company = models.Company(name="TechCo Solutions", domain="techco.com")
            db.add(company)
            db.flush()
            company_id = company.id

    # Find silver calls not yet in fact_calls
    already = set(
        r[0] for r in db.query(FactCall.silver_call_id).all()
    )
    query = db.query(SilverCall)
    if batch_id:
        query = query.filter(SilverCall.batch_id == batch_id)
    silver_rows = query.order_by(SilverCall.id).all()

    pending = [sc for sc in silver_rows if sc.id not in already]
    if not pending:
        print("[gold] No new silver calls to process.")
        return {"processed": 0}

    print(f"[gold] Building facts for {len(pending)} calls (LLM evaluation) …")
    processed = 0

    for sc in pending:
        transcript = sc.transcript_clean or ""

        # ── LLM evaluation ────────────────────────────────────────────────────
        try:
            result = evaluate_call(transcript)
        except Exception as exc:
            print(f"[gold]  ⚠ LLM failed for silver_call {sc.id}: {exc}")
            result = {
                "sentiment": "Neutral",
                "summary": "Evaluation failed.",
                "issue": "General Inquiry",
                "score": 50,
                "emotion": "Neutral",
                "resolution_status": "Pending",
                "agent_professionalism": 3,
                "customer_frustration": 3,
            }

        sentiment = result.get("sentiment", "Neutral")
        issue     = result.get("issue_category") or result.get("issue", "General Inquiry")
        resolution = result.get("resolution_status", "Pending")
        score     = result.get("quality_score") or result.get("score", 50)

        # Score breakdown (derive from total if LLM didn't return them)
        comm  = result.get("communication_score") or round(score * 0.30)
        prob  = result.get("problem_solving_score") or round(score * 0.25)
        emp   = result.get("empathy_score") or round(score * 0.20)
        comp  = result.get("compliance_score") or round(score * 0.15)
        clos  = result.get("closing_score") or round(score * 0.10)

        # ── Write to operational Call + CallAnalysis ──────────────────────────
        call = models.Call(
            company_id=company_id,
            contact_id=sc.contact_id,
            agent_id=sc.agent_id,
            agent_name=sc.agent_name,
            conversation=sc.transcript_clean,
            duration=sc.duration_minutes,
            source="upload",
            call_type="inbound",
            status="complete",
        )
        # link to agents table
        agent_ref = db.query(models.Agent).filter(
            models.Agent.agent_code == sc.agent_id,
            models.Agent.company_id == company_id,
        ).first()
        if agent_ref:
            call.agent_ref_id = agent_ref.id

        db.add(call)
        db.flush()

        analysis = models.CallAnalysis(
            call_id=call.id,
            company_id=company_id,
            sentiment=sentiment,
            summary=result.get("summary", ""),
            issue=issue,
            score=int(score),
            emotion=result.get("emotion", "Neutral"),
            resolution_status=resolution,
            agent_professionalism=result.get("agent_professionalism"),
            customer_frustration=result.get("customer_frustration"),
            communication_score=comm,
            problem_solving_score=prob,
            empathy_score=emp,
            compliance_score=comp,
            closing_score=clos,
        )
        db.add(analysis)

        # Embeddings
        try:
            chunks = chunk_transcript(transcript)
            embeddings = embed_chunks(chunks)
            for idx, (chunk, emb) in enumerate(zip(chunks, embeddings)):
                db.add(models.CallEmbedding(
                    call_id=call.id, company_id=company_id,
                    chunk_index=idx, chunk_text=chunk, embedding=emb,
                ))
        except Exception:
            pass  # embedding is optional

        # ── Dimension lookups ─────────────────────────────────────────────────
        now_date = datetime.now(timezone.utc).date()
        date_key = int(now_date.strftime("%Y%m%d"))

        agent_key = _ensure_dim_row(
            db, DimAgent, "agent_id", sc.agent_id, agent_name=sc.agent_name,
        )
        issue_key = _ensure_dim_row(
            db, DimIssue, "issue_category", issue, issue_group=_issue_group(issue),
        )
        sentiment_key = _ensure_dim_row(
            db, DimSentiment, "sentiment_label", sentiment,
        )
        resolution_key = _ensure_dim_row(
            db, DimResolution, "resolution_status", resolution,
        )
        source_key = _ensure_dim_row(
            db, DimCallSource, "source_label", "upload",
        )

        # Update dim_agent stats
        ag = db.query(DimAgent).filter(DimAgent.agent_id == sc.agent_id).first()
        if ag:
            ag.total_calls = (ag.total_calls or 0) + 1
            ag.last_seen = now_date
            if not ag.first_seen:
                ag.first_seen = now_date

        # ── Write FactCall ────────────────────────────────────────────────────
        fact = FactCall(
            silver_call_id=sc.id,
            contact_id=sc.contact_id,
            date_key=date_key,
            agent_key=agent_key,
            issue_key=issue_key,
            sentiment_key=sentiment_key,
            resolution_key=resolution_key,
            source_key=source_key,
            duration_minutes=sc.duration_minutes,
            quality_score=score,
            communication_score=comm,
            problem_solving_score=prob,
            empathy_score=emp,
            compliance_score=comp,
            closing_score=clos,
            agent_professionalism=result.get("agent_professionalism"),
            customer_frustration=result.get("customer_frustration"),
            word_count=sc.word_count,
            turn_count=sc.turn_count,
            has_ticket=sc.has_ticket,
            has_refund=sc.has_refund,
            has_escalation=sc.has_escalation,
            has_account_ref=sc.has_account_ref,
        )
        db.add(fact)
        processed += 1

        if processed % 5 == 0:
            print(f"[gold]  … {processed}/{len(pending)} calls evaluated")
            db.flush()

    db.commit()
    print(f"[gold] ✓ {processed} fact rows created")

    # ── Roll up aggregated facts ──────────────────────────────────────────────
    _rollup_agent_daily(db)
    _rollup_daily_summary(db)
    _rollup_issue_resolution(db)

    return {"processed": processed}


# ═══════════════════════════════════════════════════════════════════════════════
# 3. ROLLUP AGGREGATIONS
# ═══════════════════════════════════════════════════════════════════════════════

def _rollup_agent_daily(db: Session):
    """Rebuild fact_agent_daily from fact_calls."""
    db.query(FactAgentDaily).delete()

    rows = (
        db.query(
            FactCall.date_key,
            FactCall.agent_key,
            sqlfunc.count(FactCall.call_key).label("total"),
            sqlfunc.avg(FactCall.quality_score).label("avg_q"),
            sqlfunc.avg(FactCall.duration_minutes).label("avg_d"),
            sqlfunc.sum(case((FactCall.has_escalation == True, 1), else_=0)).label("esc"),
            sqlfunc.sum(case((FactCall.has_refund == True, 1), else_=0)).label("ref"),
        )
        .group_by(FactCall.date_key, FactCall.agent_key)
        .all()
    )

    # Need per-agent-day sentiment counts
    sent_rows = (
        db.query(
            FactCall.date_key,
            FactCall.agent_key,
            DimSentiment.sentiment_label,
            sqlfunc.count(FactCall.call_key),
        )
        .join(DimSentiment, FactCall.sentiment_key == DimSentiment.sentiment_key)
        .group_by(FactCall.date_key, FactCall.agent_key, DimSentiment.sentiment_label)
        .all()
    )
    sent_map = defaultdict(lambda: {"Positive": 0, "Negative": 0, "Neutral": 0})
    for dk, ak, label, cnt in sent_rows:
        sent_map[(dk, ak)][label] = cnt

    # Resolution counts
    res_rows = (
        db.query(
            FactCall.date_key,
            FactCall.agent_key,
            DimResolution.resolution_status,
            sqlfunc.count(FactCall.call_key),
        )
        .join(DimResolution, FactCall.resolution_key == DimResolution.resolution_key)
        .group_by(FactCall.date_key, FactCall.agent_key, DimResolution.resolution_status)
        .all()
    )
    res_map = defaultdict(int)
    for dk, ak, status, cnt in res_rows:
        if status == "Resolved":
            res_map[(dk, ak)] += cnt

    for dk, ak, total, avg_q, avg_d, esc, ref in rows:
        sm = sent_map[(dk, ak)]
        db.add(FactAgentDaily(
            date_key=dk,
            agent_key=ak,
            total_calls=total,
            avg_quality_score=round(float(avg_q or 0), 1),
            avg_duration=round(float(avg_d or 0), 1),
            positive_calls=sm["Positive"],
            negative_calls=sm["Negative"],
            neutral_calls=sm["Neutral"],
            resolved_calls=res_map.get((dk, ak), 0),
            escalated_calls=int(esc or 0),
            refund_calls=int(ref or 0),
        ))

    db.commit()
    print(f"[gold] ✓ fact_agent_daily rebuilt ({len(rows)} rows)")


def _rollup_daily_summary(db: Session):
    """Rebuild fact_daily_summary from fact_calls."""
    db.query(FactDailySummary).delete()

    rows = (
        db.query(
            FactCall.date_key,
            sqlfunc.count(FactCall.call_key).label("total"),
            sqlfunc.avg(FactCall.quality_score).label("avg_q"),
            sqlfunc.avg(FactCall.duration_minutes).label("avg_d"),
            sqlfunc.sum(case((FactCall.has_escalation == True, 1), else_=0)).label("esc"),
            sqlfunc.sum(case((FactCall.has_refund == True, 1), else_=0)).label("ref"),
        )
        .group_by(FactCall.date_key)
        .all()
    )

    # Sentiment per day
    sent_rows = (
        db.query(
            FactCall.date_key,
            DimSentiment.sentiment_label,
            sqlfunc.count(FactCall.call_key),
        )
        .join(DimSentiment, FactCall.sentiment_key == DimSentiment.sentiment_key)
        .group_by(FactCall.date_key, DimSentiment.sentiment_label)
        .all()
    )
    sent_map = defaultdict(lambda: {"Positive": 0, "Negative": 0, "Neutral": 0})
    for dk, label, cnt in sent_rows:
        sent_map[dk][label] = cnt

    # Top issue per day
    issue_rows = (
        db.query(
            FactCall.date_key,
            DimIssue.issue_category,
            sqlfunc.count(FactCall.call_key).label("cnt"),
        )
        .join(DimIssue, FactCall.issue_key == DimIssue.issue_key)
        .group_by(FactCall.date_key, DimIssue.issue_category)
        .order_by(sqlfunc.count(FactCall.call_key).desc())
        .all()
    )
    top_issue_map: dict[int, str] = {}
    for dk, cat, cnt in issue_rows:
        if dk not in top_issue_map:
            top_issue_map[dk] = cat

    # Unique agents per day
    agent_rows = (
        db.query(FactCall.date_key, sqlfunc.count(sqlfunc.distinct(FactCall.agent_key)))
        .group_by(FactCall.date_key)
        .all()
    )
    agent_map = {dk: cnt for dk, cnt in agent_rows}

    for dk, total, avg_q, avg_d, esc, ref in rows:
        sm = sent_map[dk]
        db.add(FactDailySummary(
            date_key=dk,
            total_calls=total,
            avg_quality_score=round(float(avg_q or 0), 1),
            avg_duration=round(float(avg_d or 0), 1),
            positive_calls=sm["Positive"],
            negative_calls=sm["Negative"],
            neutral_calls=sm["Neutral"],
            top_issue=top_issue_map.get(dk),
            unique_agents=agent_map.get(dk, 0),
            total_escalations=int(esc or 0),
            total_refunds=int(ref or 0),
        ))

    db.commit()
    print(f"[gold] ✓ fact_daily_summary rebuilt ({len(rows)} rows)")


def _rollup_issue_resolution(db: Session):
    """Rebuild fact_issue_resolution from fact_calls."""
    db.query(FactIssueResolution).delete()

    rows = (
        db.query(
            FactCall.date_key,
            FactCall.issue_key,
            sqlfunc.count(FactCall.call_key).label("total"),
            sqlfunc.avg(FactCall.quality_score).label("avg_q"),
            sqlfunc.avg(FactCall.duration_minutes).label("avg_d"),
        )
        .group_by(FactCall.date_key, FactCall.issue_key)
        .all()
    )

    # Resolved counts
    res_rows = (
        db.query(
            FactCall.date_key,
            FactCall.issue_key,
            sqlfunc.count(FactCall.call_key),
        )
        .join(DimResolution, FactCall.resolution_key == DimResolution.resolution_key)
        .filter(DimResolution.resolution_status == "Resolved")
        .group_by(FactCall.date_key, FactCall.issue_key)
        .all()
    )
    res_map = {(dk, ik): cnt for dk, ik, cnt in res_rows}

    for dk, ik, total, avg_q, avg_d in rows:
        db.add(FactIssueResolution(
            date_key=dk,
            issue_key=ik,
            total_calls=total,
            resolved_calls=res_map.get((dk, ik), 0),
            avg_resolution_time=round(float(avg_d or 0), 1),
            avg_quality_score=round(float(avg_q or 0), 1),
        ))

    db.commit()
    print(f"[gold] ✓ fact_issue_resolution rebuilt ({len(rows)} rows)")
