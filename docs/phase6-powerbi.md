# Phase 6: Power BI dashboard and seven-day cost forecast

This is a portfolio demo using **synthetic data**. No input is from PlayStation,
AWS CUR billing, or a live Kubernetes cluster. Keep the synthetic-data label
visible in screenshots and README.

## Export from verified Phase 4 DuckDB marts

```bash
source .venv/Scripts/activate
python -m pytest -q
python -m finops.phase6_export --db data/warehouse/finops.duckdb --out data/powerbi --horizon 7
```

The exporter is intentionally **read-only**. It checks that fully allocated
costs reconcile to raw billing before writing any CSV outputs. If DuckDB says
the file is locked, wait for the Airflow DAG to finish; you can temporarily
`docker compose stop` and use `docker compose start` afterward.

Seven exported files:

| File | Grain | Intended use |
|---|---|---|
| `dim_application.csv` | One application | Application/team dimension, includes `shared` |
| `dim_date.csv` | One date, history + forecast horizon | Date dimension |
| `fact_cost_daily.csv` | One date × consuming application | Actual fully allocated charges and request counts |
| `fact_k8s_daily.csv` | One date × application | Sample utilization and review flags |
| `fact_anomalies_daily.csv` | One date × application | Cost anomaly review signals |
| `fact_forecast_daily.csv` | One future date × application | Forward seven-day illustrative forecast |
| `forecast_backtest.csv` | One application | Walk-forward diagnostics vs naive baseline |

**Avoid double counting.** Use `fact_cost_daily` as the *only* source for actual
spend KPIs. Other fact tables can have cost columns for context but do not sum
them into the actual-spend total. Never add shared-platform charges again: they
are already distributed to consumer applications in `fact_cost_daily`.

Expected base case (30-day Phase 1 synthetic dataset): 90 rows in each of the
three historical application-grain facts, 21 rows of application forecasts,
and $4,434.39 in total fully allocated actual charges.

## Build the Power BI semantic model

1. Open **Power BI Desktop** on Windows (do not use the Power BI web service
   or publish data to an organization without authorization).
2. **Get Data > Text/CSV** and import each file from `data/powerbi/`.
3. **Transform Data** and set `usage_date` and `forecast_origin_date` to Date.
   Set money to Fixed decimal number, product requests to Whole number,
   metrics to Decimal number, and review flags to True/False (Boolean).
4. In Model view, create these single-direction 1-to-many relationships:
   - `dim_date[usage_date]` → each fact's `[usage_date]`
   - `dim_application[application]` → each fact's `[application]`
   - Leave `forecast_backtest` standalone or link application when desired.
5. Mark `dim_date` as a date table with `usage_date`.
6. Create each measure separately from `dashboards/powerbi-measures.dax`.
7. Hide technical columns from Report view when helpful, and save the `.pbix`
   as `dashboards/FinOps_Infrastructure_Intelligence.pbix`.

**Date slicers:** Actual data covers observed dates only, whereas forecast data
covers seven future dates. An all-page date slicer restricted to historical dates
will hide the forecast card. Prefer an application slicer and page-specific date
filters for forecast vs historical charts.

## Recommended four pages

### Page 1: Infrastructure cost overview

- Cards: total fully allocated cost, direct cost, allocated shared cost,
  shared cost percentage.
- Line chart: date vs total actual allocated cost.
- Bar chart: application vs total allocated cost.
- Table: application, owning team, product requests, cost per 1,000 requests.

### Page 2: Application economics

- Cards: total requests, cost per 1,000 requests.
- Stacked bar: direct vs allocated shared cost per application.
- Line chart: cost per 1,000 requests by date and application.
- Slicer: application, team.

### Page 3: Kubernetes efficiency and anomaly review

- Scatter: sampled CPU vs sampled memory utilization (application as legend).
- Table: usage date, application, CPU%, memory%, review flag.
- Bar/line: prior-seven-observation average cost vs current fully loaded cost.
- Cards: count of low-utilization review flags and cost anomaly review flags.
- **Important:** These are review signals, not confirmed underutilization,
  production anomalies, or validated savings.

### Page 4: Seven-day cost outlook

- Line chart using `dim_date[usage_date]`, actual and forecast measures
  (the line will change from historical to future dates).
- Bar chart: projected seven-day total by application.
- Table: `forecast_backtest`, displaying WAPE and naive WAPE per app.
- Text box: "7-day trailing-mean baseline, 7-day rolling holdout. Synthetic
  data; future uncertainty is not calibrated."

## Forecasting methodology

`finops.forecasting` calculates a 7-day **trailing mean of actual daily fully
allocated spend** per application and repeats it for the next seven days.
It uses an expanding rolling-origin evaluation for the *last seven dates*:
each one-day-ahead prediction uses only previous observations, avoiding lookahead
bias. Reports mean absolute error (MAE) and weighted absolute percentage error
(WAPE), with a last-observation naive comparison. Only 30 historical samples are
available, so the results are illustrative. Do not call this a trained ML model
or a guaranteed forecast.

If the baseline performs worse than naive, mention that in your README rather
than concealing it.

## Portfolio deliverables

- `data/powerbi/*.csv`: reproducible synthetic dashboard snapshot.
- `dashboards/FinOps_Infrastructure_Intelligence.pbix`: Power BI project (created
  locally in Power BI Desktop; the ZIP does not include a fake `.pbix`).
- `dashboards/screenshots/`: clear screenshots of the four report pages.
- A README section explaining business question, architecture, forecasting
  baseline, data tests, artifacts, and limitations.
- GitHub commit such as `Phase 6: Add Power BI exports and cost forecasting`.

## Commands to rerun

```bash
python -m pytest -q
dbt build --profiles-dir .
python -m finops.phase4_report
python -m finops.phase6_export --horizon 7
git status
git add .
git commit -m "Phase 6: Add Power BI exports and 7-day cost forecasting"
git push origin main
```
