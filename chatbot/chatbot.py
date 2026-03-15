from classifier import classify_query
from rag_pipeline import run_rag_pipeline
from llm_pipeline import run_llm_pipeline


def chat(question: str) -> dict:
    """
    Main hybrid chatbot entry point.

    Flow:
        User Question
              ↓
        Query Classifier
              ↓
      SUPPORT_DATA?  ──────────────── GENERAL?
           ↓                               ↓
      RAG Pipeline                   LLM Pipeline
      (Vector DB search)             (Direct Gemini)
           ↓                               ↓
     Answer from data              Normal AI answer
    """

    # Step 1 — Classify the question
    intent = classify_query(question)

    # Step 2 — Route to the correct pipeline
    if intent == "SUPPORT_DATA":
        result = run_rag_pipeline(question)
    else:
        result = run_llm_pipeline(question)

    # Step 3 — Return unified response
    return {
        "question": question,
        "intent": intent,
        "mode": result["mode"],          # "RAG" or "LLM"
        "answer": result["answer"],
        "sources": result.get("sources", []),
    }
