from sqlalchemy import (
    Column, Integer, String, Text, Float, DateTime, Boolean,
    ForeignKey, JSON, Enum as SAEnum,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base
import enum


# ── Enums ─────────────────────────────────────────────────────────────────────
class CallSource(str, enum.Enum):
    upload   = "upload"
    live     = "live"
    ai_agent = "ai_agent"
    manual   = "manual"


class SessionStatus(str, enum.Enum):
    active    = "active"
    analyzing = "analyzing"
    complete  = "complete"
    failed    = "failed"


# ── Companies ─────────────────────────────────────────────────────────────────
class Company(Base):
    __tablename__ = "companies"

    id         = Column(Integer, primary_key=True, index=True)
    name       = Column(String(200), nullable=False)
    email      = Column(String(200), unique=True, nullable=False, index=True)
    plan_type  = Column(String(50), default="free")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    users        = relationship("User",                     back_populates="company", cascade="all, delete")
    calls        = relationship("Call",                     back_populates="company", cascade="all, delete")
    agents       = relationship("Agent",                    back_populates="company", cascade="all, delete")
    live_sessions = relationship("LiveSession",             back_populates="company", cascade="all, delete")


# ── Users ─────────────────────────────────────────────────────────────────────
class User(Base):
    __tablename__ = "users"

    id            = Column(Integer, primary_key=True, index=True)
    company_id    = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    email         = Column(String(200), unique=True, nullable=False, index=True)
    password_hash = Column(String(300), nullable=False)
    role          = Column(String(50), default="company_owner")
    created_at    = Column(DateTime(timezone=True), server_default=func.now())

    company = relationship("Company", back_populates="users")


# ── Agents (normalized) ──────────────────────────────────────────────────────
class Agent(Base):
    __tablename__ = "agents"

    id          = Column(Integer, primary_key=True, index=True)
    company_id  = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_code  = Column(String(100), nullable=False, index=True)       # e.g. AG-001
    name        = Column(String(200), nullable=False)
    email       = Column(String(200), nullable=True)
    department  = Column(String(100), nullable=True)
    shift       = Column(String(50),  nullable=True)                    # morning / afternoon / night
    is_active   = Column(Boolean, default=True)
    joined_at   = Column(DateTime(timezone=True), server_default=func.now())

    company = relationship("Company", back_populates="agents")
    calls   = relationship("Call",    back_populates="agent_ref", foreign_keys="Call.agent_ref_id")


# ── Calls ─────────────────────────────────────────────────────────────────────
class Call(Base):
    __tablename__ = "calls"

    id            = Column(Integer, primary_key=True, index=True)
    company_id    = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    contact_id    = Column(String(100), index=True)
    agent_id      = Column(String(100), default="unknown")
    agent_name    = Column(String(200), default="Unknown Agent")
    agent_ref_id  = Column(Integer, ForeignKey("agents.id", ondelete="SET NULL"), nullable=True, index=True)
    conversation  = Column(Text, nullable=True)
    duration      = Column(Float, nullable=True)                         # minutes
    source        = Column(String(20), default="upload")                 # upload / live / ai_agent / manual
    call_type     = Column(String(50), default="inbound")                # inbound / outbound / internal
    phone_number  = Column(String(30), nullable=True)
    status        = Column(String(20), default="complete")               # active / analyzing / complete
    uploaded_at   = Column(DateTime(timezone=True), server_default=func.now())

    company    = relationship("Company", back_populates="calls")
    agent_ref  = relationship("Agent",   back_populates="calls", foreign_keys=[agent_ref_id])
    analysis   = relationship("CallAnalysis",  back_populates="call", uselist=False, cascade="all, delete")
    embeddings = relationship("CallEmbedding", back_populates="call", cascade="all, delete")
    tags       = relationship("CallTag",       back_populates="call", cascade="all, delete")


# ── Call Analysis (LLM results) ──────────────────────────────────────────────
class CallAnalysis(Base):
    __tablename__ = "call_analysis"

    id                    = Column(Integer, primary_key=True, index=True)
    call_id               = Column(Integer, ForeignKey("calls.id", ondelete="CASCADE"), nullable=False, unique=True)
    company_id            = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)

    # ── Core fields ──────────────────────────────────────────────────────────
    sentiment             = Column(String(20),  default="Neutral")
    summary               = Column(Text,        nullable=True)
    issue                 = Column(String(100), default="General Inquiry")
    score                 = Column(Integer,     default=0)               # 0–100
    created_at            = Column(DateTime(timezone=True), server_default=func.now())

    # ── Extended LLM fields ──────────────────────────────────────────────────
    emotion               = Column(String(50),  nullable=True)           # Calm / Frustrated / Angry …
    resolution_status     = Column(String(50),  nullable=True)           # Resolved / Partially / Not Resolved
    agent_professionalism = Column(Integer,      nullable=True)          # 1–5
    customer_frustration  = Column(Integer,      nullable=True)          # 1–5

    # ── New scoring breakdown ────────────────────────────────────────────────
    communication_score   = Column(Integer, nullable=True)               # 0–30
    problem_solving_score = Column(Integer, nullable=True)               # 0–25
    empathy_score         = Column(Integer, nullable=True)               # 0–20
    compliance_score      = Column(Integer, nullable=True)               # 0–15
    closing_score         = Column(Integer, nullable=True)               # 0–10

    call = relationship("Call", back_populates="analysis")


# ── Call Tags ─────────────────────────────────────────────────────────────────
class CallTag(Base):
    __tablename__ = "call_tags"

    id      = Column(Integer, primary_key=True, index=True)
    call_id = Column(Integer, ForeignKey("calls.id", ondelete="CASCADE"), nullable=False, index=True)
    tag     = Column(String(100), nullable=False, index=True)

    call = relationship("Call", back_populates="tags")


# ── Call Embeddings (RAG) ────────────────────────────────────────────────────
class CallEmbedding(Base):
    """Stores chunked transcript embeddings for RAG retrieval."""
    __tablename__ = "call_embeddings"

    id          = Column(Integer, primary_key=True, index=True)
    call_id     = Column(Integer, ForeignKey("calls.id", ondelete="CASCADE"), nullable=False, index=True)
    company_id  = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)
    chunk_text  = Column(Text,    nullable=False)
    embedding   = Column(JSON,    nullable=True)   # list[float] from sentence-transformers

    call = relationship("Call", back_populates="embeddings")


# ── Live Sessions (AI Calling Agent) ─────────────────────────────────────────
class LiveSession(Base):
    """Tracks real-time AI agent calling sessions stored directly in DB."""
    __tablename__ = "live_sessions"

    id           = Column(Integer, primary_key=True, index=True)
    company_id   = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    call_id      = Column(Integer, ForeignKey("calls.id", ondelete="SET NULL"), nullable=True, index=True)
    agent_id     = Column(String(100), nullable=True)
    agent_name   = Column(String(200), nullable=True)
    contact_id   = Column(String(100), nullable=True)
    phone_number = Column(String(30),  nullable=True)
    status       = Column(String(20),  default="active")                # active / analyzing / complete / failed
    language     = Column(String(20),  default="en")                     # detected language code
    started_at   = Column(DateTime(timezone=True), server_default=func.now())
    ended_at     = Column(DateTime(timezone=True), nullable=True)
    duration_sec = Column(Integer, nullable=True)

    company  = relationship("Company", back_populates="live_sessions")
    call     = relationship("Call")
    messages = relationship("LiveMessage", back_populates="session", cascade="all, delete",
                            order_by="LiveMessage.seq")


# ── Live Messages (individual turns in a live session) ────────────────────────
class LiveMessage(Base):
    """Each message/turn in a live AI agent conversation."""
    __tablename__ = "live_messages"

    id         = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("live_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    seq        = Column(Integer, nullable=False)                         # message order 1, 2, 3…
    speaker    = Column(String(20), nullable=False)                      # "agent" / "customer" / "system"
    text       = Column(Text, nullable=False)
    timestamp  = Column(DateTime(timezone=True), server_default=func.now())

    session = relationship("LiveSession", back_populates="messages")


# ── Evaluation Framework ─────────────────────────────────────────────────────
class EvaluationFrameworkModel(Base):
    """Per-company evaluation framework config."""
    __tablename__ = "evaluation_frameworks"

    id         = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    config     = Column(JSON, nullable=False)


# ── Audit Log ─────────────────────────────────────────────────────────────────
class AuditLog(Base):
    """Tracks key actions for compliance and debugging."""
    __tablename__ = "audit_log"

    id         = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id    = Column(Integer, nullable=True)
    action     = Column(String(100), nullable=False)                     # upload_calls, analyze, login, etc.
    detail     = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
