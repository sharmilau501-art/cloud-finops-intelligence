# Phase 2: CI and PySpark data-quality gate

## Purpose

Upgrade `.github/workflows/ci.yml` to execute Spark tests and the full synthetic
FinOps Spark pipeline on GitHub's Ubuntu runner. Previously the PySpark tests
could be skipped because `requirements-spark.txt` was not installed in CI.

## Workflow

1. Install Java 17, Python 3.11, project dependencies, and PySpark 4.2.0.
2. Verify PySpark imports successfully, so Spark tests cannot silently skip.
3. Run all Python tests (`python -m pytest tests/ -q`).
4. Generate deterministic 30-day synthetic data using seed 42.
5. Run Spark transformations, writing Parquet outputs and `quality_metrics.json`.
6. Apply the separate quality gate to the metrics JSON; fail CI on violations.
7. Upload both JSON reports to the GitHub Actions run for inspection (7-day retention).

## Local run in WSL Ubuntu

```bash
cd /mnt/c/Users/uppal/projects/finops-starter
source ~/.venvs/finops-spark/bin/activate
python -m pip install -r requirements.txt -r requirements-spark.txt -e .
python -m pytest tests/ -q
python -m finops.generate_data --days 30 --seed 42
python -m finops.spark_transform --raw-dir data/raw --out-dir data/spark
python -m finops.quality_gate \
  --report data/spark/quality_metrics.json \
  --summary data/spark/quality_gate_summary.json
```

The quality gate checks that count metrics are valid, application-level joins
have not silently lost source records, source and modeled billed amounts match,
`direct + shared = source`, and the pipeline reports reconciliation success.

## GitHub Actions inspection

Open **Actions** -> **FinOps CI and Data Quality** -> latest run. Expand the
steps to see the tests and full Spark output. Download the
`finops-quality-reports` run artifact to inspect the two JSON summaries.

## Security, scope, and limitations

All sample data is synthetic. This CI uses no cloud credentials or paid
services. It is a CI-based quality report, **not** a deployed, continuous
production monitoring or alerting system. The current Spark mart uses direct
application costs and intentionally does not allocate shared costs; that is
handled separately in existing FinOps warehouse models. Don't commit the
Parquet outputs or synthetic generated files unless intentionally required.
