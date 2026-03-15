import requests, json, sys

try:
    r = requests.get("http://127.0.0.1:8000/n8n/health", timeout=5)
    print("HEALTH:", r.status_code)
except Exception as e:
    print("HEALTH FAILED:", e)
    sys.exit(1)

try:
    r = requests.post("http://127.0.0.1:8000/login",
                       json={"email": "admin@techco.com", "password": "demo1234"},
                       timeout=5)
    print("LOGIN:", r.status_code)
    token = r.json().get("access_token", "")
    if not token:
        print("NO TOKEN")
        sys.exit(1)
    print("TOKEN:", token[:20] + "...")
except Exception as e:
    print("LOGIN FAILED:", e)
    sys.exit(1)

try:
    r2 = requests.get("http://127.0.0.1:8000/calls/live-analysis",
                       headers={"Authorization": "Bearer " + token},
                       timeout=10)
    print("API:", r2.status_code)
    data = r2.json()
    calls = data.get("calls", [])
    print("Total calls:", len(calls))
    if calls:
        c = calls[0]
        print("Session:", c["sessionId"], "| Status:", c["status"], "| Turns:", len(c["transcript"]))
        a = c.get("analysis")
        if a:
            print("Sentiment:", a.get("sentiment"), "| Score:", a.get("score"))
            print("Comm:", a.get("communicationScore"), "| Prob:", a.get("problemSolvingScore"), "| Emp:", a.get("empathyScore"))
            print("Comp:", a.get("complianceScore"), "| Close:", a.get("closingScore"))
            print("Summary:", str(a.get("summary", ""))[:150])
        else:
            print("NO ANALYSIS in response")
        print("Tags:", c.get("tags"))
except Exception as e:
    print("API FAILED:", e)
