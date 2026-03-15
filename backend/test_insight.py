import requests, json

r = requests.post("http://127.0.0.1:8000/login",
                   json={"email": "admin@techco.com", "password": "demo1234"}, timeout=5)
token = r.json().get("access_token", "")
print("Login:", r.status_code)

r2 = requests.get("http://127.0.0.1:8000/calls/last-insight",
                   headers={"Authorization": "Bearer " + token}, timeout=10)
print("API:", r2.status_code)
data = r2.json()

if data.get("empty"):
    print("EMPTY - no calls with analysis found")
else:
    print("Quality Score:", data.get("quality_score"))
    print()
    print("=== INSIGHTS ===")
    for k, v in data.get("insights", {}).items():
        print(f"  {k}: {v}")
    print()
    print("=== SCORE BREAKDOWN ===")
    for s in data.get("score_breakdown", []):
        print(f"  {s['label']}: {s['score']}/{s['max']}")
    print()
    print("=== TRANSCRIPT ===")
    for t in data.get("transcript", [])[:4]:
        hl = f" [{t['highlight']}]" if t.get("highlight") else ""
        print(f"  {t['speaker']}: {t['text'][:80]}{hl}")
    print(f"  ... {len(data.get('transcript', []))} total turns")
    print()
    print("=== COACHING ===")
    print("  Strengths:", data.get("coaching", {}).get("strengths", []))
    print("  Improvements:", data.get("coaching", {}).get("improvements", []))
    print()
    print("=== CONFIDENCE ===")
    for c in data.get("confidence", []):
        print(f"  {c['label']}: {c['confidence']}%")
    print()
    print("Tags:", data.get("tags", []))
