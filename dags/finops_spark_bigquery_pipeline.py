"""Manual PySpark -> quality gate -> optional BigQuery portfolio workflow.

Original scheduled DAG (finops_daily_cost_pipeline) remains unmodified.
Uses only pre-existing synthetic CSVs: it never regenerates scheduled inputs.
An upload requires an explicit manual run with upload_to_bigquery=True.
"""
from datetime import timedelta

import pendulum
from airflow.sdk import Param, dag
from airflow.providers.standard.operators.bash import BashOperator

ROOT = "/opt/finops"
PY = "/opt/finops_venv/bin/python"
SPARK_OUT = "/opt/airflow/finops_spark_output"


@dag(
    dag_id="finops_spark_bigquery_pipeline",
    description="Manual synthetic FinOps Spark transform, quality gate, and optional BQ upload",
    schedule=None,
    start_date=pendulum.datetime(2026, 10, 1, tz="UTC"),
    catchup=False,
    max_active_runs=1,
    dagrun_timeout=timedelta(minutes=60),
    default_args={"retries": 0},  # no accidental repeated cloud overwrite
    params={"upload_to_bigquery": Param(False, type="boolean")},
    tags=["finops", "pyspark", "bigquery", "portfolio", "manual"],
)
def finops_spark_bigquery_pipeline():
    check = BashOperator(
        task_id="check_synthetic_sources",
        cwd=ROOT,
        bash_command="test -s data/raw/billing.csv && test -s data/raw/k8s_metrics.csv && test -s data/raw/product_usage.csv",
    )
    spark = BashOperator(
        task_id="transform_with_pyspark",
        cwd=ROOT,
        bash_command=f"{PY} -m finops.spark_transform --raw-dir data/raw --out-dir {SPARK_OUT}",
    )
    gate = BashOperator(
        task_id="enforce_quality_gate",
        cwd=ROOT,
        bash_command=(
            f"{PY} -m finops.quality_gate "
            f"--report {SPARK_OUT}/quality_metrics.json "
            f"--summary {SPARK_OUT}/quality_gate_summary.json"
        ),
    )
    dry_run = BashOperator(
        task_id="bigquery_preflight",
        cwd=ROOT,
        bash_command=(
            f"{PY} -m finops.bigquery_load --dry-run "
            f"--spark-dir {SPARK_OUT} "
            f"--summary {SPARK_OUT}/bigquery_preflight.json"
        ),
    )
    publish = BashOperator(
        task_id="publish_to_bigquery_if_enabled",
        cwd=ROOT,
        bash_command=(
            'set -euo pipefail\n'
            'case "{{ params.upload_to_bigquery }}" in\n'
            '  True|true)\n'
            '    test -r "$GOOGLE_APPLICATION_CREDENTIALS" || '
            '{ echo "No readable ADC mount; use the Compose BigQuery override" >&2; exit 1; }\n'
            '    : "${FINOPS_BQ_PROJECT:?Missing FINOPS_BQ_PROJECT}"\n'
            f'    {PY} -m finops.bigquery_load --upload '
            f'--spark-dir {SPARK_OUT} '
            '--project "$FINOPS_BQ_PROJECT" '
            '--dataset "${FINOPS_BQ_DATASET:-finops_demo}" '
            f'--location US --summary {SPARK_OUT}/bigquery_load_summary.json\n'
            '    ;;\n'
            '  *) echo "BigQuery upload skipped: upload_to_bigquery=false" ;;\n'
            'esac\n'
        ).replace("\\n", "\n"),
    )
    check >> spark >> gate >> dry_run >> publish


finops_spark_bigquery_pipeline()
