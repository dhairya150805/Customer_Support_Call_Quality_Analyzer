"""Quick test of the Groq evaluator pipeline."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ai_pipeline.evaluator import evaluate_call, chunk_transcript, embed_chunks

SAMPLE = """
Agent: Thank you for calling TechSupport. How can I help you today?
Customer: Hi, my internet has been down since yesterday morning and I'm working from home. This is absolutely terrible!
Agent: I'm really sorry to hear that. I completely understand how frustrating this must be, especially when you're working from home. Let me pull up your account right away.
Customer: I've been waiting for 24 hours! My boss is not happy with me.
Agent: I sincerely apologize for the inconvenience. I can see there was a network outage in your area. Our engineers have identified the issue and it should be resolved within 2 hours.
Customer: Two more hours? Are you serious?
Agent: I understand your frustration. As a goodwill gesture, I'll apply a 3-day credit to your account for the inconvenience. Is there anything else I can help you with?
Customer: Fine. I hope it's actually fixed this time.
"""

print("Testing chunk_transcript...")
chunks = chunk_transcript(SAMPLE)
print(f"  {len(chunks)} chunks created")

print("\nTesting embed_chunks...")
embeddings = embed_chunks(chunks)
print(f"  {len(embeddings)} embeddings, dim={len(embeddings[0])}")

print("\nTesting evaluate_call (Groq LLM)...")
result = evaluate_call(SAMPLE)
print("  Result:")
for k, v in result.items():
    print(f"    {k}: {v}")

print("\n✅ All pipeline steps work!")
