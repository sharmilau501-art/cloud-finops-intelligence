"""Execute after installing requirements-spark.txt and Java 17+."""
from __future__ import annotations

import csv
from decimal import Decimal

import pytest

pytest.importorskip("pyspark")

from finops.generate_data import generate
from finops.spark_transform import make_spark, transform


@pytest.fixture(scope="session")
def spark():
    session = make_spark()
    yield session
    session.stop()


def test_output_counts_and_billing_reconciliation(tmp_path, spark):
    raw = tmp_path / "raw"
    generate(raw, days=30, seed=42)
    report = transform(raw, tmp_path / "spark", spark)
    assert report["source_counts"] == {
        "billing": 120,
        "k8s_metrics": 90,
        "product_usage": 90,
    }
    assert report["output_counts"] == {"billing_daily": 120, "app_daily": 90}
    assert report["reconciled"] is True
    with (raw / "billing.csv").open(newline="", encoding="utf-8") as stream:
        source_cost = sum(
            (Decimal(row["unblended_cost_usd"]) for row in csv.DictReader(stream)),
            Decimal("0.00"),
        )
    assert Decimal(report["modeled_billed_usd"]) == source_cost
    assert Decimal(report["direct_billed_usd"]) + Decimal(report["shared_billed_usd"]) == source_cost
    assert (tmp_path / "spark" / "app_daily").is_dir()
    assert (tmp_path / "spark" / "billing_daily").is_dir()
    assert (tmp_path / "spark" / "quality_metrics.json").is_file()


def test_duplicate_billing_line_item_rejected(tmp_path, spark):
    raw = tmp_path / "raw"
    generate(raw)
    file = raw / "billing.csv"
    with file.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    with file.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows([*rows, rows[0]])
    with pytest.raises(ValueError, match="Duplicate billing"):
        transform(raw, tmp_path / "spark", spark)


def test_missing_usage_record_rejected(tmp_path, spark):
    raw = tmp_path / "raw"
    generate(raw)
    file = raw / "product_usage.csv"
    with file.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    with file.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows[1:])
    with pytest.raises(ValueError, match="missing from product_usage"):
        transform(raw, tmp_path / "spark", spark)
