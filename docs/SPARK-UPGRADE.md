# Phase 1 extension: PySpark cost and usage analytics

Adds a standalone Spark job alongside the existing DuckDB/dbt/Power BI workflow. Does **not** overwrite your existing database or dashboard exports.

## Requirements

- Python 3.10+ (Python 3.14 is supported by PySpark 4.2.0)
- Java 17+ available on PATH, and `JAVA_HOME` set if required
- Your existing FinOps project virtual environment

## Setup (Windows Git Bash)

```bash
cd ~/projects/finops-starter
source .venv/Scripts/activate
python --version
java -version
python -m pip install -r requirements-spark.txt
python -m pip install -e .
```

## Run

```bash
python -m finops.generate_data --days 30 --seed 42
python -m finops.spark_transform --raw-dir data/raw --out-dir data/spark
python -m pytest tests/test_spark_transform.py -q
python -m pytest -q
```

Expected dataset sizes for the default synthetic data:
- Raw: 120 billing, 90 K8s metrics, 90 product usage records
- Output: 120 daily application billing rows (including shared), 90 application economics rows (excluding shared)
- `source_billed_usd` must equal `modeled_billed_usd`; shared + direct = total
- Existing default seed's billing total previously verified as $4,434.39, but trust the **current generated input** over any hard-coded amount.

Outputs (Parquet directories and JSON):

```
data/spark/billing_daily/
data/spark/app_daily/
data/spark/quality_metrics.json
```

Run `echo 'data/spark/' >> .gitignore` only if that rule (or a broader matching rule) does not already exist. Do not commit generated datasets. Do not commit credentials.

## Important design notes

- Spark runs in local mode (`local[2]`). This exercises the Spark API; it is **not** a distributed production cluster.
- Synthetic sample data is intentionally small, so do not describe it as production-scale.
- This job performs **direct-only** application unit economics; it preserves unallocated shared cost separately and does not replace the existing FinOps allocation model.
- Input validity and duplicate checks fail fast. The Spark output is independent of existing DuckDB source quarantine.
- Re-run the job to overwrite Spark Parquet outputs, not existing DuckDB/Power BI assets.
- The tests verify source-to-processed total and error handling; they need Java and PySpark installed to run.

## Git

```bash
git status
git add requirements-spark.txt src/finops/spark_transform.py tests/test_spark_transform.py docs/SPARK-UPGRADE.md
git commit -m "Add PySpark FinOps processing and reconciliation"
git push origin main
```

If you edited `.gitignore`, stage that file too before committing.
