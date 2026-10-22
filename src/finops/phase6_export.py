"""Read verified Phase 4 DuckDB marts and export a Power BI-ready star schema.

Run only after `dbt build --profiles-dir .` and the Phase 4 reconciliation.
This module does not regenerate or modify synthetic inputs or the warehouse.
"""
from __future__ import annotations

import argparse
import csv
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from finops.forecasting import CostPoint, forecast_all

DEFAULT_DB = Path('data/warehouse/finops.duckdb')
DEFAULT_OUTPUT = Path('data/powerbi')

COST_SQL = '''
select usage_date, application, product_requests, direct_cost_usd,
       allocated_shared_cost_usd, fully_loaded_cost_usd,
       fully_loaded_cost_per_1k_requests_usd, allocation_method
from analytics.fct_shared_cost_allocation_daily
order by usage_date, application
'''
EFFICIENCY_SQL = '''
select usage_date, application, avg_cpu_utilization_pct,
       avg_memory_utilization_pct, requested_cpu_cores,
       requested_memory_gib, telemetry_samples,
       low_utilization_review_flag, suggested_review
from analytics.mart_k8s_efficiency_daily
order by usage_date, application
'''
ANOMALY_SQL = '''
select usage_date, application, fully_loaded_cost_usd,
       prior_7_observation_avg_usd, cost_vs_baseline_ratio,
       cost_anomaly_flag
from analytics.mart_cost_anomalies_daily
order by usage_date, application
'''
APP_SQL = '''
select application, owning_team, is_shared_platform
from analytics.dim_application
order by application
'''
RAW_TOTAL_SQL = 'select sum(unblended_cost_usd) from main.billing'


def _csv_value(value):
    if isinstance(value, (date,)):
        return value.isoformat()
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, Decimal):
        return format(value, 'f')
    if value is None:
        return ''
    return value


def write_csv(path: Path, columns: list[str], rows: list[tuple]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.writer(handle)
        writer.writerow(columns)
        for row in rows:
            writer.writerow([_csv_value(value) for value in row])


def query_table(conn, sql: str) -> tuple[list[str], list[tuple]]:
    result = conn.execute(sql)
    columns = [col[0] for col in result.description]
    return columns, result.fetchall()


def validate_cost_export(rows: list[tuple], source_total: Decimal) -> None:
    """Reconcile at cent precision and enforce date/application uniqueness."""
    if not rows:
        raise ValueError('No cost allocation rows found')
    seen = set()
    direct, shared, allocated = Decimal('0.00'), Decimal('0.00'), Decimal('0.00')
    for row in rows:
        usage_date, application, requests, cost_direct, cost_shared, cost_total, *_ = row
        key = (usage_date, application)
        if key in seen or application == 'shared' or not application:
            raise ValueError('Duplicate, shared, or missing application in fully allocated fact')
        seen.add(key)
        if requests is None or requests < 0 or any(v is None or v < 0 for v in [cost_direct, cost_shared, cost_total]):
            raise ValueError('Invalid request count or negative/missing costs')
        if cost_direct + cost_shared != cost_total:
            raise ValueError('Direct + shared != fully allocated cost')
        direct += cost_direct
        shared += cost_shared
        allocated += cost_total
    if allocated != source_total or direct + shared != source_total:
        raise ValueError(f'Finance reconciliation failed: {allocated} != {source_total}')


def export_warehouse(db_path: Path, out_dir: Path, horizon: int = 7) -> dict[str, int]:
    import duckdb
    if not db_path.is_file():
        raise FileNotFoundError(f'DuckDB warehouse not found: {db_path}')
    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        cost_columns, costs = query_table(conn, COST_SQL)
        source_total = conn.execute(RAW_TOTAL_SQL).fetchone()[0]
        if source_total is None:
            raise ValueError('Raw billing total is missing')
        validate_cost_export(costs, source_total)
        efficiency_cols, efficiency = query_table(conn, EFFICIENCY_SQL)
        anomaly_cols, anomalies = query_table(conn, ANOMALY_SQL)
        app_cols, apps = query_table(conn, APP_SQL)
        # Validate other fact keys before writing any dashboard files.
        for dataset in (efficiency, anomalies):
            keys = [(r[0], r[1]) for r in dataset]
            if len(keys) != len(set(keys)):
                raise ValueError('Duplicate date/application key in dashboard fact')
    finally:
        conn.close()

    costs_for_forecast = [CostPoint(row[0], row[1], row[5]) for row in costs]
    forecast_rows, forecast_checks = forecast_all(costs_for_forecast, horizon=horizon)
    latest_date = max(r[0] for r in costs)
    earliest_date = min(r[0] for r in costs)
    dates = [(earliest_date + timedelta(days=i),)
             for i in range((latest_date - earliest_date).days + 1 + horizon)]
    date_dim_rows = [(d, d.year, d.month, d.day, d.isoweekday()) for (d,) in dates]

    out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(out_dir / 'fact_cost_daily.csv', cost_columns, costs)
    write_csv(out_dir / 'fact_k8s_daily.csv', efficiency_cols, efficiency)
    write_csv(out_dir / 'fact_anomalies_daily.csv', anomaly_cols, anomalies)
    write_csv(out_dir / 'dim_application.csv', app_cols, apps)
    write_csv(out_dir / 'dim_date.csv',
              ['usage_date', 'calendar_year', 'calendar_month', 'day_of_month', 'iso_weekday'], date_dim_rows)
    write_csv(out_dir / 'fact_forecast_daily.csv',
              ['usage_date', 'application', 'predicted_cost_usd', 'forecast_origin_date', 'model'],
              [(r.usage_date, r.application, r.predicted_cost_usd, r.forecast_origin_date, r.model)
               for r in forecast_rows])
    write_csv(out_dir / 'forecast_backtest.csv',
              ['application', 'validation_days', 'mae_usd', 'wape_pct',
               'naive_mae_usd', 'naive_wape_pct'],
              [(r.application, r.validation_days, r.mae_usd, r.wape_pct,
                r.naive_mae_usd, r.naive_wape_pct) for r in forecast_checks])
    return {'cost_rows': len(costs), 'k8s_rows': len(efficiency),
            'anomaly_rows': len(anomalies), 'forecast_rows': len(forecast_rows),
            'dates': len(dates), 'applications': len(apps),
            'source_total_cents': int(source_total * 100)}


def main() -> None:
    parser = argparse.ArgumentParser(description='Export a Power BI dataset + 7-day forecast')
    parser.add_argument('--db', type=Path, default=DEFAULT_DB)
    parser.add_argument('--out', type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--horizon', type=int, default=7)
    args = parser.parse_args()
    print(f'Phase 6 dashboard export PASS: {export_warehouse(args.db, args.out, args.horizon)}')
    print('Data uses synthetic inputs only; cost forecasts are illustrative, not calibrated.')


if __name__ == '__main__':
    main()
