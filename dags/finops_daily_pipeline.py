"""Daily synthetic infrastructure-cost workflow (Airflow 3 task SDK).

Airflow is installed only inside Docker, not in the host Python 3.14 venv.
The source CSVs are external inputs: never regenerate them on a schedule.
"""
from datetime import timedelta

import pendulum
from airflow.sdk import dag
from airflow.providers.standard.operators.bash import BashOperator

ROOT = "/opt/finops"
PY = "/opt/finops_venv/bin/python"
DBT = "/opt/finops_venv/bin/dbt"


@dag(
    dag_id="finops_daily_cost_pipeline",
    description="Ingest, audit, transform, reconcile and report infrastructure costs",
    schedule="0 6 * * *",  # daily at 06:00 UTC
    start_date=pendulum.datetime(2026, 10, 1, tz="UTC"),
    catchup=False,
    max_active_runs=1,  # one writer to the DuckDB file at a time
    dagrun_timeout=timedelta(minutes=45),
    default_args={"retries": 2, "retry_delay": timedelta(minutes=2)},
    tags=["finops", "playstation-portfolio", "data-quality"],
)
def finops_pipeline():
    source_check = BashOperator(
        task_id="check_sources",
        cwd=ROOT,
        bash_command=f"{PY} -m finops.orchestration check-sources",
    )
    ingestion = BashOperator(
        task_id="ingest_to_duckdb",
        cwd=ROOT,
        bash_command=(
            f"{PY} -m finops.ingest --raw-dir data/raw "
            "--db data/warehouse/finops.duckdb"
        ),
    )
    ingestion_gate = BashOperator(
        task_id="check_ingestion_audit",
        cwd=ROOT,
        bash_command=f"{PY} -m finops.orchestration check-ingestion",
    )
    transformations = BashOperator(
        task_id="build_and_test_dbt",
        cwd=ROOT,
        bash_command=f"{DBT} build --profiles-dir .",
    )
    cost_reconciliation = BashOperator(
        task_id="verify_cost_reconciliation",
        cwd=ROOT,
        bash_command=f"{PY} -m finops.orchestration check-marts",
    )
    write_report = BashOperator(
        task_id="write_finops_report",
        cwd=ROOT,
        bash_command=(
            f"{PY} -m finops.orchestration write-report "
            "--output reports/latest_finops_report.txt"
        ),
    )
    source_check >> ingestion >> ingestion_gate >> transformations >> cost_reconciliation >> write_report

finops_pipeline()
