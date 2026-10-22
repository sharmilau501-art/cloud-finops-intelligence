# Phase 7, Step 2: Load validated synthetic FinOps data into Snowflake

## Precondition

Warehouse: `FINOPS_WH`; Database: `FINOPS_DB`; Schemas: `RAW`, `ANALYTICS`.
These are created in Step 1 under the role `SYSADMIN`. A role with appropriate
warehouse USAGE, database/schema USAGE, and table CREATE/MODIFY permissions may
be substituted with `SNOWFLAKE_ROLE`.

## Commands (Windows Git Bash, existing virtual environment)

```bash
source .venv/Scripts/activate
python -m pip install -r requirements-phase7-load.txt
python -m finops.snowflake_load --dry-run
```

Expected: billing 120, k8s_metrics 90, product_usage 90, bill $4434.39.

In Snowsight, click your account/profile menu and copy your **Account Identifier**.
Use only the identifier, not the browser URL or the `.snowflakecomputing.com` suffix.
Find your Snowflake **login username** with `SELECT CURRENT_USER()` in a SQL worksheet.

```bash
export SNOWFLAKE_ACCOUNT='your-org-your-account'
export SNOWFLAKE_USER='your-snowflake-login'
export SNOWFLAKE_ROLE='SYSADMIN'
python -m finops.snowflake_load --auth password
```

You'll be prompted to enter the password invisibly. Do not put it in source files,
terminal commands, screenshots, Git commits, or chat. If your account requires an
MFA push, use `--auth mfa`. If your account is configured for SAML SSO, use
`--auth externalbrowser`. This tool does not cache or write passwords.

## Verify in a Snowflake SQL worksheet

```sql
USE ROLE SYSADMIN;
USE WAREHOUSE FINOPS_WH;
USE DATABASE FINOPS_DB;
USE SCHEMA RAW;

SELECT 'BILLING' AS DATASET, COUNT(*) AS RECORD_COUNT FROM BILLING
UNION ALL
SELECT 'K8S_METRICS', COUNT(*) FROM K8S_METRICS
UNION ALL
SELECT 'PRODUCT_USAGE', COUNT(*) FROM PRODUCT_USAGE;

SELECT SUM(UNBLENDED_COST_USD) AS BILLED_USD FROM BILLING;
SELECT APPLICATION, SUM(UNBLENDED_COST_USD) AS COST_USD
FROM BILLING GROUP BY APPLICATION ORDER BY APPLICATION;

ALTER WAREHOUSE FINOPS_WH SUSPEND;
```

Expected: 120, 90, 90 and 4434.39. Shared pool = 484.02.

## Design and limitations

- Phase 2 validation checks headers, ranges, record uniqueness and amounts *before* any cloud write.
- The three Snowflake tables are created using the same types as Phase 2.
- Data loads use parameterized batched inserts with Snowflake's Python connector.
- `DELETE` and `INSERT` execute in one transaction, so an error rolls back the DML.
- A rerun replaces the current RAW snapshots; it does **not** append duplicate records.
- This small-data loading approach is deliberately simple for a 300-row portfolio
  demo. For large exports, move to staged CSV/Parquet and `COPY INTO`, or Snowpipe.
- Data are synthetic. No real AWS invoice, Kubernetes cluster or Sony data are used.
- Step 3 will configure a **separate Snowflake dbt target** without breaking DuckDB.
