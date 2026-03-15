import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from google import genai
from dotenv import load_dotenv
from vector_store import search_documents

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
MODEL = "gemini-2.5-flash"

RAG_PROMPT = """
You are a smart customer support analytics assistant for KenexAI.

You have been given relevant data retrieved from the support complaint database.
Use this data to answer the user's question accurately and concisely.

--- Retrieved Support Data ---
{context}
--- End of Retrieved Data ---

User Question: {question}

Answer based on the retrieved data above. Be specific and use numbers/facts from the data.
If the data doesn't directly answer the question, say so and provide what insight you can.
"""


def run_rag_pipeline(question: str) -> dict:
    """
    Full RAG pipeline:
    1. Embed the question
    2. Search the vector store for relevant transcripts/complaints
    3. Feed context + question to LLM
    4. Return the answer with source context
    """

    # Step 1 & 2 — Search vector store
    hits = search_documents(query=question, n_results=5)

    if not hits:
        return {
            "answer": (
                "I searched the support database but found no relevant records. "
                "Please seed the vector store with call data first."
            ),
            "mode": "RAG",
            "sources": [],
        }

    # Step 3 — Build context from retrieved documents
    context_parts = []
    sources = []
    for i, hit in enumerate(hits, 1):
        meta = hit.get("metadata", {})
        context_parts.append(
            f"[Record {i}]\n"
            f"Issue: {meta.get('issue', 'N/A')} | "
            f"Sentiment: {meta.get('sentiment', 'N/A')} | "
            f"Agent: {meta.get('agent_id', 'N/A')} | "
            f"Score: {meta.get('quality_score', 'N/A')}\n"
            f"Summary: {hit['text']}"
        )
        sources.append(meta)

    context = "\n\n".join(context_parts)

    # Step 4 — LLM answer with context
    prompt = RAG_PROMPT.format(context=context, question=question)
    response = client.models.generate_content(model=MODEL, contents=prompt)

    return {
        "answer": response.text.strip(),
        "mode": "RAG",
        "sources": sources,
    }
