# Airflow 3 orchestration: PySpark -> quality gate -> optional BigQuery

Local portfolio demo only. Existing `dags/finops_daily_pipeline.py` and `compose.yaml` remain unchanged. The new DAG is **manual** (`schedule=None`), uses the existing synthetic inputs, and writes Spark outputs to `data/spark_airflow/` (not the existing `data/spark/` directory). Its `upload_to_bigquery` parameter defaults to `false`. It does not publish to Google Cloud unless explicitly enabled for a DAG run.

## Extract / prepare

Run in WSL Ubuntu, from `/mnt/c/Users/uppal/projects/finops-starter`:

```bash
source ~/.venvs/finops-spark/bin/activate
# Back up the existing Dockerfile before unzipping (the archive replaces Dockerfile.airflow).
cp Dockerfile.airflow /tmp/Dockerfile.airflow.before-spark
unzip -o /mnt/c/Users/uppal/Downloads/finops_phase4_airflow_bigquery_upgrade.zip -d .
# Keep generated Spark outputs and all credential material out of Git.
grep -qxF 'data/spark_airflow/' .gitignore || printf '\ndata/spark_airflow/\n' >> .gitignore
```

## Offline / no credentials test first

```bash
docker compose up -d --build
# The first build can take some time because PySpark is large.
docker compose exec airflow /bin/bash -lc '/opt/finops_venv/bin/python -c "import pyspark; from google.cloud import bigquery; print(pyspark.__version__)"'
docker compose exec airflow /bin/bash -lc 'java -version'
docker compose exec airflow /bin/bash -lc 'airflow dags list-import-errors'
docker compose exec airflow /bin/bash -lc 'airflow dags list'
```

Open http://localhost:8080 and manually trigger **finops_spark_bigquery_pipeline** with default `upload_to_bigquery=false`. Expect tasks `check_synthetic_sources`, `transform_with_pyspark`, `enforce_quality_gate`, `bigquery_preflight`, and `publish_to_bigquery_if_enabled` to succeed, with the last reporting that upload was skipped. The quality-gate reports are in `data/spark_airflow/`.

Airflow logs for the newest run should show a billing reconciliation of `$4,434.39` for the known clean 30-day synthetic sample. If your inputs have been regenerated with different options, counts and total may differ; the reconciliation must still pass.

## Optional: enable explicit BigQuery publishing

The overlay mounts an existing local **Application Default Credentials** JSON file into the container **read-only**. The file is sensitive: never commit it or copy it into the Git repository or Docker image. Review permissions before sharing this machine. For a managed deployment, prefer workload identity rather than mounting personal credentials.

The Airflow container runs as Unix UID 50000. If it cannot read the mounted file, grant that UID read access using an ACL rather than making the credentials world-readable:

```bash
sudo apt-get install -y acl
setfacl -m u:50000:r "$HOME/.config/gcloud/application_default_credentials.json"
```

Then run **from WSL Ubuntu** (so `${HOME}` refers to `/home/sharmila`):

```bash
export FINOPS_BQ_PROJECT=finops-cloud-intelligence-2026
export FINOPS_BQ_DATASET=finops_demo
docker compose -f compose.yaml -f compose.bigquery.yaml up -d --build
docker compose -f compose.yaml -f compose.bigquery.yaml exec airflow /bin/bash -lc 'test -r "$GOOGLE_APPLICATION_CREDENTIALS" && echo "ADC mount readable"'
```

The project already has a successful manually executed BigQuery load into `finops_demo`. In Airflow, trigger **finops_spark_bigquery_pipeline** and explicitly set `upload_to_bigquery=true` (or trigger via the CLI using `--conf '{"upload_to_bigquery": true}'`). The upload uses `WRITE_TRUNCATE` on just the two synthetic demo tables, and verifies row counts and cost reconciliation.

Check BigQuery `finops_demo.billing_daily` and `finops_demo.app_daily` after success. BigQuery usage can incur charges; verify billing limits before uploading. Never enable automatic scheduling for cloud publishing without updating the design.

## Diagnostic commands

```bash
docker compose exec airflow /bin/bash -lc 'airflow dags list-import-errors'
docker compose logs airflow --tail 100
# For overlay version:
docker compose -f compose.yaml -f compose.bigquery.yaml ps
```

## Git commit after a successful local run

```bash
git add Dockerfile.airflow dags/finops_spark_bigquery_pipeline.py compose.bigquery.yaml docs/AIRFLOW-SPARK-BIGQUERY.md .gitignore
git status
git commit -m 'Orchestrate PySpark, validation, and optional BigQuery publishing with Airflow'
git push origin main
```

Keep generated Parquet datasets, authentication credentials, and cloud tokens out of Git.
