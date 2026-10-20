# Cloud Infrastructure Cost Intelligence & FinOps Analytics Platform

**Portfolio project**: simulated infrastructure cost, resource utilization, and product usage. Not PlayStation, Sony, or actual AWS account data.

## Milestones
1. Generate reproducible synthetic input datasets and test them.
2. Ingestion, validation, reconciliation, and quarantine in DuckDB.
3. dbt staging/marts and tests.
4. FinOps cost allocation and unit economics.
5. Airflow scheduling and observability.
6. Power BI dashboards and forecasts.
7. Snowflake + optional real billing/OpenCost data, CI and portfolio polish.

## Phase 1 quick start (Windows Git Bash)
```bash
python -m venv .venv
source .venv/Scripts/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt -e .
python -m finops.generate_data --days 30 --seed 42
python -m pytest -q
```

Generated inputs appear in `data/raw/`.

## Synthetic dataset grain and assumptions
- `billing.csv`: one row per date and simulated application, including a shared platform charge (120 rows for 30 days). Illustrative AWS CUR-like fields, **not** an export of the real CUR 2.0 schema.
- `k8s_metrics.csv`: one daily snapshot per application except shared (90 rows). Simulated CPU/memory utilization.
- `product_usage.csv`: one daily application summary (90 rows). Simulated request counts and active users.
- Currency is simulated USD; the shared resource is intentionally unallocated for a later exercise. All numbers are fictitious. No actual AWS costs or services are incurred by this phase.

## Phase 2: Validate, ingest into DuckDB, and reconcile

Continue in the same Git repository, with the activated virtual environment.

```bash
python -m pip install -r requirements.txt -e .
python -m finops.generate_data --days 30 --seed 42
python -m finops.ingest --raw-dir data/raw --db data/warehouse/finops.duckdb
python -m finops.report --db data/warehouse/finops.duckdb
python -m pytest -q
```

**Expected clean sample:** 120 billing rows, 90 telemetry rows, 90 product-use rows; no quarantined records; billing reconciliation PASS.

Warehouse data is stored in `data/warehouse/finops.duckdb`, which is ignored by Git. `ingestion_quarantine` holds invalid rows from the latest successful run, with error explanations. `ingestion_audit` retains a per-dataset history for every successful run. Rerunning ingestion replaces active data rather than duplicating it.

The billing reconciliation compares parseable source amounts against accepted and quarantined amounts, and accepted amounts against what DuckDB actually stored. If cost itself cannot be parsed, reconciliation is marked **partial / review**, not PASS.

See [Phase 2 architecture and quality rules](docs/phase2-ingestion.md). All inputs and costs are synthetic. No cloud charges or credentials are needed.
