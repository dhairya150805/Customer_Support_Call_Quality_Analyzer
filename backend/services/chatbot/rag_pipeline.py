"""
RAG pipeline — retrieves data from PostgreSQL (vector search + structured
aggregates) and feeds it as grounded context to Gemini LLM.
"""

import os
from google import genai
from dotenv import load_dotenv
from sqlalchemy.orm import Session

from .vector_store import search_embeddings
from .db_retriever import get_structured_context

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
MODEL = "gemini-2.5-flash"

RAG_PROMPT = """
You are a strict data-grounded customer support analytics assistant for ReViewSense AI.

CRITICAL RULES:
1. Answer ONLY using the data provided below. Do NOT invent, assume, or hallucinate any information.
2. If the answer cannot be found in the retrieved data, respond with:
   "I cannot find this information in the available data."
3. Be specific — cite numbers, agent names, scores, and dates from the data.
4. If the data partially answers the question, state what you found and what is missing.
5. Never make up statistics, call records, or agent information that is not in the data.

--- DATABASE OVERVIEW ---
{structured_context}
--- END DATABASE OVERVIEW ---

--- RELEVANT CALL RECORDS (vector search results) ---
{vector_context}
--- END CALL RECORDS ---

User Question: {question}

Answer based strictly on the data above. If the data does not contain the answer, say so clearly.
"""


def run_rag_pipeline(question: str, db: Session, company_id: int) -> dict:
    """
    Full RAG pipeline backed by PostgreSQL:
    1. Retrieve structured aggregate data (metrics, agents, issues)
    2. Embed the query and search CallEmbedding for relevant transcript chunks
    3. Combine both contexts and send to LLM with anti-hallucination prompt
    """

    # Step 1 — Structured database aggregates
    structured_context = get_structured_context(db, company_id)

    # Step 2 — Vector similarity search over transcript embeddings
    hits = search_embeddings(query=question, db=db, company_id=company_id, top_k=8)

    vector_parts = []
    sources = []
    if hits:
        for i, hit in enumerate(hits, 1):
            meta = hit.get("metadata", {})
            vector_parts.append(
                f"[Record {i} | similarity={hit['similarity']:.3f}]\n"
                f"Call ID: {meta.get('call_id', 'N/A')} | "
                f"Agent: {meta.get('agent_name', 'N/A')} ({meta.get('agent_id', 'N/A')}) | "
                f"Issue: {meta.get('issue', 'N/A')} | "
                f"Sentiment: {meta.get('sentiment', 'N/A')} | "
                f"Score: {meta.get('quality_score', 'N/A')} | "
                f"Resolution: {meta.get('resolution_status', 'N/A')} | "
                f"Date: {meta.get('uploaded_at', 'N/A')}\n"
                f"Summary: {meta.get('summary', 'N/A')}\n"
                f"Transcript excerpt: {hit['text'][:500]}"
            )
            sources.append(meta)

    vector_context = "\n\n".join(vector_parts) if vector_parts else "No matching transcript chunks found."

    # Step 3 — LLM with grounded context
    prompt = RAG_PROMPT.format(
        structured_context=structured_context,
        vector_context=vector_context,
        question=question,
    )
    try:
        response = client.models.generate_content(model=MODEL, contents=prompt)
        answer = response.text.strip()
    except Exception as e:
        answer = (
            f"I found {len(sources)} relevant record(s) in the database but the AI model "
            f"is temporarily unavailable ({type(e).__name__}). "
            f"Here is a summary of the structured data:\n\n{structured_context}"
        )

    return {
        "answer": answer,
        "mode": "RAG",
        "sources": sources,
    }
