"""Quality gate for the existing synthetic FinOps PySpark JSON quality report.

Fails the build on missing/invalid metrics, missing joined records, or a
billing reconciliation mismatch. Run after ``finops.spark_transform``.
"""
from __future__ import annotations

import argparse
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

SOURCE_KEYS = ("billing", "k8s_metrics", "product_usage")
OUTPUT_KEYS = ("billing_daily", "app_daily")
COST_KEYS = (
    "source_billed_usd",
    "modeled_billed_usd",
    "direct_billed_usd",
    "shared_billed_usd",
)


def assess_report(report: Any) -> list[str]:
    """Return human-readable gate failures, or an empty list for a pass."""
    if not isinstance(report, dict):
        return ["Quality report must be a JSON object"]

    failures: list[str] = []
    counts: dict[str, int] = {}
    for section, keys in (("source_counts", SOURCE_KEYS), ("output_counts", OUTPUT_KEYS)):
        entries = report.get(section)
        if not isinstance(entries, dict):
            failures.append(f"Missing or invalid {section}")
            continue
        for key in keys:
            value = entries.get(key)
            label = f"{section}.{key}"
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                failures.append(f"{label} must be a positive integer")
            else:
                counts[label] = value

    def count(section: str, name: str) -> int | None:
        return counts.get(f"{section}.{name}")

    billed_input = count("source_counts", "billing")
    billed_output = count("output_counts", "billing_daily")
    if billed_input is not None and billed_output is not None and billed_output > billed_input:
        failures.append("billing_daily cannot exceed raw billing row count")

    app_output = count("output_counts", "app_daily")
    for source in ("k8s_metrics", "product_usage"):
        source_count = count("source_counts", source)
        if source_count is not None and app_output is not None and app_output != source_count:
            failures.append(f"app_daily={app_output} does not match {source}={source_count}; records may be lost")

    amounts: dict[str, Decimal] = {}
    for key in COST_KEYS:
        value = report.get(key)
        try:
            if isinstance(value, bool) or value is None:
                raise InvalidOperation
            amount = Decimal(str(value))
            if not amount.is_finite() or amount < 0:
                raise InvalidOperation
            amounts[key] = amount
        except (InvalidOperation, ValueError):
            failures.append(f"{key} must be a nonnegative finite amount")

    if all(key in amounts for key in COST_KEYS):
        if amounts["source_billed_usd"] != amounts["modeled_billed_usd"]:
            failures.append("Source billed cost differs from modeled billed cost")
        if amounts["source_billed_usd"] != amounts["direct_billed_usd"] + amounts["shared_billed_usd"]:
            failures.append("Direct plus shared cost does not reconcile to source")

    if report.get("reconciled") is not True:
        failures.append("Pipeline did not report reconciled=true")

    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate PySpark data quality and financial reconciliation")
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    args = parser.parse_args()

    report: Any = None
    try:
        report = json.loads(args.report.read_text(encoding="utf-8"))
        failures = assess_report(report)
    except (OSError, ValueError) as exc:
        failures = [f"Could not read quality report: {exc}"]

    summary = {
        "status": "PASS" if not failures else "FAIL",
        "source_report": str(args.report),
        "failures": failures,
        "source_counts": report.get("source_counts") if isinstance(report, dict) else None,
        "output_counts": report.get("output_counts") if isinstance(report, dict) else None,
        "source_billed_usd": report.get("source_billed_usd") if isinstance(report, dict) else None,
        "modeled_billed_usd": report.get("modeled_billed_usd") if isinstance(report, dict) else None,
    }
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
