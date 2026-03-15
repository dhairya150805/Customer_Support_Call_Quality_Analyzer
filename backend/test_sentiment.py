"""Test the evaluator with the NEW model."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ai_pipeline.evaluator import evaluate_call

# Clearly negative/angry transcript
ANGRY = """
Customer: I am absolutely furious! My service has been down for 3 days and nobody told me!
Agent: I apologize for the inconvenience.
Customer: Don't just apologize! Fix it! I'm paying for a service I'm not getting. This is completely unacceptable!
Agent: I understand your frustration. Let me escalate this right now.
Customer: I want a full refund and an explanation! This is the worst service I've ever experienced!
Agent: I will process a refund and escalate to management. I'm very sorry.
"""

# Clearly positive transcript  
HAPPY = """
Customer: Hi, I just wanted to say thank you! The technician came yesterday and fixed everything perfectly.
Agent: That's wonderful to hear! I'm so glad it was resolved quickly.
Customer: He was very professional and explained everything. My service is working perfectly now!
Agent: Excellent! I'll pass that feedback along. Is there anything else I can help you with?
Customer: No, everything is great. You have a wonderful team!
"""

print("Testing ANGRY transcript...")
r1 = evaluate_call(ANGRY)
print(f"  Sentiment: {r1['sentiment']}")
print(f"  Emotion: {r1['emotion']}")
print(f"  Frustration: {r1['customer_frustration']}/5")
print(f"  Resolution: {r1['resolution_status']}")
print(f"  Quality: {r1['quality_score']}")

print()
print("Testing HAPPY transcript...")
r2 = evaluate_call(HAPPY)
print(f"  Sentiment: {r2['sentiment']}")
print(f"  Emotion: {r2['emotion']}")
print(f"  Frustration: {r2['customer_frustration']}/5")
print(f"  Resolution: {r2['resolution_status']}")
print(f"  Quality: {r2['quality_score']}")

print()
if r1["sentiment"] == "Negative" and r2["sentiment"] == "Positive":
    print("✅ LLM is working correctly! Sentiment is accurate.")
else:
    print(f"⚠️  Check: angry={r1['sentiment']}, happy={r2['sentiment']}")
