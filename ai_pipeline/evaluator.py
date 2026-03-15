"""
ai_pipeline/evaluator.py

RAG + LLM evaluation pipeline for ReViewSense AI.

Pipeline:
  1. chunk_transcript()   — split text into overlapping chunks
  2. embed_chunks()       — generate sentence embeddings (local, no API)
  3. evaluate_call()      — send transcript to Groq LLM with structured prompt
                            returns 8-field JSON result
"""

import json
import os
import re
import textwrap
from pathlib import Path
from typing import Any

# Auto-load .env from backend/ or project root so the API key is always found
def _load_env():
    for candidate in [
        Path(__file__).parent.parent / "backend" / ".env",
        Path(__file__).parent.parent / ".env",
        Path(__file__).parent / ".env",
    ]:
        if candidate.exists():
            from dotenv import load_dotenv
            load_dotenv(candidate, override=True)   # override=True so server env gets the key
            print(f"[evaluator] Loaded .env from {candidate}")
            break

_load_env()
# Sanity check
if not os.getenv("GROQ_API_KEY"):
    print("[evaluator] WARNING: GROQ_API_KEY is not set — LLM will fall back to defaults")
else:
    print(f"[evaluator] GROQ_API_KEY loaded (starts with {os.getenv('GROQ_API_KEY','')[:8]}...)")

# ── Lazy imports (heavy libraries loaded once on first use) ───────────────────
_groq_client = None
_embedding_model = None


def _get_groq():
    global _groq_client
    if _groq_client is None:
        from groq import Groq
        api_key = os.getenv("GROQ_API_KEY", "")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY is not set in .env")
        _groq_client = Groq(api_key=api_key)
    return _groq_client


def _get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        from sentence_transformers import SentenceTransformer
        # Downloads ~90 MB on first run, then cached
        _embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
    return _embedding_model


# ─────────────────────────────────────────────────────────────────────────────
# 1.  CHUNKING
# ─────────────────────────────────────────────────────────────────────────────
def chunk_transcript(text: str, chunk_size: int = 400, overlap: int = 80) -> list[str]:
    """
    Split a transcript into overlapping character-level chunks.

    Args:
        text:       Full transcript string.
        chunk_size: Max characters per chunk (default 400).
        overlap:    Characters shared between consecutive chunks (default 80).

    Returns:
        List of chunk strings.
    """
    text = text.strip()
    if not text:
        return []

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        chunks.append(chunk)
        if end >= len(text):
            break
        start += chunk_size - overlap

    return chunks


# ─────────────────────────────────────────────────────────────────────────────
# 2.  EMBEDDING
# ─────────────────────────────────────────────────────────────────────────────
def embed_chunks(chunks: list[str]) -> list[list[float]]:
    """
    Generate sentence embeddings for each chunk.

    Uses the `all-MiniLM-L6-v2` model (384-dimensional vectors).
    Model is downloaded once on first call, then cached locally.

    Args:
        chunks: List of text chunks from chunk_transcript().

    Returns:
        List of embedding vectors (each is a list of 384 floats).
    """
    if not chunks:
        return []
    model = _get_embedding_model()
    embeddings = model.encode(chunks, convert_to_numpy=True)
    return [emb.tolist() for emb in embeddings]


# ─────────────────────────────────────────────────────────────────────────────
# 3.  LLM EVALUATION
# ─────────────────────────────────────────────────────────────────────────────
SYSTEM_PROMPT = textwrap.dedent("""
You are an expert AI call-center quality analyst.

Your task is to analyze a customer support conversation transcript and produce structured insights about:
• sentiment
• emotion
• issue type
• resolution status
• agent professionalism
• customer frustration
• overall quality score
• concise summary

The system is used in a multi-tenant SaaS call-analytics platform.
Each transcript represents a real customer support call between an agent and a customer.
Focus on understanding context, not just keywords.

You MUST return ONLY valid JSON with exactly these 8 fields and no other text:

{
  "sentiment": "Positive" | "Neutral" | "Negative",
  "emotion": "Calm" | "Frustrated" | "Angry" | "Confused" | "Satisfied" | "Concerned" | "Impatient" | "Disappointed",
  "issue_category": "Billing Issue" | "Technical Problem" | "Service Outage" | "Refund Request" | "Account Access" | "Product Inquiry" | "Other",
  "resolution_status": "Resolved" | "Partially Resolved" | "Not Resolved",
  "agent_professionalism": <integer 1-5>,
  "customer_frustration": <integer 1-5>,
  "quality_score": <integer 0-100>,
  "summary": "<2-3 sentence summary>"
}

Quality score guidelines:
90-100 → Excellent support
70-89  → Good support
50-69  → Average support
30-49  → Poor support
0-29   → Very poor support
""").strip()


def evaluate_call(transcript: str) -> dict[str, Any]:
    """
    Send transcript to Groq LLM and return structured 8-field analysis.

    Args:
        transcript: Full call transcript text.

    Returns:
        Dict with keys:
            sentiment, emotion, issue_category, resolution_status,
            agent_professionalism, customer_frustration, quality_score, summary

    Raises:
        RuntimeError if Groq API fails or returns invalid JSON.
    """
    transcript = transcript.strip()
    if not transcript:
        return _fallback_result("No transcript provided.")

    # ── Fix 3: Smart chunking for large transcripts ───────────────────────────
    # Instead of blindly truncating at 4000 chars (which discards the end of the
    # call — often where resolution happens), chunk the transcript, embed all
    # chunks, rank by L2 norm (information density), and send the top chunks
    # up to 4000 chars total.
    MAX_LLM_CHARS = 4000

    if len(transcript) <= MAX_LLM_CHARS:
        # Short transcript — send as-is
        best_text = transcript
    else:
        # Split into 400-char overlapping chunks
        chunks = chunk_transcript(transcript, chunk_size=400, overlap=80)

        # Embed all chunks (uses local sentence-transformers, no API call)
        embeddings = embed_chunks(chunks)

        # Rank chunks by L2 norm of their embedding vector
        # Higher norm = more information-dense / semantically rich
        ranked = sorted(
            zip(chunks, embeddings),
            key=lambda x: sum(v * v for v in x[1]),
            reverse=True,
        )

        # Take highest-density chunks until we hit the char limit
        selected = []
        total_chars = 0
        for chunk_text, _ in ranked:
            if total_chars + len(chunk_text) > MAX_LLM_CHARS:
                break
            selected.append(chunk_text)
            total_chars += len(chunk_text)

        # Re-join in original order (by position in original transcript)
        chunk_positions = {c: i for i, (c, _) in enumerate(zip(chunks, embeddings))}
        selected.sort(key=lambda c: chunk_positions.get(c, 0))
        best_text = "\n---\n".join(selected)

    user_message = f"Analyze this customer support transcript:\n\n{best_text}"

    try:
        client = _get_groq()

        # Try primary model first, fall back to smaller model if unavailable
        for model in ["llama-3.3-70b-versatile", "llama3-8b-8192"]:
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system",  "content": SYSTEM_PROMPT},
                        {"role": "user",    "content": user_message},
                    ],
                    temperature=0.1,                   # Low temperature for consistent JSON
                    max_tokens=512,
                    response_format={"type": "json_object"},
                )
                break   # success — exit the retry loop
            except Exception as model_err:
                if "decommissioned" in str(model_err).lower() or "does not exist" in str(model_err).lower():
                    continue    # try next model
                raise           # other error — re-raise

        raw = response.choices[0].message.content.strip()

        # Parse JSON
        result = json.loads(raw)

        # Validate and normalise all 8 fields
        return _normalise(result)

    except json.JSONDecodeError as e:
        print(f"[evaluator] JSON parse error: {e}")
        return _fallback_result(f"JSON parse error: {e}")
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        print(f"[evaluator] Groq API error:\n{tb}")
        return _fallback_result(str(e))


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
_VALID_SENTIMENTS  = {"Positive", "Neutral", "Negative"}
_VALID_EMOTIONS    = {"Calm", "Frustrated", "Angry", "Confused", "Satisfied", "Concerned", "Impatient", "Disappointed"}
_VALID_ISSUES      = {"Billing Issue", "Technical Problem", "Service Outage", "Refund Request", "Account Access", "Product Inquiry", "Other"}
_VALID_RESOLUTIONS = {"Resolved", "Partially Resolved", "Not Resolved"}


def _normalise(data: dict) -> dict:
    """Validate fields and apply defaults for anything missing or invalid."""
    return {
        "sentiment":             data.get("sentiment", "Neutral")        if data.get("sentiment")             in _VALID_SENTIMENTS  else "Neutral",
        "emotion":               data.get("emotion", "Calm")             if data.get("emotion")               in _VALID_EMOTIONS    else "Calm",
        "issue_category":        data.get("issue_category", "Other")     if data.get("issue_category")        in _VALID_ISSUES      else "Other",
        "resolution_status":     data.get("resolution_status", "Not Resolved") if data.get("resolution_status") in _VALID_RESOLUTIONS else "Not Resolved",
        "agent_professionalism": max(1, min(5, int(data.get("agent_professionalism", 3) or 3))),
        "customer_frustration":  max(1, min(5, int(data.get("customer_frustration",  3) or 3))),
        "quality_score":         max(0, min(100, int(data.get("quality_score", 50) or 50))),
        "summary":               str(data.get("summary", "No summary available."))[:1000],
    }


def _fallback_result(reason: str) -> dict:
    """Return neutral defaults when LLM evaluation fails."""
    return {
        "sentiment":             "Neutral",
        "emotion":               "Calm",
        "issue_category":        "Other",
        "resolution_status":     "Not Resolved",
        "agent_professionalism": 3,
        "customer_frustration":  3,
        "quality_score":         50,
        "summary":               f"Analysis unavailable: {reason}",
    }


# ─────────────────────────────────────────────────────────────────────────────
# 4.  FULL EVALUATION (with score breakdown for live analyzer)
# ─────────────────────────────────────────────────────────────────────────────
FULL_SYSTEM_PROMPT = textwrap.dedent("""
You are an expert AI call-center quality analyst.

Analyze the customer support conversation transcript and produce a detailed
structured analysis. Return ONLY valid JSON with exactly these fields:

{
  "sentiment": "Positive" | "Neutral" | "Negative",
  "emotion": "Calm" | "Frustrated" | "Angry" | "Confused" | "Satisfied" | "Concerned" | "Impatient" | "Disappointed",
  "issue_category": "Billing Issue" | "Technical Problem" | "Service Outage" | "Refund Request" | "Account Access" | "Product Inquiry" | "Other",
  "resolution_status": "Resolved" | "Partially Resolved" | "Not Resolved",
  "agent_professionalism": <integer 1-5>,
  "customer_frustration": <integer 1-5>,
  "quality_score": <integer 0-100>,
  "communication_score": <integer 0-30>,
  "problem_solving_score": <integer 0-25>,
  "empathy_score": <integer 0-20>,
  "compliance_score": <integer 0-15>,
  "closing_score": <integer 0-10>,
  "summary": "<2-3 sentence summary>",
  "tags": ["tag1", "tag2", ...]
}

Score breakdown guidelines:
- communication_score (0-30): Clarity, active listening, professional language
- problem_solving_score (0-25): Effectiveness of resolution, technical competence
- empathy_score (0-20): Understanding customer emotions, showing care
- compliance_score (0-15): Following protocol, proper verification
- closing_score (0-10): Proper wrap-up, confirming satisfaction
- quality_score should equal the sum of the 5 sub-scores

Tags: provide 3-6 short lowercase tags describing the call topics/issues.
""").strip()


def evaluate_call_full(transcript: str) -> dict[str, Any]:
    """
    Full evaluation with score breakdown. Used when call analysis is done
    directly in the backend (fallback when n8n is unavailable).
    """
    transcript = transcript.strip()
    if not transcript:
        return _fallback_full("No transcript provided.")

    MAX_LLM_CHARS = 4000
    if len(transcript) <= MAX_LLM_CHARS:
        best_text = transcript
    else:
        chunks = chunk_transcript(transcript, chunk_size=400, overlap=80)
        embeddings = embed_chunks(chunks)
        ranked = sorted(
            zip(chunks, embeddings),
            key=lambda x: sum(v * v for v in x[1]),
            reverse=True,
        )
        selected, total_chars = [], 0
        for chunk_text, _ in ranked:
            if total_chars + len(chunk_text) > MAX_LLM_CHARS:
                break
            selected.append(chunk_text)
            total_chars += len(chunk_text)
        chunk_positions = {c: i for i, (c, _) in enumerate(zip(chunks, embeddings))}
        selected.sort(key=lambda c: chunk_positions.get(c, 0))
        best_text = "\n---\n".join(selected)

    user_message = f"Analyze this customer support transcript:\n\n{best_text}"

    try:
        client = _get_groq()
        for model in ["llama-3.3-70b-versatile", "llama3-8b-8192"]:
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": FULL_SYSTEM_PROMPT},
                        {"role": "user", "content": user_message},
                    ],
                    temperature=0.1,
                    max_tokens=600,
                    response_format={"type": "json_object"},
                )
                break
            except Exception as model_err:
                if "decommissioned" in str(model_err).lower() or "does not exist" in str(model_err).lower():
                    continue
                raise

        raw = response.choices[0].message.content.strip()
        result = json.loads(raw)
        return _normalise_full(result)

    except json.JSONDecodeError as e:
        print(f"[evaluator] Full eval JSON parse error: {e}")
        return _fallback_full(f"JSON parse error: {e}")
    except Exception as e:
        import traceback
        print(f"[evaluator] Full eval error:\n{traceback.format_exc()}")
        return _fallback_full(str(e))


def _normalise_full(data: dict) -> dict:
    """Validate and normalise full evaluation result."""
    base = _normalise(data)
    base["communication_score"] = max(0, min(30, int(data.get("communication_score", 15) or 15)))
    base["problem_solving_score"] = max(0, min(25, int(data.get("problem_solving_score", 12) or 12)))
    base["empathy_score"] = max(0, min(20, int(data.get("empathy_score", 10) or 10)))
    base["compliance_score"] = max(0, min(15, int(data.get("compliance_score", 8) or 8)))
    base["closing_score"] = max(0, min(10, int(data.get("closing_score", 5) or 5)))
    base["tags"] = [str(t)[:100] for t in data.get("tags", [])][:10]
    # Recalculate quality_score as sum of sub-scores
    base["quality_score"] = min(100, base["communication_score"] + base["problem_solving_score"] + base["empathy_score"] + base["compliance_score"] + base["closing_score"])
    return base


def _fallback_full(reason: str) -> dict:
    """Return defaults for full evaluation when LLM fails."""
    base = _fallback_result(reason)
    base["communication_score"] = 15
    base["problem_solving_score"] = 12
    base["empathy_score"] = 10
    base["compliance_score"] = 8
    base["closing_score"] = 5
    base["tags"] = []
    return base
