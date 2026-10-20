"""Load validated simulated infrastructure datasets into an auditable DuckDB database.

Usage: python -m finops.ingest --raw-dir data/raw --db data/warehouse/finops.duckdb
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import duckdb

from finops.validation import SCHEMAS, ValidatedDataset, load_and_validate_csv

DATASETS = tuple(SCHEMAS)


def prepare_tables(con: duckdb.DuckDBPyConnection) -> None:
    for name, columns in SCHEMAS.items():
        column_sql = ", ".join(f"{column.name} {column.sql_type}" for column in columns)
        con.execute(f"CREATE TABLE IF NOT EXISTS {name} ({column_sql})")
    con.execute("""
        CREATE TABLE IF NOT EXISTS ingestion_quarantine (
            run_id VARCHAR,
            dataset VARCHAR,
            csv_line_number BIGINT,
            error_reasons VARCHAR,
            raw_record_json VARCHAR
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS ingestion_audit (
            run_id VARCHAR,
            ingestion_time_utc TIMESTAMP,
            dataset VARCHAR,
            source_count BIGINT,
            accepted_count BIGINT,
            rejected_count BIGINT,
            loaded_count BIGINT,
            source_parseable_usd DECIMAL(18,2),
            accepted_usd DECIMAL(18,2),
            rejected_parseable_usd DECIMAL(18,2),
            db_loaded_usd DECIMAL(18,2),
            unparseable_amount_rows BIGINT,
            reconciled BOOLEAN
        )
    """)


def ingest(raw_dir: Path, db_path: Path) -> dict:
    """Replace current raw tables atomically; keep audit history by run ID.

    Failures in a CSV schema abort before the existing DB is modified. A
    transaction prevents partially loaded tables from becoming visible.
    """
    raw_dir, db_path = Path(raw_dir), Path(db_path)
    # Validate ALL three source files before altering warehouse tables.
    datasets: list[ValidatedDataset] = [
        load_and_validate_csv(name, raw_dir) for name in DATASETS
    ]
    db_path.parent.mkdir(parents=True, exist_ok=True)
    run_id = str(uuid4())
    started_at = datetime.now(timezone.utc).replace(tzinfo=None)
    connection = duckdb.connect(str(db_path))
    in_transaction = False
    try:
        connection.execute("BEGIN TRANSACTION")
        in_transaction = True
        prepare_tables(connection)
        for name in DATASETS:
            connection.execute(f"DELETE FROM {name}")
        # 'Current quarantine' belongs to latest successful run only.
        connection.execute("DELETE FROM ingestion_quarantine")
        summaries = {}
        for dataset in datasets:
            columns = SCHEMAS[dataset.name]
            placeholders = ", ".join("?" for _ in columns)
            if dataset.rows:
                connection.executemany(
                    f"INSERT INTO {dataset.name} VALUES ({placeholders})",
                    dataset.rows,
                )
            if dataset.rejected:
                connection.executemany(
                    "INSERT INTO ingestion_quarantine VALUES (?, ?, ?, ?, ?)",
                    [
                        (run_id, dataset.name, r.row_number, "; ".join(r.reasons), r.raw_json)
                        for r in dataset.rejected
                    ],
                )
            loaded_count = connection.execute(
                f"SELECT COUNT(*) FROM {dataset.name}"
            ).fetchone()[0]
            if loaded_count != len(dataset.rows):
                raise AssertionError(f"loaded row count mismatch: {dataset.name}")

            db_total = None
            reconciled = None
            if dataset.name == "billing":
                db_total = connection.execute(
                    "SELECT COALESCE(SUM(unblended_cost_usd), 0) FROM billing"
                ).fetchone()[0]
                db_total = Decimal(str(db_total)).quantize(Decimal("0.01"))
                reconciled = (
                    db_total == dataset.accepted_usd
                    and dataset.source_parseable_usd
                    == dataset.accepted_usd + dataset.rejected_parseable_usd
                    and dataset.unparseable_amount_rows == 0
                )
                if db_total != dataset.accepted_usd:
                    raise AssertionError("billing warehouse totals do not match valid source totals")

            connection.execute(
                "INSERT INTO ingestion_audit VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    run_id,
                    started_at,
                    dataset.name,
                    dataset.source_count,
                    len(dataset.rows),
                    len(dataset.rejected),
                    loaded_count,
                    dataset.source_parseable_usd if dataset.name == "billing" else None,
                    dataset.accepted_usd if dataset.name == "billing" else None,
                    dataset.rejected_parseable_usd if dataset.name == "billing" else None,
                    db_total,
                    dataset.unparseable_amount_rows if dataset.name == "billing" else None,
                    reconciled,
                ),
            )
            summaries[dataset.name] = {
                "source": dataset.source_count,
                "accepted": len(dataset.rows),
                "quarantined": len(dataset.rejected),
                "loaded": loaded_count,
            }
            if dataset.name == "billing":
                summaries[dataset.name].update(
                    {
                        "source_parseable_usd": str(dataset.source_parseable_usd),
                        "accepted_usd": str(dataset.accepted_usd),
                        "rejected_parseable_usd": str(dataset.rejected_parseable_usd),
                        "unparseable_amount_rows": dataset.unparseable_amount_rows,
                        "reconciled": reconciled,
                    }
                )

        connection.execute("COMMIT")
        in_transaction = False
        return {"run_id": run_id, "database": str(db_path), "datasets": summaries}
    except Exception:
        if in_transaction:
            connection.execute("ROLLBACK")
        raise
    finally:
        connection.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate and ingest Phase 1 synthetic data")
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--db", type=Path, default=Path("data/warehouse/finops.duckdb"))
    args = parser.parse_args()
    print(json.dumps(ingest(args.raw_dir, args.db), indent=2))


if __name__ == "__main__":
    main()
