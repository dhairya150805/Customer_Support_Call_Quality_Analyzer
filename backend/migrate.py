"""
ReViewSense AI — Database Migration Script
Run: python migrate.py
Idempotent — safe to run multiple times.
Works with PostgreSQL (Supabase).
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from database import engine, Base
from sqlalchemy import text, inspect

# Import ALL models so Base.metadata knows every table
import models  # noqa: F401

# ── Step 1: Create all tables that don't exist yet ───────────────────────────
print("Creating tables …")
Base.metadata.create_all(bind=engine)
print("OK: All tables created / verified")


# ── Step 2: Safe column additions (SQLite-compatible) ───────────────────────
def add_column_if_missing(table: str, column: str, col_type: str, default=None):
    """Add a column if it doesn't already exist (PostgreSQL-compatible)."""
    insp = inspect(engine)
    existing = [c["name"] for c in insp.get_columns(table)]
    if column in existing:
        return
    default_clause = f" DEFAULT {default!r}" if default is not None else ""
    sql = f"ALTER TABLE {table} ADD COLUMN {column} {col_type}{default_clause}"
    with engine.connect() as conn:
        conn.execute(text(sql))
        conn.commit()
    print(f"  OK: {table}.{column} added")


# call_analysis — extended LLM fields
for col in ["emotion", "resolution_status"]:
    add_column_if_missing("call_analysis", col, "VARCHAR(50)")
for col in ["agent_professionalism", "customer_frustration",
            "communication_score", "problem_solving_score",
            "empathy_score", "compliance_score", "closing_score"]:
    add_column_if_missing("call_analysis", col, "INTEGER")

# calls — new columns
add_column_if_missing("calls", "agent_ref_id", "INTEGER")
add_column_if_missing("calls", "source",       "VARCHAR(20)", "upload")
add_column_if_missing("calls", "call_type",    "VARCHAR(50)", "inbound")
add_column_if_missing("calls", "phone_number", "VARCHAR(30)")
add_column_if_missing("calls", "status",       "VARCHAR(20)", "complete")

print("\nMigration complete!")
