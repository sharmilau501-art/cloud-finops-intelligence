# Phase 5: Read-only FinOps Analytics Assistant (completed in metrics-only mode)

## Status

**Current:** A local FastAPI self-service analytics dashboard backed by approved BigQuery `SELECT` queries over **synthetic** cloud cost datasets. It works without Gemini credits or an API key. BigQuery requests may still incur charges depending on the GCP project configuration.

**Deferred:** Local Ollama LLM integration and verification of Gemini narrative output. Do not describe them as completed.

## Architecture

Browser (`http://127.0.0.1:8001`) → FastAPI `/ask` → deterministic intent classifier → fixed read-only BigQuery SQL template → verified aggregate metrics → deterministic explanation and raw metric records.

The model never generates SQL, and data is synthetic. `app_daily` metrics show **direct application costs**; platform-wide shared charges are not allocated to applications. The `billing_daily` query reports shared costs separately.

## Setup: WSL Ubuntu

```bash
cd /mnt/c/Users/uppal/projects/finops-starter
source ~/.venvs/finops-spark/bin/activate
python -m pip install -r requirements-assistant.txt -e .
python -m pytest tests/test_assistant.py -q
```

## Default mode: no paid Gemini API calls

```bash
unset GEMINI_API_KEY
export FINOPS_NARRATOR=metrics_only
export FINOPS_BQ_PROJECT=finops-cloud-intelligence-2026
export FINOPS_BQ_DATASET=finops_demo
python -m finops.assistant --dry-run --question 'Which application costs most?'
python -m finops.assistant --question 'What was the total cloud spend?'
python -m uvicorn finops.assistant_api:app --host 127.0.0.1 --port 8001
```

Visit `http://127.0.0.1:8001`; the CLI/API response includes `mode: metrics_only`, grounded metric records, a synthetic-data caveat, and a deterministic explanation.

**`FINOPS_NARRATOR=metrics_only` is the default even if a key remains in the shell**, so merely leaving a Gemini key configured does not trigger a paid call. Later, `FINOPS_NARRATOR=gemini` explicitly enables that option, provided a key is available. Any Gemini failure returns the verified metrics and a generic warning instead of crashing. Credentials and raw API errors are never sent to the UI.

## Supported questions

- What was total cloud spending?
- Which application costs most?
- What is cost per 1,000 requests?

Unsupported questions fail closed; natural-language questions cannot execute arbitrary SQL. Queries set `maximum_bytes_billed` to 10 MiB, which is not a zero-cost guarantee. This is a trusted local development app with no authentication, so **do not expose it to the public internet**.

## Validation and portfolio claim

The original BigQuery upload was validated with 120 billing rows, 90 application daily rows, and $4,434.39 matched source vs warehouse billing (synthetic figures). Tests use mocked warehouse results and do not require GCP access. After running the updated tests locally, document their outcome. If GCP billing controls matter, check them before live query tests.

Accurate resume wording: "Built a read-only self-service FinOps analytics application using FastAPI and Google BigQuery, routing natural-language questions to predefined SQL and presenting verified cost metrics with data-quality safeguards."

## Deferred

An optional local Ollama narrator can be implemented and tested later. No Ollama binaries, local models, Docker services, or paid Gemini credits are required to complete this phase.

## Version control

Commit source, tests, requirements, and docs only. Never commit `.env`, application default credentials (`application_default_credentials.json`), API keys, personal billing exports, or generated Parquet data.
