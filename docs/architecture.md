# Intended architecture

Synthetic CSV / optional AWS CUR 2.0 adapter / optional OpenCost adapter
  -> Python ingestion & schema checks
  -> DuckDB raw tables and quarantined records
  -> dbt staging and fact/dimension models
  -> allocation and unit economics marts
  -> Power BI reports / Python forecasts

Airflow orchestrates ingestion and transformations in a later phase. Snowflake replaces the local warehouse in an optional later phase.

## Accounting safeguards (future phases)
Preserve raw line-item IDs; do not double-count platform shared charges; retain unallocated amounts; document allocation policy; reconcile modeled total to original bill.
