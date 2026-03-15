"""
db_retriever.py — Retrieves structured aggregate data from PostgreSQL
so the chatbot can answer questions about overall metrics, trends,
agent performance, sentiment breakdowns, and top issues.
"""

from sqlalchemy import func, case
from sqlalchemy.orm import Session

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
import models


def get_structured_context(db: Session, company_id: int) -> str:
    """
    Query the database for aggregate stats and return a formatted
    context string the LLM can use to answer data-driven questions.
    """
    parts = []

    # ── Total calls & date range ─────────────────────────────────────────────
    total_calls = (
        db.query(func.count(models.Call.id))
        .filter(models.Call.company_id == company_id)
        .scalar()
    ) or 0

    if total_calls == 0:
        return "No call data is available for this company yet."

    date_range = (
        db.query(
            func.min(models.Call.uploaded_at),
            func.max(models.Call.uploaded_at),
        )
        .filter(models.Call.company_id == company_id)
        .first()
    )
    parts.append(
        f"=== DATABASE SUMMARY ===\n"
        f"Total calls in database: {total_calls}\n"
        f"Date range: {date_range[0]} to {date_range[1]}"
    )

    # ── Average quality score ────────────────────────────────────────────────
    avg_score = (
        db.query(func.avg(models.CallAnalysis.score))
        .filter(models.CallAnalysis.company_id == company_id)
        .scalar()
    )
    if avg_score is not None:
        parts.append(f"Average quality score: {round(avg_score, 1)} / 100")

    # ── Sentiment breakdown ──────────────────────────────────────────────────
    sentiment_rows = (
        db.query(
            models.CallAnalysis.sentiment,
            func.count(models.CallAnalysis.id).label("cnt"),
        )
        .filter(models.CallAnalysis.company_id == company_id)
        .group_by(models.CallAnalysis.sentiment)
        .all()
    )
    if sentiment_rows:
        total_analyzed = sum(r.cnt for r in sentiment_rows)
        breakdown = ", ".join(
            f"{r.sentiment}: {r.cnt} ({round(r.cnt / total_analyzed * 100)}%)"
            for r in sentiment_rows
        )
        parts.append(f"Sentiment breakdown ({total_analyzed} analyzed): {breakdown}")

    # ── Top issues ───────────────────────────────────────────────────────────
    issue_rows = (
        db.query(
            models.CallAnalysis.issue,
            func.count(models.CallAnalysis.id).label("cnt"),
        )
        .filter(models.CallAnalysis.company_id == company_id)
        .group_by(models.CallAnalysis.issue)
        .order_by(func.count(models.CallAnalysis.id).desc())
        .limit(10)
        .all()
    )
    if issue_rows:
        issues_str = "\n".join(
            f"  - {r.issue}: {r.cnt} calls" for r in issue_rows
        )
        parts.append(f"Top issues:\n{issues_str}")

    # ── Agent performance ────────────────────────────────────────────────────
    agent_rows = (
        db.query(
            models.Call.agent_id,
            models.Call.agent_name,
            func.count(models.Call.id).label("calls"),
            func.avg(models.CallAnalysis.score).label("avg_score"),
            func.sum(case((models.CallAnalysis.sentiment == "Positive", 1), else_=0)).label("pos"),
            func.sum(case((models.CallAnalysis.sentiment == "Negative", 1), else_=0)).label("neg"),
        )
        .join(models.CallAnalysis, models.CallAnalysis.call_id == models.Call.id, isouter=True)
        .filter(models.Call.company_id == company_id)
        .group_by(models.Call.agent_id, models.Call.agent_name)
        .order_by(func.avg(models.CallAnalysis.score).desc())
        .limit(15)
        .all()
    )
    if agent_rows:
        agents_str = "\n".join(
            f"  - {r.agent_name} ({r.agent_id}): {r.calls} calls, "
            f"avg score {round(r.avg_score or 0)}, "
            f"{r.pos or 0} positive, {r.neg or 0} negative"
            for r in agent_rows
        )
        parts.append(f"Agent performance:\n{agents_str}")

    # ── Resolution status breakdown ──────────────────────────────────────────
    resolution_rows = (
        db.query(
            models.CallAnalysis.resolution_status,
            func.count(models.CallAnalysis.id).label("cnt"),
        )
        .filter(
            models.CallAnalysis.company_id == company_id,
            models.CallAnalysis.resolution_status.isnot(None),
        )
        .group_by(models.CallAnalysis.resolution_status)
        .all()
    )
    if resolution_rows:
        res_str = ", ".join(f"{r.resolution_status}: {r.cnt}" for r in resolution_rows)
        parts.append(f"Resolution status: {res_str}")

    return "\n\n".join(parts)
