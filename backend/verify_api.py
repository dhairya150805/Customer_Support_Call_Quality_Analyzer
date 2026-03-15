import requests, json

r = requests.post("http://127.0.0.1:8000/login", json={"email": "admin@techco.com", "password": "demo1234"})
token = r.json().get("access_token", "")
print("Token OK" if token else "NO TOKEN")

r2 = requests.get("http://127.0.0.1:8000/calls/live-analysis", headers={"Authorization": "Bearer " + token})
print("API Status:", r2.status_code)
data = r2.json()

calls = data.get("calls", [])
print("Total calls:", len(calls))
if calls:
    c = calls[0]
    sid = c["sessionId"]
    agent = c["agentName"]
    status = c["status"]
    turns = len(c["transcript"])
    print(f"Session: {sid} | Agent: {agent} | Status: {status} | Turns: {turns}")
    a = c.get("analysis")
    if a:
        print(f"Sentiment: {a['sentiment']} | Score: {a['score']}")
        comm = a.get("communicationScore")
        prob = a.get("problemSolvingScore")
        emp = a.get("empathyScore")
        comp = a.get("complianceScore")
        clo = a.get("closingScore")
        print(f"Comm: {comm} | ProbSolve: {prob} | Empathy: {emp} | Comp: {comp} | Close: {clo}")
        print(f"Summary: {str(a.get('summary', ''))[:120]}")
    print(f"Tags: {c['tags']}")
