"""Phase 7: validate and load synthetic FinOps CSVs into FINOPS_DB.RAW.

Examples:
    python -m finops.snowflake_load --dry-run
    python -m finops.snowflake_load --auth password
    python -m finops.snowflake_load --auth mfa
    python -m finops.snowflake_load --auth externalbrowser

Never stores account credentials in the repository. Loading replaces the contents
of the three RAW tables in a single DML transaction; repeat runs are idempotent.
"""
from __future__ import annotations

import argparse
import getpass
import os
from decimal import Decimal
from pathlib import Path

from finops.validation import SCHEMAS, load_and_validate_csv

DATASET_NAMES = ("billing", "k8s_metrics", "product_usage")
DATABASE = "FINOPS_DB"
SCHEMA = "RAW"


def validate_sources(raw_dir: Path):
    """Run Phase 2 strict CSV validation before any cloud modifications."""
    datasets = [load_and_validate_csv(name, raw_dir) for name in DATASET_NAMES]
    for data in datasets:
        if data.rejected:
            preview = "; ".join(
                f"line {item.row_number}: {', '.join(item.reasons)}"
                for item in data.rejected[:3]
            )
            raise ValueError(
                f"{data.name}: {len(data.rejected)} invalid records; "
                f"Snowflake load aborted. Examples: {preview}"
            )
        if not data.rows:
            raise ValueError(f"{data.name}: no valid records; load aborted")
    billing = datasets[0]
    if billing.unparseable_amount_rows or billing.source_parseable_usd != billing.accepted_usd:
        raise ValueError("Billing source does not fully reconcile; load aborted")
    return datasets


def table_name(dataset: str) -> str:
    # No user-supplied SQL identifier is accepted here.
    if dataset not in DATASET_NAMES:
        raise ValueError(f"Unknown dataset: {dataset}")
    return f"{DATABASE}.{SCHEMA}.{dataset.upper()}"


def create_table_sql(dataset: str) -> str:
    columns = SCHEMAS[dataset]
    ddl_columns = ", ".join(f"{col.name.upper()} {col.sql_type}" for col in columns)
    return f"CREATE TABLE IF NOT EXISTS {table_name(dataset)} ({ddl_columns})"


def insert_sql(dataset: str) -> str:
    columns = SCHEMAS[dataset]
    names = ", ".join(col.name.upper() for col in columns)
    placeholders = ", ".join("%s" for _ in columns)
    return f"INSERT INTO {table_name(dataset)} ({names}) VALUES ({placeholders})"


def expected_summaries(datasets) -> dict:
    result = {d.name: len(d.rows) for d in datasets}
    result["billing_total_usd"] = datasets[0].accepted_usd
    return result


def load_into_snowflake(conn, datasets) -> dict:
    """Create RAW tables and replace all rows within one DML transaction."""
    cur = conn.cursor()
    try:
        # DDL in Snowflake commits implicitly. Complete DDL before BEGIN.
        for data in datasets:
            cur.execute(create_table_sql(data.name))

        cur.execute("BEGIN")
        try:
            for data in datasets:
                cur.execute(f"DELETE FROM {table_name(data.name)}")
                cur.executemany(insert_sql(data.name), data.rows)
                count = int(cur.execute(
                    f"SELECT COUNT(*) FROM {table_name(data.name)}"
                ).fetchone()[0])
                if count != len(data.rows):
                    raise AssertionError(
                        f"{data.name}: Snowflake count {count} != valid source {len(data.rows)}"
                    )

            loaded_cost = Decimal(str(cur.execute(
                f"SELECT COALESCE(SUM(UNBLENDED_COST_USD),0) FROM {table_name('billing')}"
            ).fetchone()[0])).quantize(Decimal("0.01"))
            if loaded_cost != datasets[0].accepted_usd:
                raise AssertionError(
                    f"Snowflake billing ${loaded_cost} does not equal "
                    f"validated source ${datasets[0].accepted_usd}"
                )
            cur.execute("COMMIT")
        except Exception:
            cur.execute("ROLLBACK")
            raise

        result = expected_summaries(datasets)
        result["snowflake_billing_usd"] = loaded_cost
        result["reconciled"] = True
        return result
    finally:
        cur.close()


def connect(auth: str):
    try:
        import snowflake.connector
    except ImportError as exc:
        raise RuntimeError(
            "Install the connector: python -m pip install -r requirements-phase7-load.txt"
        ) from exc

    account = os.environ.get("SNOWFLAKE_ACCOUNT", "").strip()
    user = os.environ.get("SNOWFLAKE_USER", "").strip()
    if not account or not user:
        raise ValueError(
            "Set SNOWFLAKE_ACCOUNT and SNOWFLAKE_USER in your current Git Bash session. "
            "Use the Snowflake account identifier (no https:// or domain)."
        )

    params = {
        "account": account,
        "user": user,
        "role": os.environ.get("SNOWFLAKE_ROLE", "SYSADMIN"),
        "warehouse": "FINOPS_WH",
        "database": DATABASE,
        "schema": SCHEMA,
        "session_parameters": {"QUERY_TAG": "cloud_finops_portfolio_phase7_raw_load"},
    }
    if auth == "externalbrowser":
        params["authenticator"] = "externalbrowser"
    else:
        params["password"] = getpass.getpass("Snowflake password (hidden): ")
        if auth == "mfa":
            params["authenticator"] = "username_password_mfa"
    return snowflake.connector.connect(**params)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--dry-run", action="store_true", help="Validate locally without connecting")
    parser.add_argument("--auth", choices=["password", "mfa", "externalbrowser"], default="password")
    args = parser.parse_args(argv)

    datasets = validate_sources(args.raw_dir)
    expected = expected_summaries(datasets)
    print("Validated synthetic source files:")
    for name in DATASET_NAMES:
        print(f"  {name}: {expected[name]} rows")
    print(f"  Billing total: ${expected['billing_total_usd']:.2f}")
    if args.dry_run:
        print("DRY RUN PASSED. Snowflake was not contacted.")
        return

    conn = connect(args.auth)
    try:
        result = load_into_snowflake(conn, datasets)
    finally:
        conn.close()
    print("SNOWFLAKE RAW LOAD SUCCEEDED:")
    for name in DATASET_NAMES:
        print(f"  {DATABASE}.{SCHEMA}.{name.upper()}: {result[name]} rows")
    print(f"  Snowflake billing total: ${result['snowflake_billing_usd']:.2f}")
    print("  Source-to-Snowflake reconciliation: PASS")


if __name__ == "__main__":
    main()
