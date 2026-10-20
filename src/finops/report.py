"""Command line summary of current ingested data and billing reconciliation."""
from __future__ import annotations

import argparse
from pathlib import Path

import duckdb


def report(db_path: Path) -> str:
    if not db_path.is_file():
        raise FileNotFoundError(f"Warehouse not found: {db_path}. Run ingestion first.")
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        lines = ["CURRENT WAREHOUSE COUNTS"]
        for dataset in ("billing", "k8s_metrics", "product_usage"):
            count = con.execute(f"SELECT COUNT(*) FROM {dataset}").fetchone()[0]
            lines.append(f"  {dataset}: {count}")
        lines.append("BILLING SUMMARY BY APPLICATION (USD)")
        rows = con.execute("""
            SELECT application, SUM(unblended_cost_usd) AS cost
            FROM billing GROUP BY application ORDER BY application
        """).fetchall()
        for app, cost in rows:
            lines.append(f"  {app}: ${cost:,.2f}")
        audit_rows = con.execute("""
            SELECT dataset, source_count, accepted_count, rejected_count, loaded_count,
                   reconciled, unparseable_amount_rows
            FROM ingestion_audit
            WHERE run_id = (SELECT run_id FROM ingestion_audit ORDER BY ingestion_time_utc DESC LIMIT 1)
            ORDER BY dataset
        """).fetchall()
        lines.append("LATEST INGESTION AUDIT")
        for dataset, source, accepted, rejected, loaded, reconciled, unparseable in audit_rows:
            lines.append(f"  {dataset}: source={source} accepted={accepted} rejected={rejected} loaded={loaded}")
            if dataset == "billing":
                label = "PASS" if reconciled else "PARTIAL / REVIEW"
                lines.append(f"  Billing reconciliation: {label} (unparseable cost rows={unparseable})")
        return "\n".join(lines)
    finally:
        con.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=Path("data/warehouse/finops.duckdb"))
    args = parser.parse_args()
    print(report(args.db))


if __name__ == "__main__":
    main()
