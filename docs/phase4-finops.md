# Phase 4: Shared cloud cost allocation, efficiency and anomaly checks

This phase extends Phase 3; it does not overwrite existing data, tests or models.
All data in this training repository are **synthetic**, not Sony/PlayStation or real AWS billing records.

## Run order

From the repository root, with the existing `.venv` activated:

```bash
python -m pytest -q
dbt debug --profiles-dir .
dbt build --profiles-dir .
python -m finops.analytics_report
python -m finops.phase4_report
```

If input files have been regenerated or the warehouse was deleted, run Phase 2 ingestion before `dbt build`:

```bash
python -m finops.generate_data --days 30 --seed 42
python -m finops.ingest --raw-dir data/raw --db data/warehouse/finops.duckdb
```

## Cost allocation policy

1. Keep each product application's direct costs unchanged.
2. Identify the daily shared-platform pool from `fct_billing_daily` where `application = 'shared'`.
3. Allocate the pool to consumer applications that have daily product usage. Use each application's share of daily API requests as a proxy for its consumption of shared services.
4. Perform a deterministic **largest remainder** distribution using integer cents: compute fractional quotas, take floors, then distribute leftover cents to the largest fractional remainders (tie: application name ascending). This guarantees that each day's shared allocation sums exactly to the shared charge.
5. If all application requests for a day are zero, use an **equal split** across the existing consumers on that day; flag the method with `equal_share_zero_requests`.
6. If a date has non-zero costs but no product-usage consumers, the dbt reconciliation test fails. Costs must not silently disappear.

This is an illustrative allocation methodology, **not** a claim about actual PlayStation pricing, Kubernetes usage-based attribution, or AWS tag policy. Application request volume is only a proxy for shared-cost consumption. In a production platform, select cost drivers per resource category and business agreement (CPU-hours, storage GB-hours, network bytes, etc.).

## Analytical marts and grains

| Model | Grain | Meaning |
|---|---|---|
| `fct_shared_cost_allocation_daily` | Date × consumer application | Direct, allocated shared, and fully loaded cost; cost/1,000 requests |
| `mart_k8s_efficiency_daily` | Date × application | Sampled CPU and memory percentages, requested resources, review flag |
| `mart_cost_anomalies_daily` | Date × application | Current cost vs. previous seven **observed** days and anomaly review flag |

Thresholds for prototype behavior:

- **Low utilization:** `cpu_utilization_pct < 25` AND `memory_utilization_pct < 35` on daily simulated telemetry snapshots. A flag means *review*, not verified waste or immediate action.
- **Anomaly:** current fully loaded cost is **strictly greater than 1.25 ×** the average of the previous seven observed daily costs for the same application, with at least seven prior observations. The first seven observations have no valid baseline and cannot be flagged.

The dbt variables can be overridden on the command line, for example:

```bash
dbt build --profiles-dir . --vars '{low_cpu_threshold_pct: 20, low_memory_threshold_pct: 30, cost_anomaly_ratio_threshold: 1.30}'
```

The example assumes a Bash-compatible shell; the single quoted YAML mapping is passed as one argument.

## Data quality guarantees

`dbt build` executes tests covering:

- Global cost reconciliation for **every billing date** (not merely grand totals).
- Shared pool allocation exact to the cent.
- Direct costs preserved from Phase 3.
- No duplicate application/date rows.
- No negative charges or request counts.
- Derived unit cost matches its numerator and denominator.
- No paid non-shared application silently missing from the allocation mart.
- Resource utilization review rows match allocation rows.
- Anomaly rows unique, and none flagged without sufficient history.
- Allocations within one cent of an exact request-share quota.

The new `tests/test_cost_allocation.py` independently tests deterministic cent handling in Python, including ties and zero-traffic fallback.

## Limitations (important for interviews)

- Billing, product activity and telemetry are synthetic. The generator has one bill line per service/day and one telemetry sample per app/day.
- Daily requests are a convenient *proxy*, not evidence that request-weighted shared allocation is always fair.
- K8s telemetry percentages are not time-weighted; a review flag does **not** estimate realizable savings.
- The anomaly detector is a simple 7-observation heuristic, not seasonality-adjusted detection or an incident investigation.
- No AWS CUR adapter, real Prometheus/OpenCost source, Snowflake migration, or orchestrator is included in Phase 4. Those remain later phases.

## Portfolio bullet after implementation and verification

> Built a dbt-based infrastructure cost allocation model over a DuckDB warehouse using synthetic billing, Kubernetes, and product-usage datasets; implemented deterministic cent-accurate shared-cost attribution, unit economics, utilization review flags, anomaly monitoring, and automated reconciliation tests.
