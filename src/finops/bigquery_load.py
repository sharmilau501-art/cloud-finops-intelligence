"""Publish the existing FinOps PySpark Parquet marts to BigQuery.

First run a free/offline preflight:
  python -m finops.bigquery_load --dry-run

Then, only after setting up a Google Cloud project and ADC:
  python -m finops.bigquery_load --upload --project YOUR_PROJECT_ID

The input is simulated portfolio data, not real customer/cloud billing data.
"""
from __future__ import annotations

import argparse
import json
import re
import tempfile
from decimal import Decimal
from pathlib import Path
from typing import Any

from finops.quality_gate import assess_report

TABLES = ("billing_daily", "app_daily")
PROJECT_RE = re.compile(r"^[a-z][a-z0-9-]{4,61}[a-z0-9]$")
DATASET_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def check_identifiers(project: str, dataset: str) -> None:
    """Restrict identifiers before interpolating them in BigQuery SQL."""
    if not PROJECT_RE.fullmatch(project):
        raise ValueError(f"Invalid Google Cloud project ID: {project!r}")
    if not DATASET_RE.fullmatch(dataset):
        raise ValueError(f"Invalid BigQuery dataset ID: {dataset!r}")


def preflight(spark_dir: Path) -> dict[str, Any]:
    """Validate the Spark quality gate and discover real Parquet part files."""
    spark_dir = Path(spark_dir)
    report_path = spark_dir / "quality_metrics.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    failures = assess_report(report)
    if failures:
        raise ValueError("Quality gate FAILED: " + "; ".join(failures))

    parts: dict[str, list[Path]] = {}
    for name in TABLES:
        directory = spark_dir / name
        matching = sorted(directory.glob("part-*.parquet"))
        if not matching or any(not p.is_file() or p.stat().st_size == 0 for p in matching):
            raise ValueError(f"Missing or empty Parquet part files: {directory}")
        parts[name] = matching

    counts = report["output_counts"]
    return {
        "status": "READY",
        "quality_gate": "PASS",
        "expected_counts": {name: counts[name] for name in TABLES},
        "expected_billing_usd": report["source_billed_usd"],
        "parquet_parts": {name: [str(p) for p in paths] for name, paths in parts.items()},
    }


def _consolidate_parts(paths: list[Path], destination: Path) -> None:
    """Combine local Spark part files into one load-job file (portfolio-sized data)."""
    import duckdb

    con = duckdb.connect(database=":memory:")
    try:
        con.read_parquet([str(path) for path in paths]).write_parquet(str(destination))
    finally:
        con.close()


def upload(
    plan: dict[str, Any], project: str, dataset: str, location: str = "US",
    client: Any = None, bq: Any = None,
) -> dict[str, Any]:
    """Upload two tables, assert BigQuery row counts and dollar reconciliation.

    Local Spark partitions are consolidated for this small demonstration.
    For larger cloud datasets, use GCS and a single BigQuery URI load job instead.
    """
    check_identifiers(project, dataset)
    if bq is None:
        from google.cloud import bigquery as bq
    if client is None:
        client = bq.Client(project=project)

    remote_dataset = client.get_dataset(f"{project}.{dataset}")
    actual_location = remote_dataset.location
    if actual_location.upper() != location.upper():
        raise ValueError(
            f"Dataset region {actual_location!r} differs from --location {location!r}"
        )

    loaded: dict[str, int] = {}
    with tempfile.TemporaryDirectory(prefix="finops-bigquery-") as tmpdir:
        for name in TABLES:
            table_id = f"{project}.{dataset}.{name}"
            local = Path(tmpdir) / f"{name}.parquet"
            _consolidate_parts([Path(p) for p in plan["parquet_parts"][name]], local)
            config = bq.LoadJobConfig(
                source_format=bq.SourceFormat.PARQUET,
                write_disposition=bq.WriteDisposition.WRITE_TRUNCATE,
            )
            with local.open("rb") as source:
                job = client.load_table_from_file(
                    source, table_id, rewind=True, size=local.stat().st_size,
                    job_config=config, location=location,
                )
                job.result()
            actual = client.get_table(table_id).num_rows
            expected = plan["expected_counts"][name]
            if actual != expected:
                raise AssertionError(f"{table_id}: expected {expected} rows; found {actual}")
            loaded[name] = actual

    billing_table = f"{project}.{dataset}.billing_daily"
    query = f"SELECT SUM(billed_cost_usd) AS total FROM `{billing_table}`"
    rows = list(client.query(query, location=location).result())
    if len(rows) != 1 or rows[0].total is None:
        raise AssertionError("BigQuery billing total query returned no amount")
    actual_usd = Decimal(str(rows[0].total)).quantize(Decimal("0.01"))
    expected_usd = Decimal(str(plan["expected_billing_usd"])).quantize(Decimal("0.01"))
    if actual_usd != expected_usd:
        raise AssertionError(f"BigQuery billing mismatch: {actual_usd} != {expected_usd}")

    return {
        "status": "PASS", "project": project, "dataset": dataset,
        "location": location, "loaded_counts": loaded,
        "source_billed_usd": str(expected_usd), "bigquery_billed_usd": str(actual_usd),
        "reconciled": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="FinOps PySpark to BigQuery loader")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="validate local outputs only; no GCP credentials")
    mode.add_argument("--upload", action="store_true", help="publish to BigQuery; uses application default credentials")
    parser.add_argument("--spark-dir", type=Path, default=Path("data/spark"))
    parser.add_argument("--project", help="Google Cloud project ID (upload only)")
    parser.add_argument("--dataset", default="finops_demo")
    parser.add_argument("--location", default="US")
    parser.add_argument("--summary", type=Path, default=Path("data/spark/bigquery_load_summary.json"))
    args = parser.parse_args()

    plan = preflight(args.spark_dir)
    if args.upload:
        if not args.project:
            parser.error("--upload requires --project YOUR_PROJECT_ID")
        result = upload(plan, project=args.project, dataset=args.dataset, location=args.location)
    else:
        result = plan
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
