# Installing Phase 4 upgrade in your existing repository

**Do not create a new repository.** Extract this ZIP and copy the files into the root of `C:\Users\uppal\projects\finops-starter`, preserving folder hierarchy. Allow replacing `.github/workflows/dbt.yml` (it only adds Phase 4 checks to your current workflow). Existing Phase 1–3 data and code are preserved.

## Verify

```bash
source .venv/Scripts/activate
python -m pytest -q
dbt debug --profiles-dir .
dbt build --profiles-dir .
python -m finops.analytics_report
python -m finops.phase4_report
```

After a clean build, the `phase4_report` should reconcile raw and fully allocated billing. With your existing seed data:

- Source billed cost: `$4,434.39`
- Shared cost pool: `$484.02`
- Fully allocated cost: `$4,434.39`
- Shared allocation cost: `$484.02`
- Three product applications; one shared platform excluded as a recipient.

The SQL and Python code should run on your existing dbt-duckdb environment, but the package authoring environment **could not run DuckDB/dbt**, so your local build is the end-to-end verification. All source code parses and the pure-Python tests run independently.

## Save to GitHub after all commands succeed

```bash
git status
git add .
git commit -m "Phase 4: Add shared cost allocation and FinOps analytics"
git push origin main
```

Read `docs/phase4-finops.md` for assumptions, tests and limitations.
