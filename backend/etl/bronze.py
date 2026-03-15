"""
Bronze Layer — Raw JSON ingestion into bronze_raw_calls.

Reads every *.json file in  data/raw/
Loads each call record as-is into bronze_raw_calls.
Moves processed files into  data/bronze/  for audit.
"""

import json
import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from etl.warehouse_models import BronzeRawCall

# Paths relative to project root (one level above backend/)
_PROJECT = Path(__file__).resolve().parent.parent.parent
RAW_DIR    = _PROJECT / "data" / "raw"
BRONZE_DIR = _PROJECT / "data" / "bronze"


def ingest_raw_files(db: Session, *, raw_dir: Path = RAW_DIR) -> dict:
    """
    Scan raw_dir for *.json, load each into bronze_raw_calls.

    Returns summary dict: {files, records, batch_id}
    """
    json_files = sorted(raw_dir.glob("*.json"))
    if not json_files:
        print("[bronze] No JSON files found in", raw_dir)
        return {"files": 0, "records": 0, "batch_id": None}

    batch_id = f"batch-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
    total_records = 0

    for fpath in json_files:
        print(f"[bronze] Ingesting {fpath.name} …")
        with open(fpath, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Support both {"calls": [...]} and plain [...]
        records = data.get("calls", data) if isinstance(data, dict) else data
        if not isinstance(records, list):
            print(f"[bronze]  ⚠ Skipping {fpath.name} — not a list or {{calls:[]}}")
            continue

        for idx, record in enumerate(records):
            row = BronzeRawCall(
                batch_id=batch_id,
                source_file=fpath.name,
                record_index=idx,
                raw_json=record,
                contact_id=record.get("contact_id"),
                agent_id=record.get("agent_id"),
                is_processed=False,
            )
            db.add(row)
            total_records += 1

        # Move file to bronze/ archive
        dest = BRONZE_DIR / f"{batch_id}__{fpath.name}"
        shutil.move(str(fpath), str(dest))
        print(f"[bronze]  ✓ {len(records)} records → bronze_raw_calls  |  archived → {dest.name}")

    db.commit()
    print(f"[bronze] Done — batch={batch_id}  files={len(json_files)}  records={total_records}")
    return {"files": len(json_files), "records": total_records, "batch_id": batch_id}
