import os
from google import genai
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
MODEL = "gemini-2.5-flash"

CLASSIFIER_PROMPT = """
You are a query classifier for a customer support analytics chatbot.

Determine whether the user's question is related to:
- customer complaints
- support calls / call transcripts
- refunds
- login issues
- payment failures
- sentiment analysis
- agent performance
- support dashboard metrics
- call quality scores
- issue categories

If YES → return exactly: SUPPORT_DATA

If the question is about anything else such as:
- programming / coding
- sports
- general knowledge
- weather
- politics
- science / technology (not related to support)

If NO → return exactly: GENERAL

User question: {question}

Return only one word: SUPPORT_DATA or GENERAL
"""


def classify_query(question: str) -> str:
    """
    Classify the user's question.
    Returns 'SUPPORT_DATA' or 'GENERAL'.
    """
    prompt = CLASSIFIER_PROMPT.format(question=question)
    response = client.models.generate_content(model=MODEL, contents=prompt)
    result = response.text.strip().upper()

    # Ensure we only return valid labels
    if "SUPPORT_DATA" in result:
        return "SUPPORT_DATA"
    return "GENERAL"
