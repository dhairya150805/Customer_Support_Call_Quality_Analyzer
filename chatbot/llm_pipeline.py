import os
from google import genai
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
MODEL = "gemini-2.5-flash"

GENERAL_PROMPT = """
You are a helpful AI assistant. Answer the following question clearly and concisely
using your general knowledge.

Question: {question}
"""


def run_llm_pipeline(question: str) -> dict:
    """
    Direct LLM answer — no RAG, no database lookup.
    Used for general knowledge questions unrelated to support data.
    """
    prompt = GENERAL_PROMPT.format(question=question)
    response = client.models.generate_content(model=MODEL, contents=prompt)

    return {
        "answer": response.text.strip(),
        "mode": "LLM",
        "sources": [],
    }
