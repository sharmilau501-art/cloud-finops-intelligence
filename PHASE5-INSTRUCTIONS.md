# Phase 5 installation checklist

This ZIP is an **upgrade** for your existing `finops-starter` repository,
not a full replacement. Extract into the repository root and keep all
files from Phases 1–4. No existing files need to be overwritten.

**Prerequisite:** Docker Desktop (Windows 11) using the WSL 2 backend.
Airflow 3.1 runs with Python 3.12 **inside Docker**; continue to use the
current Python 3.14 venv for regular host commands.

```bash
# From ~/projects/finops-starter (main)
source .venv/Scripts/activate
cat .gitignore.phase5-additions.txt >> .gitignore
rm .gitignore.phase5-additions.txt
python -m pytest -q
python -m finops.orchestration check-sources
python -m finops.orchestration check-ingestion
python -m finops.orchestration check-marts
docker --version
docker compose version
docker compose build
docker compose up -d
docker compose logs airflow --tail 120
```

Open http://localhost:8080. The standalone instance prints an `admin`
password in its logs. Find `finops_daily_cost_pipeline`, enable it, and
manually trigger one run. Wait until the final task is green. Then:

```bash
cat reports/latest_finops_report.txt
python -m pytest -q
git status
git add .
git commit -m "Phase 5: Orchestrate FinOps pipeline with Apache Airflow"
git push origin main
```

Avoid simultaneous host-side DuckDB writes while the Airflow DAG runs.
A passing unit test suite alone is not proof of an Airflow runtime run.

See `docs/phase5-airflow.md` for troubleshooting and verification drills.
