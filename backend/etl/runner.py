"""
ETL Runner — Orchestrates the full Bronze → Silver → Gold pipeline.

Usage:
    cd backend
    python -m etl.runner                    # full pipeline
    python -m etl.runner --bronze-only      # just ingest raw files
    python -m etl.runner --silver-only      # just clean bronze
    python -m etl.runner --gold-only        # just build facts
    python -m etl.runner --no-llm           # skip LLM (gold without AI scoring)
"""

import argparse
import sys
import os
import time
from datetime import datetime, timezone

# Make sure project paths are on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from database import SessionLocal, engine, Base
from etl.warehouse_models import (
    BronzeRawCall, SilverCall, SilverAgent, SilverInteraction, SilverExtractedEntity,
    DimDate, DimAgent, DimIssue, DimSentiment, DimResolution, DimCallSource,
    FactCall, FactAgentDaily, FactDailySummary, FactIssueResolution,
)
from etl.bronze import ingest_raw_files
from etl.silver import transform_to_silver
from etl.gold import populate_dimensions, build_facts


def create_warehouse_tables():
    """Create all warehouse tables if they don't exist."""
    print("=" * 60)
    print("  Creating warehouse tables …")
    print("=" * 60)
    Base.metadata.create_all(bind=engine)
    print("  ✓ All tables ready\n")


def run_bronze(db):
    print("=" * 60)
    print("  BRONZE LAYER — Raw JSON Ingestion")
    print("=" * 60)
    result = ingest_raw_files(db)
    print()
    return result


def run_silver(db, batch_id=None):
    print("=" * 60)
    print("  SILVER LAYER — Clean & Normalize")
    print("=" * 60)
    result = transform_to_silver(db, batch_id=batch_id)
    print()
    return result


def run_gold(db, company_id=1, batch_id=None):
    print("=" * 60)
    print("  GOLD LAYER — Dimensions & Facts")
    print("=" * 60)
    populate_dimensions(db)
    result = build_facts(db, company_id=company_id, batch_id=batch_id)
    print()
    return result


def main():
    parser = argparse.ArgumentParser(description="ReViewSense ETL Pipeline")
    parser.add_argument("--bronze-only", action="store_true", help="Only run bronze ingestion")
    parser.add_argument("--silver-only", action="store_true", help="Only run silver transform")
    parser.add_argument("--gold-only",   action="store_true", help="Only run gold build")
    parser.add_argument("--company-id",  type=int, default=1, help="Company ID for gold layer")
    args = parser.parse_args()

    start = time.time()
    print("\n" + "═" * 60)
    print(f"  ReViewSense ETL Pipeline — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("═" * 60 + "\n")

    create_warehouse_tables()

    db = SessionLocal()
    batch_id = None

    try:
        if args.bronze_only:
            run_bronze(db)
        elif args.silver_only:
            run_silver(db)
        elif args.gold_only:
            run_gold(db, company_id=args.company_id)
        else:
            # Full pipeline
            bronze_result = run_bronze(db)
            batch_id = bronze_result.get("batch_id")

            if bronze_result["records"] > 0:
                run_silver(db, batch_id=batch_id)
                run_gold(db, company_id=args.company_id, batch_id=batch_id)
            else:
                # Still try silver/gold for any leftover unprocessed rows
                run_silver(db)
                run_gold(db, company_id=args.company_id)

        elapsed = time.time() - start
        print("═" * 60)
        print(f"  ETL COMPLETE — {elapsed:.1f}s")
        print("═" * 60 + "\n")

        # Summary counts
        bronze_ct = db.query(BronzeRawCall).count()
        silver_ct = db.query(SilverCall).count()
        fact_ct   = db.query(FactCall).count()
        agent_ct  = db.query(DimAgent).count()
        issue_ct  = db.query(DimIssue).count()
        print(f"  Warehouse totals:")
        print(f"    Bronze raw calls :  {bronze_ct}")
        print(f"    Silver calls     :  {silver_ct}")
        print(f"    Fact calls       :  {fact_ct}")
        print(f"    Dim agents       :  {agent_ct}")
        print(f"    Dim issues       :  {issue_ct}")
        print()

    finally:
        db.close()


if __name__ == "__main__":
    main()
