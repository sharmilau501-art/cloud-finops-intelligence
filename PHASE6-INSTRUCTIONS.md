# Phase 6: Power BI & 7-day forecasting

**Install**: Merge the contents of this ZIP into your existing
`C:\Users\uppal\projects\finops-starter` directory. Do not replace or remove
Phases 1–5, your `.venv`, or your DuckDB database.

**Run in VS Code Git Bash**:

```bash
source .venv/Scripts/activate
python -m pytest -q
python -m finops.phase6_export --db data/warehouse/finops.duckdb --out data/powerbi --horizon 7
```

`dbt build --profiles-dir .` should already pass from Phase 4. If you modify
upstream data, run ingestion + `dbt build` before the Phase 6 export.

**Expected sample**: 90 fully allocated application-day cost rows, 90 Kubernetes
sample records, 90 cost anomaly review records, 21 forecast rows, and raw vs
allocated spend of $4,434.39. The seven-day projected amount is NOT a confirmed
real-world bill.

Then open Power BI Desktop and follow **`docs/phase6-powerbi.md`** to build
four dashboard pages with relationships and measures.

**Version control:** commit the code, synthetic exports, and any dashboard
file/screenshots you actually create. Do not commit credentials, private
billing, `.venv`, `.duckdb`, or Docker-generated Airflow passwords.
