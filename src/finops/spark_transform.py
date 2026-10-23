"""Independent PySpark analytics layer for the existing synthetic FinOps CSVs.

Does NOT change the existing DuckDB ingestion, dbt, or Power BI outputs.
Run: python -m finops.spark_transform --raw-dir data/raw --out-dir data/spark
"""
from __future__ import annotations

import argparse
import json
import os
from decimal import Decimal
from pathlib import Path

# Helps Spark start on machines with VPNs / ambiguous loopback hostnames.
os.environ.setdefault("SPARK_LOCAL_IP", "127.0.0.1")

from pyspark.sql import DataFrame, SparkSession, functions as F
from pyspark.sql.types import (
    DateType,
    DecimalType,
    DoubleType,
    LongType,
    StringType,
    StructField,
    StructType,
)

BILLING_SCHEMA = StructType([
    StructField("usage_date", DateType()),
    StructField("line_item_id", StringType()),
    StructField("line_item_product_code", StringType()),
    StructField("resource_id", StringType()),
    StructField("application", StringType()),
    StructField("team", StringType()),
    StructField("cost_category", StringType()),
    StructField("unblended_cost_usd", DecimalType(18, 2)),
    StructField("usage_quantity", DoubleType()),
    StructField("usage_unit", StringType()),
])
K8S_SCHEMA = StructType([
    StructField("usage_date", DateType()),
    StructField("application", StringType()),
    StructField("namespace", StringType()),
    StructField("cpu_utilization_pct", DoubleType()),
    StructField("memory_utilization_pct", DoubleType()),
    StructField("requested_cpu_cores", DoubleType()),
    StructField("requested_memory_gib", DoubleType()),
])
USAGE_SCHEMA = StructType([
    StructField("usage_date", DateType()),
    StructField("application", StringType()),
    StructField("product_requests", LongType()),
    StructField("active_users", LongType()),
])


def _uri(path: Path) -> str:
    return Path(path).resolve().as_uri()


def make_spark() -> SparkSession:
    return (
        SparkSession.builder.master("local[2]")
        .appName("finops-pyspark-upgrade")
        .config("spark.sql.shuffle.partitions", "2")
        .config("spark.ui.enabled", "false")
        .getOrCreate()
    )


def _load(spark: SparkSession, path: Path, schema: StructType) -> DataFrame:
    if not path.is_file():
        raise FileNotFoundError(f"Missing input: {path}. Generate data first.")
    return (
        spark.read.schema(schema)
        .option("header", "true")
        .option("enforceSchema", "false")
        .option("mode", "FAILFAST")
        .csv(_uri(path))
    )


def _assert_no_duplicates(df: DataFrame, key: list[str], dataset: str) -> None:
    if df.groupBy(*key).count().where(F.col("count") > 1).limit(1).count():
        raise ValueError(f"Duplicate {dataset} key(s): {', '.join(key)}")


def _assert_valid(df: DataFrame, rule, message: str) -> None:
    if df.where(rule).limit(1).count():
        raise ValueError(message)


def _total(df: DataFrame, column: str) -> Decimal:
    value = df.agg(F.sum(F.col(column)).alias("total")).first()["total"]
    return Decimal(str(value or 0)).quantize(Decimal("0.01"))


def transform(raw_dir: Path, out_dir: Path, spark: SparkSession) -> dict:
    """Validate joins, build Parquet marts, and fail if billings don't reconcile."""
    raw_dir, out_dir = Path(raw_dir), Path(out_dir)
    billing = _load(spark, raw_dir / "billing.csv", BILLING_SCHEMA)
    k8s = _load(spark, raw_dir / "k8s_metrics.csv", K8S_SCHEMA)
    usage = _load(spark, raw_dir / "product_usage.csv", USAGE_SCHEMA)

    _assert_valid(
        billing,
        F.col("usage_date").isNull()
        | F.col("application").isNull()
        | F.col("team").isNull()
        | F.col("line_item_id").isNull()
        | F.col("unblended_cost_usd").isNull()
        | (F.col("unblended_cost_usd") < 0),
        "Invalid billing date, key, team, or cost",
    )
    _assert_valid(
        usage,
        F.col("usage_date").isNull()
        | F.col("application").isNull()
        | F.col("product_requests").isNull()
        | (F.col("product_requests") <= 0)
        | F.col("active_users").isNull()
        | (F.col("active_users") < 0),
        "Invalid product usage date/key/request count/users",
    )
    _assert_valid(
        k8s,
        F.col("usage_date").isNull()
        | F.col("application").isNull()
        | F.col("cpu_utilization_pct").isNull()
        | F.col("memory_utilization_pct").isNull()
        | ~F.col("cpu_utilization_pct").between(0, 100)
        | ~F.col("memory_utilization_pct").between(0, 100),
        "Invalid Kubernetes date/key/utilization",
    )
    _assert_no_duplicates(billing, ["line_item_id"], "billing")
    key = ["usage_date", "application"]
    _assert_no_duplicates(k8s, key, "Kubernetes")
    _assert_no_duplicates(usage, key, "product usage")

    billing_daily = (
        billing.groupBy("usage_date", "application", "team")
        .agg(F.sum("unblended_cost_usd").alias("billed_cost_usd"))
    )
    direct = billing_daily.where(F.col("application") != "shared")
    if direct.select(*key).join(usage.select(*key), key, "left_anti").limit(1).count():
        raise ValueError("Application/date missing from product_usage.csv")
    if direct.select(*key).join(k8s.select(*key), key, "left_anti").limit(1).count():
        raise ValueError("Application/date missing from k8s_metrics.csv")

    app_daily = (
        direct.join(usage, key, "inner")
        .join(k8s, key, "inner")
        .withColumn(
            "cost_per_1000_requests_usd",
            F.round(F.col("billed_cost_usd") * F.lit(1000) / F.col("product_requests"), 4),
        )
        .select(
            "usage_date", "application", "team", "billed_cost_usd",
            "product_requests", "active_users", "cpu_utilization_pct",
            "memory_utilization_pct", "cost_per_1000_requests_usd",
        )
    )

    source_total = _total(billing, "unblended_cost_usd")
    result_total = _total(billing_daily, "billed_cost_usd")
    direct_total = _total(direct, "billed_cost_usd")
    shared_total = _total(billing_daily.where(F.col("application") == "shared"), "billed_cost_usd")
    if source_total != result_total or source_total != direct_total + shared_total:
        raise AssertionError("Billing reconciliation FAILED")

    input_counts = {
        "billing": billing.count(),
        "k8s_metrics": k8s.count(),
        "product_usage": usage.count(),
    }
    output_counts = {
        "billing_daily": billing_daily.count(),
        "app_daily": app_daily.count(),
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    billing_daily.write.mode("overwrite").parquet(_uri(out_dir / "billing_daily"))
    app_daily.write.mode("overwrite").parquet(_uri(out_dir / "app_daily"))
    report = {
        "source_counts": input_counts,
        "output_counts": output_counts,
        "source_billed_usd": str(source_total),
        "modeled_billed_usd": str(result_total),
        "direct_billed_usd": str(direct_total),
        "shared_billed_usd": str(shared_total),
        "reconciled": True,
        "note": "Synthetic, direct-only application costs; shared cost is not allocated here.",
    }
    (out_dir / "quality_metrics.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="PySpark FinOps analytics upgrade")
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--out-dir", type=Path, default=Path("data/spark"))
    args = parser.parse_args()
    spark = make_spark()
    try:
        print(json.dumps(transform(args.raw_dir, args.out_dir, spark), indent=2))
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
