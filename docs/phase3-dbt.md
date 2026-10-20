# Phase 3: dbt transformations and dimensional modeling

This layer builds on Phase 2's validated DuckDB `main.billing`, `main.k8s_metrics`, and `main.product_usage` tables. Data is **synthetic**; nothing is obtained from Sony or an AWS account.

## Prerequisites
- Phase 2 ingestion succeeded (`python -m finops.report`).
- Python virtual environment is active. If your Python 3.14 environment has dbt installation issues, Python 3.12 is a reliable alternative.
- Run commands from **repository root** `~/projects/finops-starter` (not from inside `models`).
- Close Python tools or editors that hold an open DuckDB write connection before running dbt.

## Commands (Windows / Git Bash)
```bash
source .venv/Scripts/activate
python -m pip install -r requirements-phase3.txt
dbt --version
dbt debug --profiles-dir .
dbt build --profiles-dir .
python -m finops.analytics_report
python -m pytest -q
git status
```

`dbt build` creates the SQL views/tables in `analytics` and runs all dbt data tests. `dbt debug` confirms profile connectivity. Use `dbt docs generate --profiles-dir .` for generated lineage metadata. On local machines with an open database connection, close the program holding `finops.duckdb` before trying again.

## Data models and grain
| Model | Type | Grain / definition |
| --- | --- | --- |
| `stg_billing` | View | individual billing line; normalized field names and types |
| `stg_k8s_metrics` | View | individual telemetry sample |
| `stg_product_usage` | View | individual daily usage summary |
| `dim_application` | Table | one application |
| `dim_date` | Table | one observed date |
| `fct_billing_daily` | Table | one day, application, and owning team, USD charge |
| `fct_k8s_daily` | Table | one day/application; simple telemetry sample averages |
| `fct_product_usage_daily` | Table | one day/application; summed requests and simulated users |
| `mart_unit_economics_daily` | Table | one day/application; direct billing and per-1,000-request ratio |

All are under `analytics` schema in the **same** `finops.duckdb` file. Phase 2 inputs remain under `main`.

## Metric definitions and limitations
- **Billed cost** = sum of raw `unblended_cost_usd`, including the `shared` platform resource. The daily reconciliation test must match raw totals at the cent.
- **Direct cost** = an application's own billing charges; does not include shared-network costs. Not a fully-loaded cost.
- **Direct cost per 1k requests** = 1,000 × direct cost / application requests, NULL if requests zero. This is not PlayStation production unit economics.
- **CPU and memory utilization** = average of simulated daily samples; not weighted by time, requested resources, or cluster size.
- **Active users** = the generator's per-application daily counters, added across rows. Real distinct users require different source data / rules.
- All sources must be fully ingested before running dbt, and fact model uniqueness is enforced for the synthetic generator's expected grain.
- **Phase 4** adds robust shared-cost allocation and cost-per-workload accounting. Shared cost intentionally remains unallocated here so we can prove no double counting.

## Data quality
- YAML checks: not-null keys, unique dimension keys, relationship between facts and dimensions.
- SQL checks: fact uniqueness at expected grains, no negative costs/volumes, preservation of raw daily billing total, and prevention of silent shared-cost allocation.
- `dbt build` is the acceptance test for this phase. Phase 2 `pytest` suite remains separate.

## Expected records for 30 synthetic days
- `dim_application`: 4
- `dim_date`: 30
- `fct_billing_daily`: 120
- `fct_k8s_daily`: 90
- `fct_product_usage_daily`: 90
- `mart_unit_economics_daily`: 90
- Raw and modeled billed USD should both equal **$4,434.39** with seed 42; amount varies if data is regenerated with a different seed.

## Commit after passing tests
```bash
git add .
git commit -m "Phase 3: build dbt staging and warehouse marts"
git push origin main
```

The `target/`, `logs/`, and `dbt_packages/` artifacts should be excluded by your `.gitignore`. If the Phase 1 generated `*.egg-info` files are still tracked, remove those from Git's index using `git rm -r --cached src/cloud_finops_intelligence.egg-info` after adding that pattern to `.gitignore`.
