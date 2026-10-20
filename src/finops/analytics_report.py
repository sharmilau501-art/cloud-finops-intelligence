"""Print the Phase 3 dbt marts and verify preserved billing totals.

Usage: python -m finops.analytics_report
"""
from __future__ import annotations

import argparse
from decimal import Decimal
from pathlib import Path

import duckdb


def report(db_path: Path) -> str:
    if not db_path.is_file():
        raise FileNotFoundError(f"Missing warehouse {db_path}; run Phase 2 ingestion first.")
    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        raw = Decimal(str(conn.execute(
            "SELECT COALESCE(SUM(unblended_cost_usd),0) FROM main.billing"
        ).fetchone()[0]))
        mart = Decimal(str(conn.execute(
            "SELECT COALESCE(SUM(billed_cost_usd),0) FROM analytics.fct_billing_daily"
        ).fetchone()[0]))
        if raw != mart:
            raise AssertionError(f"Billing totals differ: raw={raw} modeled={mart}")
        lines = [
            "PHASE 3 DBT MART SUMMARY",
            f"  Raw billed USD: ${raw:,.2f}",
            f"  Modeled billed USD: ${mart:,.2f}",
            "  Cost reconciliation: PASS",
        ]
        for name in (
            'dim_application', 'dim_date', 'fct_billing_daily',
            'fct_k8s_daily', 'fct_product_usage_daily', 'mart_unit_economics_daily',
        ):
            count = conn.execute(f"SELECT COUNT(*) FROM analytics.{name}").fetchone()[0]
            lines.append(f"  {name}: {count} records")
        lines.append("DIRECT-ONLY UNIT ECONOMICS (SHARED COST EXCLUDED)")
        rows = conn.execute("""
            select application,
                   sum(product_requests) as requests,
                   sum(direct_cost_usd) as direct_cost_usd,
                   round(sum(direct_cost_usd) * 1000.0
                         / nullif(sum(product_requests), 0), 4) as usd_per_1k_requests
            from analytics.mart_unit_economics_daily
            group by 1 order by 1
        """).fetchall()
        for app, requests, direct_cost, per_1k in rows:
            lines.append(f"  {app}: requests={requests:,} direct_cost=${direct_cost:,.2f} "
                         f"cost_per_1k=${per_1k:.4f}")
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
