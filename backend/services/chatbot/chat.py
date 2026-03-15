from sqlalchemy.orm import Session

from .classifier import classify_query
from .rag_pipeline import run_rag_pipeline
from .llm_pipeline import run_llm_pipeline


def chat(question: str, db: Session, company_id: int) -> dict:
    """
    Main hybrid chatbot entry point.

    Flow:
        User Question → Query Classifier → RAG (support data from DB) | LLM (general)
    """

    intent = classify_query(question)

    if intent == "SUPPORT_DATA":
        result = run_rag_pipeline(question, db, company_id)
    else:
        result = run_llm_pipeline(question)

    return {
        "question": question,
        "intent": intent,
        "mode": result["mode"],
        "answer": result["answer"],
        "sources": result.get("sources", []),
    }
