"""
Chatbot route — exposes the hybrid RAG chatbot via the main backend.
All support-data questions are answered from the PostgreSQL database.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from auth import get_current_user
from database import get_db
import models
from services.chatbot.chat import chat

router = APIRouter(prefix="/chatbot", tags=["chatbot"])


class ChatRequest(BaseModel):
    question: str


class ChatResponse(BaseModel):
    question: str
    intent: str
    mode: str
    answer: str
    sources: list


@router.post("/chat", response_model=ChatResponse)
def chatbot_chat(
    body: ChatRequest,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Hybrid RAG chatbot endpoint (requires authentication).

    Flow:
        User question → Classifier → RAG (DB retrieval + LLM) | LLM (general)
    """
    result = chat(body.question, db, user.company_id)
    return result


@router.post("/query", response_model=ChatResponse)
def chatbot_query(
    body: ChatRequest,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Dedicated RAG query endpoint — always retrieves from the database.
    Alias for /chat but ensures the same pipeline.
    """
    result = chat(body.question, db, user.company_id)
    return result


@router.get("/health")
def chatbot_health():
    return {"status": "ok"}
