"""
KenexAI — Hybrid Chatbot API
Run with:  uvicorn main:app --reload --port 8001
Seed data: python seed_data.py  (run once before starting)
"""

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from chatbot import chat
import os

app = FastAPI(
    title="KenexAI — Hybrid Chatbot",
    description=(
        "Hybrid AI chatbot: routes support/analytics questions through RAG "
        "(ChromaDB vector search), and general questions straight to Gemini LLM."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Request / Response Schemas ──────────────────────────────────────────────

class ChatRequest(BaseModel):
    question: str


class ChatResponse(BaseModel):
    question: str
    intent: str       # "SUPPORT_DATA" or "GENERAL"
    mode: str         # "RAG" or "LLM"
    answer: str
    sources: list     # retrieved docs metadata (empty for LLM mode)


# ─── Endpoints ───────────────────────────────────────────────────────────────

@app.post("/chat", response_model=ChatResponse)
def chat_endpoint(request: ChatRequest):
    """
    Hybrid chatbot endpoint.

    Flow:
        User question → Classifier → RAG (support data) | LLM (general)

    Example SUPPORT_DATA question:
        "What are the most common complaints today?"

    Example GENERAL question:
        "What is machine learning?"
    """
    result = chat(request.question)
    return result


@app.get("/")
def root():
    """Serve the frontend index.html file."""
    index_path = os.path.join(os.path.dirname(__file__), "index.html")
    return FileResponse(index_path)


@app.get("/index.html")
def get_index():
    """Explicitly serve /index.html."""
    index_path = os.path.join(os.path.dirname(__file__), "index.html")
    return FileResponse(index_path)


@app.get("/health")
def health():
    return {"status": "ok"}
