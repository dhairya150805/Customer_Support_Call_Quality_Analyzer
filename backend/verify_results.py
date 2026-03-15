from database import SessionLocal
import models

db = SessionLocal()

# Check the analysis
a = db.query(models.CallAnalysis).filter(models.CallAnalysis.call_id == 477).first()
if a:
    print(f"Sentiment: {a.sentiment}")
    print(f"Emotion: {a.emotion}")
    print(f"Summary: {a.summary}")
    print(f"Issue: {a.issue}")
    print(f"Resolution: {a.resolution_status}")
    print(f"Overall Score: {a.score}")
    print(f"Agent Prof: {a.agent_professionalism}")
    print(f"Cust Frust: {a.customer_frustration}")
    print(f"Communication: {a.communication_score}/30")
    print(f"Problem Solving: {a.problem_solving_score}/25")
    print(f"Empathy: {a.empathy_score}/20")
    print(f"Compliance: {a.compliance_score}/15")
    print(f"Closing: {a.closing_score}/10")
else:
    print("NO ANALYSIS FOUND")

# Check tags
tags = db.query(models.CallTag).filter(models.CallTag.call_id == 477).all()
print(f"Tags: {[t.tag for t in tags]}")

# Check session status
s = db.query(models.LiveSession).filter(models.LiveSession.id == 18).first()
status = s.status if s else "NOT FOUND"
print(f"Session status: {status}")

# Check call status
c = db.query(models.Call).filter(models.Call.id == 477).first()
cstatus = c.status if c else "NOT FOUND"
print(f"Call status: {cstatus}")

# Check messages
msgs = db.query(models.LiveMessage).filter(models.LiveMessage.session_id == 18).order_by(models.LiveMessage.seq).all()
print(f"Messages: {len(msgs)} turns")
for m in msgs[:3]:
    print(f"  [{m.speaker}] {m.text[:80]}")

db.close()
