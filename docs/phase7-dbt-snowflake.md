# Phase 7 step 3: Run dbt on Snowflake

This add-on introduces a **second** dbt profile; the existing `profiles.yml` in the repository root continues to target local DuckDB. The only existing file replaced is `models/staging/_sources.yml` to select the appropriate raw schema for each adapter.

Prerequisite: `python -m finops.snowflake_load --auth password` succeeded; Snowflake contains FINOPS_DB.RAW.BILLING (120), K8S_METRICS (90), PRODUCT_USAGE (90), with billed total $4,434.39.

## Installation

Copy the ZIP's contents to the root of your existing `finops-starter` project, preserving folders.

```bash
source .venv/Scripts/activate
python -m pip install -r requirements-phase7-dbt.txt
dbt --version
```

**Credentials:** The original loader used the Snowflake account identifier and exact login username via `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, and `SNOWFLAKE_ROLE`. Re-export if you opened a new Git Bash session:

```bash
export SNOWFLAKE_ACCOUNT='YOUR_ORG-YOUR_ACCOUNT'
export SNOWFLAKE_USER='YOUR_SNOWFLAKE_LOGIN_NAME'
export SNOWFLAKE_ROLE='SYSADMIN'
```

Read the password without showing it or saving it in a Git-tracked file:

```bash
read -rs -p "Snowflake password: " DBT_ENV_SECRET_SNOWFLAKE_PASSWORD; echo
export DBT_ENV_SECRET_SNOWFLAKE_PASSWORD
```

## Test connection, then build

```bash
dbt debug --profiles-dir config/snowflake --target snowflake
# Run only this command for model creation + all dbt tests:
dbt build --profiles-dir config/snowflake --target snowflake
```

If `dbt build` reports a SQL or model error, **do not commit yet**: capture that specific error for diagnosis.

## Verify in Snowflake worksheet

```sql
USE ROLE SYSADMIN;
USE WAREHOUSE FINOPS_WH;
SELECT COUNT(*) AS N FROM FINOPS_DB.ANALYTICS.FCT_BILLING_DAILY;  -- expect 120
SELECT COUNT(*) AS N FROM FINOPS_DB.ANALYTICS.FCT_SHARED_COST_ALLOCATION_DAILY; -- expect 90
SELECT SUM(BILLED_COST_USD) AS RAW_MODELED_TOTAL
FROM FINOPS_DB.ANALYTICS.FCT_BILLING_DAILY; -- expect 4434.39
SELECT SUM(FULLY_LOADED_COST_USD) AS ALLOCATED_TOTAL
FROM FINOPS_DB.ANALYTICS.FCT_SHARED_COST_ALLOCATION_DAILY; -- expect 4434.39
ALTER WAREHOUSE FINOPS_WH SUSPEND;
```

## Confirm DuckDB still works

```bash
dbt build --profiles-dir .
python -m pytest -q
```

Keep credentials out of Git and shell history. When finished, remove the temporary password environment variable:

```bash
unset DBT_ENV_SECRET_SNOWFLAKE_PASSWORD
```

After all checks succeed:

```bash
git status
git add config/snowflake/profiles.yml models/staging/_sources.yml requirements-phase7-dbt.txt docs/phase7-dbt-snowflake.md
git diff --cached --stat
git commit -m "Phase 7: Add Snowflake dbt target and verify FinOps marts"
git push origin main
```

These are synthetic records, not actual PlayStation or AWS production charges. Snowflake compute is billable; FINOPS_WH is XSMALL with auto-suspend set to 60 seconds, but manually suspending after use is encouraged.
