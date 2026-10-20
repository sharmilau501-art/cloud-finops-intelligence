"""Report and check cost allocation against the Phase 2 raw DuckDB warehouse.

Usage: python -m finops.phase4_report
"""
from __future__ import annotations

import argparse
from decimal import Decimal
from pathlib import Path

import duckdb


def money(value: object) -> Decimal:
    return Decimal(str(value)).quantize(Decimal('0.01'))


def report(db_path: Path) -> str:
    if not db_path.is_file():
        raise FileNotFoundError(f"Missing {db_path}. Run Phase 2 ingestion first.")
    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        raw = money(conn.execute(
            'select coalesce(sum(unblended_cost_usd),0) from main.billing'
        ).fetchone()[0])
        allocated = money(conn.execute(
            'select coalesce(sum(fully_loaded_cost_usd),0) '
            'from analytics.fct_shared_cost_allocation_daily'
        ).fetchone()[0])
        shared = money(conn.execute(
            "select coalesce(sum(billed_cost_usd),0) from analytics.fct_billing_daily "
            "where application = 'shared'"
        ).fetchone()[0])
        allocated_shared = money(conn.execute(
            'select coalesce(sum(allocated_shared_cost_usd),0) '
            'from analytics.fct_shared_cost_allocation_daily'
        ).fetchone()[0])
        if raw != allocated:
            raise AssertionError(f'Billing mismatch: source {raw} vs allocated {allocated}')
        if shared != allocated_shared:
            raise AssertionError(f'Shared pool mismatch: source {shared} vs allocated {allocated_shared}')

        daily_discrepancies = conn.execute('''
            with raw_daily as (
                select usage_date, sum(unblended_cost_usd) as billed
                from main.billing group by usage_date
            ), mart_daily as (
                select usage_date, sum(fully_loaded_cost_usd) as allocated
                from analytics.fct_shared_cost_allocation_daily group by usage_date
            )
            select count(*) from raw_daily r full outer join mart_daily m
              on r.usage_date = m.usage_date
            where r.usage_date is null or m.usage_date is null
               or abs(r.billed - m.allocated) > 0.005
        ''').fetchone()[0]
        if daily_discrepancies:
            raise AssertionError(f'{daily_discrepancies} date(s) failed billing reconciliation')

        lines = [
            'PHASE 4 FINOPS SUMMARY (SYNTHETIC DATA)',
            f'  Raw billed: ${raw:,.2f}',
            f'  Fully allocated: ${allocated:,.2f}',
            f'  Shared pool: ${shared:,.2f}',
            f'  Shared distributed: ${allocated_shared:,.2f}',
            '  Total + daily reconciliation: PASS',
            'APPLICATION UNIT ECONOMICS (INCLUDING ALLOCATED SHARED COST)',
        ]
        rows = conn.execute('''
            select application, sum(product_requests) as requests,
                   sum(direct_cost_usd) as direct_cost,
                   sum(allocated_shared_cost_usd) as shared_cost,
                   sum(fully_loaded_cost_usd) as full_cost,
                   round(sum(fully_loaded_cost_usd) * 1000.0 /
                         nullif(sum(product_requests), 0),4) as cost_per_1k
            from analytics.fct_shared_cost_allocation_daily
            group by 1 order by 1
        ''').fetchall()
        for app, requests, direct, share, total, rate in rows:
            pretty_rate = f'${rate:.4f}' if rate is not None else 'N/A (zero requests)'
            lines.append(
                f'  {app}: requests={requests:,} direct=${direct:,.2f} '
                f'shared=${share:,.2f} total=${total:,.2f} per_1k={pretty_rate}'
            )
        low_count = conn.execute('''
            select count(*) from analytics.mart_k8s_efficiency_daily
            where low_utilization_review_flag
        ''').fetchone()[0]
        anomaly_count = conn.execute('''
            select count(*) from analytics.mart_cost_anomalies_daily
            where cost_anomaly_flag
        ''').fetchone()[0]
        lines += [
            'REVIEW SIGNALS (ILLUSTRATIVE, NOT CONFIRMED SAVINGS)',
            f'  Low CPU and memory utilization snapshots: {low_count}',
            f'  Unusually high cost days: {anomaly_count}',
            '  Data limitations: synthetic daily samples; no verified rightsizing savings.',
        ]
        return '\n'.join(lines)
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--db', type=Path, default=Path('data/warehouse/finops.duckdb'))
    args = parser.parse_args()
    print(report(args.db))


if __name__ == '__main__':
    main()
