from database import engine
from sqlalchemy import text

with engine.connect() as conn:
    r = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='live_sessions' ORDER BY ordinal_position"))
    print("live_sessions columns:", [x[0] for x in r])

    r2 = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='calls' ORDER BY ordinal_position"))
    print("calls columns:", [x[0] for x in r2])

    r3 = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='call_analysis' ORDER BY ordinal_position"))
    print("call_analysis columns:", [x[0] for x in r3])
