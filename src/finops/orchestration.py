"""Fail-closed stage checks for the scheduled FinOps workflow.

CLI used by Airflow; supports manual invocation outside Airflow as well.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_RAW = Path("data/raw")
DEFAULT_DB = Path("data/warehouse/finops.duckdb")


def check_sources(raw_dir: Path = DEFAULT_RAW) -> dict[str, int]:
    """Require each data source with an exact header and at least one record."""
    from finops.validation import SCHEMAS

    counts: dict[str, int] = {}
    for dataset, cols in SCHEMAS.items():
        path = Path(raw_dir) / f"{dataset}.csv"
        if not path.is_file():
            raise FileNotFoundError(f"Missing source dataset: {path}")
        with path.open(newline="", encoding="utf-8-sig") as fh:
            reader = csv.DictReader(fh)
            found = reader.fieldnames or []
            expected = [c.name for c in cols]
            if found != expected:
                raise ValueError(
                    f"Incorrect columns in {path}: expected {expected}, got {found}"
                )
            count = sum(1 for _ in reader)
        if count < 1:
            raise ValueError(f"Source dataset is empty: {path}")
        counts[dataset] = count
    return counts


def check_ingestion(db_path: Path = DEFAULT_DB) -> dict[str, int]:
    """Reject incomplete runs, quarantines, and failed billing reconciliation."""
    from finops.validation import SCHEMAS

    path = Path(db_path)
    if not path.is_file():
        raise FileNotFoundError(f"DuckDB warehouse is missing: {path}")
    import duckdb
    conn = duckdb.connect(str(path), read_only=True)
    try:
        latest = conn.execute(
            "SELECT run_id FROM main.ingestion_audit "
            "GROUP BY run_id ORDER BY MAX(ingestion_time_utc) DESC, run_id DESC LIMIT 1"
        ).fetchone()
        if latest is None:
            raise AssertionError("No ingestion audit run found")
        run_id = latest[0]
        rows = conn.execute(
            "SELECT dataset, source_count, accepted_count, rejected_count, "
            "loaded_count, reconciled, unparseable_amount_rows "
            "FROM main.ingestion_audit WHERE run_id = ?",
            [run_id],
        ).fetchall()
        if len(rows) != len(SCHEMAS) or {r[0] for r in rows} != set(SCHEMAS):
            raise AssertionError("Ingestion audit lacks exactly one row per dataset")
        counts: dict[str, int] = {}
        for dataset, source_count, accepted, rejected, loaded, reconciled, invalid_costs in rows:
            if source_count < 1 or not (source_count == accepted == loaded):
                raise AssertionError(f"Dataset count mismatch for {dataset}")
            if rejected != 0:
                raise AssertionError(f"{dataset} has {rejected} quarantined record(s)")
            if dataset == "billing" and (reconciled is not True or invalid_costs != 0):
                raise AssertionError("Billing ingestion failed reconciliation")
            counts[dataset] = loaded
        return counts
    finally:
        conn.close()


def check_marts(db_path: Path = DEFAULT_DB) -> str:
    """Reuse verified Phase 4 cost reconciliation (overall and per day)."""
    path = Path(db_path)
    if not path.is_file():
        raise FileNotFoundError(f"DuckDB warehouse is missing: {path}")
    from finops.phase4_report import report

    return report(path)


def write_report(
    db_path: Path = DEFAULT_DB,
    output: Path = Path("reports/latest_finops_report.txt"),
) -> Path:
    """Atomically replace latest report after the reconciliation gate passes."""
    audit = check_ingestion(db_path)
    details = check_marts(db_path)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).isoformat()
    report_text = (
        f"FinOps scheduled run verified at {stamp}\n"
        f"Loaded records: {audit}\n\n{details}\n"
    )
    temp_file = output.with_name(output.name + ".tmp")
    temp_file.write_text(report_text, encoding="utf-8")
    temp_file.replace(output)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="FinOps stage gates used by Apache Airflow")
    parser.add_argument(
        "action",
        choices=["check-sources", "check-ingestion", "check-marts", "write-report"],
    )
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--output", type=Path, default=Path("reports/latest_finops_report.txt"))
    args = parser.parse_args()
    if args.action == "check-sources":
        print(f"Source check PASS: {check_sources(args.raw_dir)}")
    elif args.action == "check-ingestion":
        print(f"Ingestion audit PASS: {check_ingestion(args.db)}")
    elif args.action == "check-marts":
        print(check_marts(args.db))
    else:
        print(f"Report written: {write_report(args.db, args.output)}")


if __name__ == "__main__":
    main()
