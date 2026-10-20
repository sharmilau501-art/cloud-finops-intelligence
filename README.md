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
