"""
Vector store — searches the PostgreSQL CallEmbedding table
using the same sentence-transformers model (all-MiniLM-L6-v2)
that was used to create the embeddings at upload time.
"""

import numpy as np
from sqlalchemy.orm import Session

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
import models

# ─── Lazy-loaded embedding model (cached after first call) ──────────────────
_embedding_model = None


def _get_model():
    global _embedding_model
    if _embedding_model is None:
        from sentence_transformers import SentenceTransformer
        _embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
    return _embedding_model


def embed_query(text: str) -> np.ndarray:
    """Embed a single query string into a 384-dim vector."""
    model = _get_model()
    return model.encode(text, normalize_embeddings=True)


def search_embeddings(
    query: str,
    db: Session,
    company_id: int,
    top_k: int = 8,
) -> list[dict]:
    """
    Cosine-similarity search over CallEmbedding rows in PostgreSQL.

    1. Embed the query with all-MiniLM-L6-v2
    2. Fetch all embeddings for the company
    3. Compute cosine similarity with numpy
    4. Return top-k results with chunk text + metadata from Call/CallAnalysis
    """
    query_vec = embed_query(query)

    # Fetch embeddings for this company (with joined call + analysis)
    rows = (
        db.query(
            models.CallEmbedding.id,
            models.CallEmbedding.call_id,
            models.CallEmbedding.chunk_text,
            models.CallEmbedding.embedding,
            models.Call.agent_id,
            models.Call.agent_name,
            models.Call.contact_id,
            models.Call.uploaded_at,
            models.CallAnalysis.sentiment,
            models.CallAnalysis.issue,
            models.CallAnalysis.score,
            models.CallAnalysis.summary,
            models.CallAnalysis.emotion,
            models.CallAnalysis.resolution_status,
        )
        .join(models.Call, models.Call.id == models.CallEmbedding.call_id)
        .outerjoin(models.CallAnalysis, models.CallAnalysis.call_id == models.Call.id)
        .filter(models.CallEmbedding.company_id == company_id)
        .filter(models.CallEmbedding.embedding.isnot(None))
        .all()
    )

    if not rows:
        return []

    # Build matrix and compute cosine similarity
    embeddings = []
    valid_rows = []
    for r in rows:
        emb = r.embedding
        if emb and isinstance(emb, list) and len(emb) > 0:
            embeddings.append(emb)
            valid_rows.append(r)

    if not valid_rows:
        return []

    matrix = np.array(embeddings, dtype=np.float32)
    # Normalize for cosine similarity
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1
    matrix = matrix / norms
    query_norm = query_vec / (np.linalg.norm(query_vec) + 1e-9)

    similarities = matrix @ query_norm

    # Get top-k indices
    k = min(top_k, len(valid_rows))
    top_indices = np.argsort(similarities)[::-1][:k]

    hits = []
    for idx in top_indices:
        r = valid_rows[idx]
        hits.append({
            "text": r.chunk_text,
            "similarity": float(similarities[idx]),
            "metadata": {
                "call_id": r.call_id,
                "agent_id": r.agent_id,
                "agent_name": r.agent_name,
                "contact_id": r.contact_id,
                "sentiment": r.sentiment,
                "issue": r.issue,
                "quality_score": r.score,
                "summary": r.summary,
                "emotion": r.emotion,
                "resolution_status": r.resolution_status,
                "uploaded_at": str(r.uploaded_at) if r.uploaded_at else None,
            },
        })

    return hits
