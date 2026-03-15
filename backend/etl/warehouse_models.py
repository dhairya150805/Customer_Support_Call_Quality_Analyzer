"""
Warehouse Models — Bronze / Silver / Gold layer tables.

Star-schema design:
  BRONZE  → raw JSON ingestion (1:1 with source file)
  SILVER  → cleaned, validated, normalised records
  GOLD    → dimension + fact tables for analytics
"""

from sqlalchemy import (
    Column, Integer, String, Text, Float, DateTime, Boolean,
    ForeignKey, JSON, Date, SmallInteger, UniqueConstraint,
)
from sqlalchemy.sql import func
from database import Base


# ═══════════════════════════════════════════════════════════════════════════════
# BRONZE LAYER  — raw ingestion, no transformation
# ═══════════════════════════════════════════════════════════════════════════════

class BronzeRawCall(Base):
    """Exact copy of each JSON call record with ingestion metadata."""
    __tablename__ = "bronze_raw_calls"

    id            = Column(Integer, primary_key=True, index=True)
    batch_id      = Column(String(100), nullable=False, index=True)     # UUID per file load
    source_file   = Column(String(500), nullable=False)                 # original filename
    record_index  = Column(Integer, nullable=False)                     # position in array
    raw_json      = Column(JSON, nullable=False)                        # full record as-is
    contact_id    = Column(String(100), nullable=True, index=True)
    agent_id      = Column(String(100), nullable=True, index=True)
    ingested_at   = Column(DateTime(timezone=True), server_default=func.now())
    is_processed  = Column(Boolean, default=False, index=True)          # Silver picked it up?


# ═══════════════════════════════════════════════════════════════════════════════
# SILVER LAYER  — cleaned, validated, normalised
# ═══════════════════════════════════════════════════════════════════════════════

class SilverCall(Base):
    """Cleaned & validated call record."""
    __tablename__ = "silver_calls"

    id                = Column(Integer, primary_key=True, index=True)
    bronze_id         = Column(Integer, ForeignKey("bronze_raw_calls.id"), nullable=False, index=True)
    batch_id          = Column(String(100), nullable=False, index=True)
    contact_id        = Column(String(100), nullable=False, index=True)
    agent_id          = Column(String(100), nullable=False, index=True)
    agent_name        = Column(String(200), nullable=False)
    duration_minutes  = Column(Float, nullable=True)
    transcript_clean  = Column(Text, nullable=True)                     # whitespace-normalised
    word_count        = Column(Integer, nullable=True)
    turn_count        = Column(Integer, nullable=True)                  # agent+customer turns
    has_ticket        = Column(Boolean, default=False)
    ticket_ids        = Column(JSON, nullable=True)                     # ["TKT-8834"]
    has_account_ref   = Column(Boolean, default=False)
    account_ids       = Column(JSON, nullable=True)                     # ["ACC-4821"]
    has_refund        = Column(Boolean, default=False)
    has_escalation    = Column(Boolean, default=False)
    cleaned_at        = Column(DateTime(timezone=True), server_default=func.now())


class SilverAgent(Base):
    """Deduplicated agent directory from all ingested calls."""
    __tablename__ = "silver_agents"

    id          = Column(Integer, primary_key=True, index=True)
    agent_id    = Column(String(100), unique=True, nullable=False, index=True)
    agent_name  = Column(String(200), nullable=False)
    call_count  = Column(Integer, default=0)
    first_seen  = Column(DateTime(timezone=True), server_default=func.now())
    last_seen   = Column(DateTime(timezone=True), server_default=func.now())


class SilverInteraction(Base):
    """Individual conversation turns parsed from transcripts."""
    __tablename__ = "silver_interactions"

    id              = Column(Integer, primary_key=True, index=True)
    silver_call_id  = Column(Integer, ForeignKey("silver_calls.id", ondelete="CASCADE"), nullable=False, index=True)
    turn_number     = Column(Integer, nullable=False)
    speaker         = Column(String(20), nullable=False)                # "Agent" / "Customer"
    text            = Column(Text, nullable=False)
    word_count      = Column(Integer, nullable=True)


class SilverExtractedEntity(Base):
    """Tickets, account IDs, emails, amounts extracted from conversation."""
    __tablename__ = "silver_extracted_entities"

    id              = Column(Integer, primary_key=True, index=True)
    silver_call_id  = Column(Integer, ForeignKey("silver_calls.id", ondelete="CASCADE"), nullable=False, index=True)
    entity_type     = Column(String(50), nullable=False, index=True)    # ticket / account / email / amount / error_code
    entity_value    = Column(String(300), nullable=False)


# ═══════════════════════════════════════════════════════════════════════════════
# GOLD LAYER  — Star-schema dimensions & facts
# ═══════════════════════════════════════════════════════════════════════════════

# ── DIMENSIONS ────────────────────────────────────────────────────────────────

class DimDate(Base):
    """Date dimension for time-based analysis."""
    __tablename__ = "dim_date"

    date_key     = Column(Integer, primary_key=True)                    # YYYYMMDD
    full_date    = Column(Date, unique=True, nullable=False)
    year         = Column(SmallInteger, nullable=False)
    quarter      = Column(SmallInteger, nullable=False)                 # 1-4
    month        = Column(SmallInteger, nullable=False)                 # 1-12
    month_name   = Column(String(20), nullable=False)                   # "January"
    day          = Column(SmallInteger, nullable=False)                 # 1-31
    day_of_week  = Column(SmallInteger, nullable=False)                 # 0=Mon 6=Sun
    day_name     = Column(String(20), nullable=False)                   # "Monday"
    week_of_year = Column(SmallInteger, nullable=False)
    is_weekend   = Column(Boolean, nullable=False)


class DimAgent(Base):
    """Agent dimension."""
    __tablename__ = "dim_agent"

    agent_key   = Column(Integer, primary_key=True, autoincrement=True)
    agent_id    = Column(String(100), unique=True, nullable=False, index=True)
    agent_name  = Column(String(200), nullable=False)
    total_calls = Column(Integer, default=0)
    first_seen  = Column(Date, nullable=True)
    last_seen   = Column(Date, nullable=True)


class DimIssue(Base):
    """Issue/topic dimension."""
    __tablename__ = "dim_issue"

    issue_key       = Column(Integer, primary_key=True, autoincrement=True)
    issue_category  = Column(String(100), unique=True, nullable=False, index=True)
    issue_group     = Column(String(100), nullable=True)                # billing / technical / account / general


class DimSentiment(Base):
    """Sentiment dimension."""
    __tablename__ = "dim_sentiment"

    sentiment_key   = Column(Integer, primary_key=True, autoincrement=True)
    sentiment_label = Column(String(20), unique=True, nullable=False)   # Positive / Negative / Neutral


class DimResolution(Base):
    """Resolution status dimension."""
    __tablename__ = "dim_resolution"

    resolution_key    = Column(Integer, primary_key=True, autoincrement=True)
    resolution_status = Column(String(50), unique=True, nullable=False) # Resolved / Partially / Not Resolved / Pending


class DimCallSource(Base):
    """Call source/channel dimension."""
    __tablename__ = "dim_call_source"

    source_key   = Column(Integer, primary_key=True, autoincrement=True)
    source_label = Column(String(50), unique=True, nullable=False)      # upload / live / ai_agent / manual


# ── FACT TABLES ───────────────────────────────────────────────────────────────

class FactCall(Base):
    """Grain: one row per call. Central fact table."""
    __tablename__ = "fact_calls"

    call_key            = Column(Integer, primary_key=True, autoincrement=True)
    silver_call_id      = Column(Integer, ForeignKey("silver_calls.id"), nullable=False, unique=True, index=True)
    contact_id          = Column(String(100), nullable=True, index=True)

    # ── Dimension FKs ────────────────────────────────────────────────────────
    date_key            = Column(Integer, ForeignKey("dim_date.date_key"), nullable=True, index=True)
    agent_key           = Column(Integer, ForeignKey("dim_agent.agent_key"), nullable=True, index=True)
    issue_key           = Column(Integer, ForeignKey("dim_issue.issue_key"), nullable=True, index=True)
    sentiment_key       = Column(Integer, ForeignKey("dim_sentiment.sentiment_key"), nullable=True, index=True)
    resolution_key      = Column(Integer, ForeignKey("dim_resolution.resolution_key"), nullable=True, index=True)
    source_key          = Column(Integer, ForeignKey("dim_call_source.source_key"), nullable=True, index=True)

    # ── Measures ──────────────────────────────────────────────────────────────
    duration_minutes    = Column(Float, nullable=True)
    quality_score       = Column(Integer, nullable=True)                # 0-100
    communication_score = Column(Integer, nullable=True)                # 0-30
    problem_solving_score = Column(Integer, nullable=True)              # 0-25
    empathy_score       = Column(Integer, nullable=True)                # 0-20
    compliance_score    = Column(Integer, nullable=True)                # 0-15
    closing_score       = Column(Integer, nullable=True)                # 0-10
    agent_professionalism = Column(Integer, nullable=True)              # 1-5
    customer_frustration  = Column(Integer, nullable=True)              # 1-5
    word_count          = Column(Integer, nullable=True)
    turn_count          = Column(Integer, nullable=True)

    # ── Flags ──────────────────────────────────────────────────────────────────
    has_ticket          = Column(Boolean, default=False)
    has_refund          = Column(Boolean, default=False)
    has_escalation      = Column(Boolean, default=False)
    has_account_ref     = Column(Boolean, default=False)

    created_at          = Column(DateTime(timezone=True), server_default=func.now())


class FactAgentDaily(Base):
    """Grain: one row per agent per day. Pre-aggregated agent performance."""
    __tablename__ = "fact_agent_daily"

    id                = Column(Integer, primary_key=True, autoincrement=True)
    date_key          = Column(Integer, ForeignKey("dim_date.date_key"), nullable=False, index=True)
    agent_key         = Column(Integer, ForeignKey("dim_agent.agent_key"), nullable=False, index=True)
    total_calls       = Column(Integer, default=0)
    avg_quality_score = Column(Float, nullable=True)
    avg_duration      = Column(Float, nullable=True)
    positive_calls    = Column(Integer, default=0)
    negative_calls    = Column(Integer, default=0)
    neutral_calls     = Column(Integer, default=0)
    resolved_calls    = Column(Integer, default=0)
    escalated_calls   = Column(Integer, default=0)
    refund_calls      = Column(Integer, default=0)

    __table_args__ = (
        UniqueConstraint("date_key", "agent_key", name="uq_agent_daily"),
    )


class FactDailySummary(Base):
    """Grain: one row per day. Organisation-level daily rollup."""
    __tablename__ = "fact_daily_summary"

    id                = Column(Integer, primary_key=True, autoincrement=True)
    date_key          = Column(Integer, ForeignKey("dim_date.date_key"), nullable=False, unique=True, index=True)
    total_calls       = Column(Integer, default=0)
    avg_quality_score = Column(Float, nullable=True)
    avg_duration      = Column(Float, nullable=True)
    positive_calls    = Column(Integer, default=0)
    negative_calls    = Column(Integer, default=0)
    neutral_calls     = Column(Integer, default=0)
    top_issue         = Column(String(100), nullable=True)
    unique_agents     = Column(Integer, default=0)
    total_escalations = Column(Integer, default=0)
    total_refunds     = Column(Integer, default=0)


class FactIssueResolution(Base):
    """Grain: one row per issue category per day."""
    __tablename__ = "fact_issue_resolution"

    id                = Column(Integer, primary_key=True, autoincrement=True)
    date_key          = Column(Integer, ForeignKey("dim_date.date_key"), nullable=False, index=True)
    issue_key         = Column(Integer, ForeignKey("dim_issue.issue_key"), nullable=False, index=True)
    total_calls       = Column(Integer, default=0)
    resolved_calls    = Column(Integer, default=0)
    avg_resolution_time = Column(Float, nullable=True)
    avg_quality_score = Column(Float, nullable=True)

    __table_args__ = (
        UniqueConstraint("date_key", "issue_key", name="uq_issue_daily"),
    )
