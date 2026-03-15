import os
from google import genai
from dotenv import load_dotenv

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
MODEL = "gemini-2.5-flash"

GENERAL_PROMPT = """
You are a helpful AI assistant for ReViewSense AI, a customer support analytics platform.

Answer the following question clearly and concisely using your general knowledge.
IMPORTANT: If the question asks about specific customer data, call records, agent
performance, or any project-specific information, you must respond with:
"This question requires data from the support database. Please rephrase your question
about customer calls, agents, or support metrics so I can search the database for you."

Question: {question}
"""


def run_llm_pipeline(question: str) -> dict:
    """
    Direct LLM answer — no RAG, no database lookup.
    Used for general knowledge questions unrelated to support data.
    """
    prompt = GENERAL_PROMPT.format(question=question)
    try:
        response = client.models.generate_content(model=MODEL, contents=prompt)
        answer = response.text.strip()
    except Exception as e:
        answer = (
            f"The AI model is temporarily unavailable ({type(e).__name__}). "
            f"Please try again in a moment."
        )

    return {
        "answer": answer,
        "mode": "LLM",
        "sources": [],
    }
