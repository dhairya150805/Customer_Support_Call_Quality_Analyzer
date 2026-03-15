from database import engine
from sqlalchemy import text

with engine.connect() as conn:
    conn.execute(text("ALTER TABLE live_sessions ADD COLUMN language VARCHAR(20) DEFAULT 'en'"))
    conn.commit()
    print("Added language column to live_sessions")
