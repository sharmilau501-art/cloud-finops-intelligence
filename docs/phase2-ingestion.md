# Phase 2: Ingestion, Validation and Reconciliation

## Goals

Create a reliable raw layer for an infrastructure economics analytics platform, using deterministic *synthetic* source records. Make data quality visible instead of silently dropping malformed values.

## Source contracts

| File | Grain | Natural key | Important rules |
|---|---|---|---|
| `billing.csv` | Per day and simulated application | `line_item_id` | Valid date, unique ID, valid nonnegative USD with at most two decimals, nonnegative usage quantity |
| `k8s_metrics.csv` | Daily application utilization | (`usage_date`, `application`) | CPU/memory utilization in [0, 100], positive requested capacity |
| `product_usage.csv` | Daily application traffic | (`usage_date`, `application`) | Nonnegative integer requests and active users |

Headers must match the expected schema exactly (including column order), so breaking source changes fail early rather than corrupting the warehouse.

## Warehouse tables

- `billing`: typed synthetic billing records, one per `line_item_id`.
- `k8s_metrics`: application-level daily utilization snapshots.
- `product_usage`: application-level daily traffic records.
- `ingestion_quarantine`: invalid raw rows from the **latest successful run** with dataset, original CSV line, raw JSON, and validation errors.
- `ingestion_audit`: append-only history, one record per dataset per successful ingestion run, identified by UUID.

All three sources are checked before changing the database. On success, a single database transaction replaces all three active source tables and latest quarantined rows. This guarantees reruns do not duplicate active records, and validation failures leave a prior successful warehouse intact.

## Billing reconciliation rules

Let:
- `S` = sum of **parseable** USD costs from every input billing row (even if another field rejects the row)
- `A` = sum of USD costs on accepted billing rows
- `Q` = sum of parseable USD costs on quarantined billing rows
- `D` = sum of accepted USD costs stored in DuckDB

We verify `S = A + Q` and `A = D`. An audit `reconciled = true` additionally requires **zero rows with unparseable billing amounts**. Otherwise status is **PARTIAL / REVIEW** even if every *parseable* amount was accounted for.

Quarantined cost is **not** allocated or counted in the accepted-data dashboard, preventing false confidence in financial totals. This is a small portfolio illustration and not GAAP billing reconciliation or a substitute for CUR-specific line-item adjustments.

## Operational behavior

```bash
python -m finops.ingest
python -m finops.report
python -m pytest -q
```

`ingest` raises an error if any file is missing or its header does not match. Bad *rows* are quarantined, while valid records are ingested. Inspect `ingestion_quarantine` before assuming data is complete.

Useful SQL:

```sql
SELECT dataset, source_count, accepted_count, rejected_count, reconciled
FROM ingestion_audit ORDER BY ingestion_time_utc DESC;

SELECT dataset, csv_line_number, error_reasons
FROM ingestion_quarantine ORDER BY dataset, csv_line_number;

SELECT application, SUM(unblended_cost_usd) AS total_usd
FROM billing GROUP BY application ORDER BY total_usd DESC;
```

## Planned next iteration (Phase 3)

Build dbt models over these raw tables, with source freshness, relationships, accepted-cost facts, dimensions, and dbt tests. The shared `platform` spending remains intentionally **unallocated** until the FinOps allocation model in Phase 4.
