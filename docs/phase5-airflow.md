# Phase 5: Apache Airflow Orchestration

## Purpose

Schedule the existing Phase 2 ingestion, Phase 3/4 dbt warehouse and financial
reconciliation checks as an observable, retryable workflow. This is an
intentionally local **portfolio** environment, not a PlayStation or Sony system.
The CSV data is simulated and must not be represented as live usage data.

## Workflow graph

```text
check_sources
    -> ingest_to_duckdb
    -> check_ingestion_audit
    -> build_and_test_dbt
    -> verify_cost_reconciliation
    -> write_finops_report
```

- `check_sources`: Fail if any CSV source missing, empty, or schema changed.
- `ingest_to_duckdb`: Calls the existing transactional Python loader.
- `check_ingestion_audit`: Fails the workflow if records were quarantined,
  counts disagree, or source billing cannot be fully reconciled.
- `build_and_test_dbt`: Runs ALL dbt models and 49 Phase 4 dbt tests.
- `verify_cost_reconciliation`: Reuses Phase 4 total and daily dollar checks.
- `write_finops_report`: Creates `reports/latest_finops_report.txt` atomically.

## Requirements

- Windows 11, VS Code + Git Bash, Docker Desktop with WSL 2 backend enabled.
- Docker Compose v2, at least 4 GB allocated to Docker (more helps).
- Existing Phase 4 repository with raw CSV files in `data/raw`.
- Port 8080 unused (otherwise update host port in `compose.yaml`).
- Internet connection for the first Docker image build.

## Quick start

From the existing repository root:

```bash
docker --version
docker compose version
python -m pytest -q
python -m finops.orchestration check-sources
docker compose build
docker compose up -d
docker compose ps
docker compose logs airflow --tail 120
```

Airflow 3 standalone creates an admin password. Look for a line in the
container logs beginning `Simple auth manager | Password for user 'admin'`.
Then visit <http://localhost:8080> and log in with `admin` and that password.
The UI may take a minute or two to initialize on first boot.

Turn on the paused DAG `finops_daily_cost_pipeline`, then click **Trigger**
to create an on-demand run. The configured recurring schedule is 06:00 UTC
daily with `catchup=False`. Airflow stores task attempts and logs.

Verify the DAG is discoverable:

```bash
docker compose exec airflow airflow dags list
```

After a successful on-demand DAG run:

```bash
cat reports/latest_finops_report.txt
docker compose exec airflow /opt/finops_venv/bin/python -m finops.orchestration check-ingestion
```

For the 30-day seed-42 synthetic data, the final financial totals should
reconcile to $4,434.39 and shared spending of $484.02.

## Failure drills

1. **Missing source**: Temporarily rename `data/raw/billing.csv`, trigger a
   new DAG run, and verify `check_sources` fails. Restore the file.
2. **Invalid financial record**: In a **copy** of the source data (back up
   `billing.csv` first), insert a negative cost and run again. Ingestion
   may quarantine it, but the `check_ingestion_audit` stage must fail.
   Restore the clean file and trigger again.
3. **Retry visibility**: See Airflow's task instance history/logs after a
   failure. This DAG uses two retries with a two-minute delay.

Do not run local `dbt build` or `ingest` simultaneously with an Airflow DAG
run, since DuckDB permits only one writer to the same database file.
Only one DAG run is active at a time (`max_active_runs=1`).

## Notes and limitations

- Airflow 3 uses Python 3.12 **inside Docker**, so the existing host
  Python 3.14 virtual environment remains unchanged.
- Standalone uses development defaults and is **not hardened**. Keep the
  service on localhost and do not expose it publicly.
- The DAG does **not** generate new synthetic data each day. It processes
  whatever CSV files are present. With unchanged inputs, daily runs produce
  identical financial results. A real schedule would be fed by periodic
  AWS CUR exports, OpenCost metrics, and product usage sources.
- The project code is mounted at `/opt/finops`; DuckDB is shared with the
  host project under `data/warehouse`. This is fine for demos but isn't a
  production concurrency strategy.
- Airflow state is stored in the `airflow_state` Docker named volume;
  stopping containers via `docker compose down` preserves it.
- To stop: `docker compose down`.
- Don't use `docker compose down -v` unless you intentionally want to
  erase stored Airflow run history and users.

## Github deliverables

Commit: DAG source, Dockerfile, compose.yaml, orchestration safety gates,
tests, this document, and screenshots of the Airflow DAG graph plus a
successful run. Do not commit credentials, the local DuckDB file, or
generated reports. The existing GitHub CI runs Phase 5 host-side tests
together with dbt tests; Airflow end-to-end validation is performed locally.
