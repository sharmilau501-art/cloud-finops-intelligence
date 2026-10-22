# Cloud Infrastructure Cost Intelligence & FinOps Analytics Platform

**Portfolio project**: simulated infrastructure cost, resource utilization, and product usage. Not PlayStation, Sony, or actual AWS account data.

## Milestones
1. Generate reproducible synthetic input datasets and test them.
2. Ingestion, validation, reconciliation, and quarantine in DuckDB.
3. dbt staging/marts and tests.
4. FinOps cost allocation and unit economics.
5. Airflow scheduling and observability.
6. Power BI dashboards and forecasts.
7. Snowflake RAW ingestion, dbt cloud warehouse modeling, financial reconciliation, and portfolio documentation.

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
- Currency is simulated USD; The dataset includes shared platform charges, which are allocated to consuming applications during Phase 4 using the project's shared-cost allocation model.

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

## Power BI Dashboards & Cost Forecasting

Business objective: Analyze cloud infrastructure costs, shared-cost allocation, application unit economics, Kubernetes utilization, and short-term spending trends.



Reporting: Four Power BI dashboard pages using reproducible synthetic data.



Forecasting: Seven-day trailing-average baseline with rolling-origin backtesting.



Evaluation: MAE and WAPE compared against a last-observation naive forecast. Record the actual results from forecast_backtest.csv, including applications where naive performed better.



Limitations: Only 30 days of synthetic historical data; review flags and forecasts do not establish real production savings or calibrated uncertainty.

## End-to-End Platform Overview

The **Cloud Infrastructure Cost Intelligence & FinOps Analytics Platform** is an end-to-end data engineering portfolio project designed to analyze cloud infrastructure spending, resource utilization, application-level cost allocation, and short-term cost trends.

The platform integrates **Python, SQL, DuckDB, Snowflake, dbt, Apache Airflow, Docker, Power BI, and statistical forecasting** to demonstrate a reproducible analytics workflow.

### Business Problem

Cloud infrastructure costs can be difficult to attribute accurately when multiple applications share computing resources. Infrastructure, finance, and engineering teams need reliable information to understand spending patterns, measure application efficiency, and identify opportunities for further investigation.

This project addresses these challenges by:

- Consolidating synthetic cloud billing, Kubernetes telemetry, and product usage datasets.
- Validating source data and reconciling financial totals throughout the pipeline.
- Allocating shared infrastructure costs to individual applications.
- Calculating application-level cost and cost per 1,000 product requests.
- Identifying unusual cost days and low-resource-utilization patterns for review.
- Visualizing infrastructure costs and application economics through Power BI.
- Generating seven-day cost forecasts and evaluating forecast accuracy.
- Supporting both a local DuckDB warehouse and a Snowflake cloud data warehouse.

## Technology Stack

| Category | Technologies |
|---|---|
| Programming | Python, SQL |
| Data generation and validation | Python, pandas, pytest |
| Local analytical database | DuckDB |
| Cloud data warehouse | Snowflake |
| Data transformations | dbt Core, dbt-duckdb, dbt-snowflake |
| Pipeline orchestration | Apache Airflow |
| Containers | Docker, Docker Compose |
| Business intelligence | Power BI, DAX |
| Forecasting | Seven-day trailing-mean baseline, rolling-origin backtesting |
| Version control | Git, GitHub |

## Data Architecture

The platform supports two analytical environments.

**Local analytical pipeline**

Synthetic Data Generation → Python Validation & Ingestion → DuckDB RAW Tables → dbt Transformations & Tests → FinOps Analytical Models → Power BI CSV Exports → Dashboards & Forecasting

**Cloud analytical pipeline**

Synthetic Source CSVs → Python Snowflake Loader → Snowflake RAW Schema → dbt Snowflake Models & Tests → Snowflake ANALYTICS Schema → Financial Reconciliation

**Orchestration:** Apache Airflow coordinates the local ingestion, validation, dbt transformation, reconciliation, and reporting workflow. The Snowflake loading and dbt execution paths are also available as separately executable commands.

## Dataset Overview

The project uses reproducible synthetic infrastructure and product usage data spanning 30 days.

| Dataset | Description | Records |
|---|---|---:|
| Cloud billing | Infrastructure charges across applications and shared resources | 120 |
| Kubernetes metrics | Daily CPU and memory utilization snapshots | 90 |
| Product usage | Application request volumes and active-user metrics | 90 |
| **Total** | **Validated synthetic records** | **300** |

Applications represented in the data include `catalog`, `checkout`, and `streaming`, together with a shared infrastructure cost pool.

All source values are simulated. No production customer information, PlayStation operational data, or actual AWS billing exports are used.

## Data Engineering Implementation

### Phase 1: Synthetic Data Generation

- Developed reproducible data generators with Python.
- Created simulated cloud billing, Kubernetes utilization, and product usage datasets.
- Implemented automated unit tests for generated data integrity.
- Used deterministic generation to support repeatable validation.

### Phase 2: Data Ingestion and Quality Validation

- Built Python ingestion workflows using DuckDB.
- Implemented schema validation, data-quality checks, and rejected-record quarantine.
- Maintained ingestion audit information.
- Reconciled source billing amounts against ingested warehouse amounts.
- Designed ingestion to avoid duplicate active records during repeat execution.

### Phase 3: Dimensional Modeling with dbt

- Created staging and analytical models using dbt.
- Implemented SQL-based transformations for infrastructure spending, application usage, and cost reporting.
- Added data-quality tests to verify analytical model integrity.
- Built reusable models for downstream FinOps calculations.

### Phase 4: Shared-Cost Allocation and FinOps Analytics

- Implemented shared infrastructure cost allocation across consuming applications.
- Calculated direct costs, allocated shared costs, and fully loaded application costs.
- Developed application unit-economics metrics based on product request volume.
- Generated review flags for low-resource utilization and unusual infrastructure spending.
- Verified that allocated application costs reconcile to the original billing total.

### Phase 5: Apache Airflow Orchestration

- Containerized Apache Airflow using Docker.
- Developed a multi-task pipeline for validation, ingestion, dbt transformation, reconciliation, and reporting.
- Executed the workflow through the Airflow user interface.
- Added automated testing and pipeline execution documentation.

### Phase 6: Power BI Reporting and Forecasting

Developed a four-page Power BI report covering:

1. **Infrastructure Cost Overview:** Total spending, direct and allocated shared costs, application spending, and daily cost trends.
2. **Application Economics:** Product request volume, fully loaded application costs, and unit-cost comparisons.
3. **Kubernetes Efficiency & Anomaly Review:** CPU and memory utilization, low-utilization review flags, and unusual cost-day signals.
4. **Seven-Day Cost Outlook:** Historical spending, future cost baseline, and forecast evaluation metrics.

**Forecasting methodology**

- Generated seven-day forecasts using a trailing-mean baseline.
- Evaluated one-day-ahead predictions using rolling-origin backtesting.
- Measured forecast performance using Mean Absolute Error (MAE) and Weighted Absolute Percentage Error (WAPE).
- Compared predictions against a last-observation naive baseline.

The forecasting approach is intentionally simple and interpretable. It does not represent a production-trained machine learning system or provide calibrated prediction intervals.

### Phase 7: Snowflake Cloud Data Warehouse Integration

Extended the existing local platform with Snowflake.

**Snowflake environment**

| Component | Name |
|---|---|
| Virtual warehouse | `FINOPS_WH` |
| Database | `FINOPS_DB` |
| Source schema | `RAW` |
| Analytics schema | `ANALYTICS` |

**Implementation highlights**

- Established a Python connection to Snowflake using the Snowflake Connector for Python.
- Loaded synthetic billing, Kubernetes, and product usage datasets into Snowflake RAW tables.
- Verified source-to-Snowflake record counts and financial totals.
- Integrated dbt-snowflake as a separate transformation target.
- Retained the existing DuckDB configuration for local development.
- Executed Snowflake dbt transformations and automated data tests.
- Configured Snowflake connections using environment variables rather than hardcoded credentials.

**Validated Snowflake RAW ingestion results**

| Table | Records |
|---|---:|
| `FINOPS_DB.RAW.BILLING` | 120 |
| `FINOPS_DB.RAW.K8S_METRICS` | 90 |
| `FINOPS_DB.RAW.PRODUCT_USAGE` | 90 |
| **Total** | **300** |

The Snowflake ingestion process successfully reconciled the source billing total of **$4,434.39**.

## Financial Reconciliation and Application Economics

The project demonstrates cost attribution across three consuming applications using synthetic financial data.

| Application | Direct cost | Allocated shared cost | Fully loaded cost |
|---|---:|---:|---:|
| Catalog | $1,176.61 | $151.40 | $1,328.01 |
| Checkout | $2,011.52 | $173.50 | $2,185.02 |
| Streaming | $762.24 | $159.12 | $921.36 |
| **Total** | **$3,950.37** | **$484.02** | **$4,434.39** |

**Financial validation**

- Original billed cost: **$4,434.39**
- Shared infrastructure costs allocated: **$484.02**
- Fully loaded application costs: **$4,434.39**
- Reconciliation difference: **$0.00**

The model attributes 100% of the synthetic shared infrastructure cost pool to consuming applications under the project's allocation methodology.

## Resource Efficiency and Anomaly Review

The analytical pipeline generated:

- Two low-utilization review signals.
- Two unusual cost-day review signals.

These indicators are intended to support engineering investigation. They are not confirmed infrastructure faults, production incidents, or verified opportunities for cost reduction.

## Power BI Deliverable

The Power BI project is available in:

`dashboards/FinOps_Infrastructure_Intelligence.pbix`

The report enables exploration of infrastructure spending, application-level cost attribution, Kubernetes utilization, product usage, and forecasting metrics.

Dashboard images are stored in `dashboards/screenshots/`.

## Running the Project

### Local Development

Create and activate a Python virtual environment, then install the dependencies from the repository.

Common project commands:

- `python -m finops.generate_data --days 30 --seed 42`
- `python -m finops.ingest --raw-dir data/raw --db data/warehouse/finops.duckdb`
- `dbt build --profiles-dir .`
- `python -m finops.phase4_report`
- `python -m finops.phase6_export --horizon 7`
- `python -m pytest -q`

### Snowflake Development

The Snowflake integration uses the same synthetic source datasets.

Common commands:

- `python -m finops.snowflake_load --dry-run`
- `python -m finops.snowflake_load --auth password`
- `dbt debug --profiles-dir config/snowflake --target snowflake`
- `dbt build --profiles-dir config/snowflake --target snowflake`

Snowflake account, username, role, and password settings must be configured appropriately before execution. Passwords and access tokens must never be committed to the repository.

The Snowflake virtual warehouse should be suspended when not in use to reduce unnecessary compute consumption.

## Testing and Reliability

The project incorporates multiple layers of validation:

- Python unit testing with pytest.
- Source schema and data-quality checks.
- Rejected-record handling and ingestion auditing.
- dbt model and relationship testing.
- Source-to-warehouse billing reconciliation.
- Shared-cost allocation reconciliation.
- Forecast backtesting against a naive baseline.
- Local pipeline orchestration verification using Apache Airflow.

## Project Outcomes

This project demonstrates the ability to:

- Design and implement reproducible end-to-end data engineering pipelines.
- Develop and validate data ingestion workflows.
- Build dimensional analytical models with dbt.
- Work with both local and cloud data warehouses.
- Implement financial reconciliation and business-oriented data-quality controls.
- Orchestrate workflows using Apache Airflow and Docker.
- Translate infrastructure and application telemetry into cost and efficiency metrics.
- Develop Power BI dashboards that support technical and financial analysis.
- Evaluate statistical forecasting baselines using measurable error metrics.

## Limitations and Future Enhancements

This is a technical portfolio project using synthetic data. It is not affiliated with Sony Interactive Entertainment, PlayStation, or any cloud service provider.

The current implementation does not demonstrate actual production infrastructure savings. Utilization and anomaly flags require investigation before operational action.

Possible extensions include integrating authorized real cloud billing exports, OpenCost or Kubernetes telemetry, more sophisticated forecasting approaches, production alerting, and automated cloud deployment pipelines.