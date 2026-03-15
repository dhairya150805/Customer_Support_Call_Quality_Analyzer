import requests
import json

payload = {
    "message": {
        "type": "end-of-call-report",
        "call": {
            "id": "test-pipeline-003",
            "customer": {"number": "+919978840108"},
            "assistant": {
                "name": "ReViewSense Support Agent",
                "transcriber": {"language": "en"}
            },
            "startedAt": "2026-03-15T10:00:00Z",
            "endedAt": "2026-03-15T10:03:30Z"
        },
        "messages": [
            {"role": "assistant", "message": "Hello! Thank you for calling ReviewSense. How can I help you today?"},
            {"role": "user", "message": "Hi, I have been having issues with my account. I cannot log in and it keeps showing an error."},
            {"role": "assistant", "message": "I am sorry about that. Can you tell me what error you are seeing?"},
            {"role": "user", "message": "It says invalid credentials but my password is correct. I have tried for 2 days and I am really frustrated."},
            {"role": "assistant", "message": "I completely understand your frustration. Let me check your account. What is your registered email?"},
            {"role": "user", "message": "john.doe@example.com"},
            {"role": "assistant", "message": "Your account was locked due to multiple failed attempts. I have reset it and sent a password reset link to your email."},
            {"role": "user", "message": "Oh great, I can see the email now. Yes I am logged in! Thank you so much!"},
            {"role": "assistant", "message": "Wonderful! Is there anything else I can help you with?"},
            {"role": "user", "message": "No that is all. Thank you for the excellent support!"},
            {"role": "assistant", "message": "You are welcome! Have a great day!"}
        ]
    }
}

print("=== Sending simulated Vapi end-of-call-report ===")
r = requests.post("http://127.0.0.1:8000/vapi/webhook", json=payload)
print(f"Status: {r.status_code}")
try:
    print(f"Response: {json.dumps(r.json(), indent=2)}")
except:
    print(f"Text: {r.text[:500]}")
