"""
seed_data.py — Run this ONCE to populate the ChromaDB vector store
with sample call analysis records so the chatbot has data to search.

Usage:
    cd d:/kenexai/chatbot
    python seed_data.py
"""

from vector_store import add_documents

SAMPLE_RECORDS = [
    {
        "id": "call_001",
        "text": (
            "Customer called about a refund not received after 10 days. "
            "Agent escalated to billing team. Issue unresolved at end of call."
        ),
        "metadata": {
            "call_id": "call_001",
            "agent_id": "agent_12",
            "issue": "Refund Delay",
            "sentiment": "negative",
            "quality_score": 55,
            "date": "2026-03-10",
        },
    },
    {
        "id": "call_002",
        "text": (
            "Customer reported login failure after password reset. "
            "Agent guided through steps and issue was resolved in 5 minutes."
        ),
        "metadata": {
            "call_id": "call_002",
            "agent_id": "agent_08",
            "issue": "Login Issue",
            "sentiment": "neutral",
            "quality_score": 82,
            "date": "2026-03-11",
        },
    },
    {
        "id": "call_003",
        "text": (
            "Payment failed during checkout. Customer reported error code 402. "
            "Agent confirmed server-side payment gateway issue and logged a ticket."
        ),
        "metadata": {
            "call_id": "call_003",
            "agent_id": "agent_05",
            "issue": "Payment Failure",
            "sentiment": "negative",
            "quality_score": 60,
            "date": "2026-03-11",
        },
    },
    {
        "id": "call_004",
        "text": (
            "Customer asked about status of refund for cancelled subscription. "
            "Refund was confirmed processed but not yet credited to account."
        ),
        "metadata": {
            "call_id": "call_004",
            "agent_id": "agent_12",
            "issue": "Refund Status",
            "sentiment": "neutral",
            "quality_score": 72,
            "date": "2026-03-12",
        },
    },
    {
        "id": "call_005",
        "text": (
            "Customer praised agent for quick resolution of delivery tracking issue. "
            "Very satisfied with the support received."
        ),
        "metadata": {
            "call_id": "call_005",
            "agent_id": "agent_03",
            "issue": "Delivery Tracking",
            "sentiment": "positive",
            "quality_score": 95,
            "date": "2026-03-12",
        },
    },
    {
        "id": "call_006",
        "text": (
            "Multiple refund-related complaints received today from users who upgraded plan. "
            "Billing system error suspected. Three calls in one hour about same issue."
        ),
        "metadata": {
            "call_id": "call_006",
            "agent_id": "agent_07",
            "issue": "Refund - Billing Error",
            "sentiment": "negative",
            "quality_score": 48,
            "date": "2026-03-13",
        },
    },
    {
        "id": "call_007",
        "text": (
            "Agent performance review: agent_12 received 3 negative sentiment calls this week, "
            "average quality score 58. Requires coaching on de-escalation techniques."
        ),
        "metadata": {
            "call_id": "call_007",
            "agent_id": "agent_12",
            "issue": "Agent Performance",
            "sentiment": "negative",
            "quality_score": 58,
            "date": "2026-03-13",
        },
    },
    {
        "id": "call_008",
        "text": (
            "Dashboard metrics for today: 34 total calls, "
            "24% refund complaints, 18% login issues, 12% payment failures. "
            "Overall average quality score: 71. Risk flag rate: 22%."
        ),
        "metadata": {
            "call_id": "call_008",
            "agent_id": "system",
            "issue": "Dashboard Summary",
            "sentiment": "neutral",
            "quality_score": 71,
            "date": "2026-03-14",
        },
    },
]


if __name__ == "__main__":
    print("🌱 Seeding ChromaDB vector store with sample support records...")
    add_documents(SAMPLE_RECORDS)
    print(f"✅ Done! {len(SAMPLE_RECORDS)} records added.")
    print("You can now run: uvicorn main:app --reload")
