"""Read-only, grounded FinOps questions over existing BigQuery Spark marts.

CLI:
  python -m finops.assistant --dry-run --question 'Which application costs most?'
  python -m finops.assistant --question 'What was the total cloud spend?'
No LLM may generate SQL. The SQL catalog is fixed in application code.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from decimal import Decimal
from typing import Any

PROJECT_RE = re.compile(r"^[a-z][a-z0-9-]{4,61}[a-z0-9]$")
DATASET_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,1023}$")
MAX_BYTES_BILLED = 10 * 1024 * 1024  # protects against accidental large queries


def classify_question(question: str) -> str:
    """Map user text to a small approved query catalog (never AI-generated SQL)."""
    q = question.strip().lower()
    if not q or len(q) > 500:
        raise ValueError("Question must be between 1 and 500 characters.")
    if any(x in q for x in ("per 1,000", "per 1000", "per thousand", "unit cost", "per request")):
        return "unit_economics"
    if any(x in q for x in ("application", "applications", "app ", "apps", "highest", "most expensive", "top cost")):
        return "application_spend"
    if any(x in q for x in ("total", "overall", "spend", "spending", "bill", "billed")):
        return "total_spend"
    raise ValueError("Supported topics: total spending, most expensive application, and cost per 1,000 requests.")


def approved_sql(intent: str, project: str, dataset: str) -> str:
    """Validate identifiers before inserting them into fixed SQL templates.

    BigQuery cannot bind table identifiers as query parameters.
    """
    if not PROJECT_RE.fullmatch(project) or not DATASET_RE.fullmatch(dataset):
        raise ValueError("Invalid Google Cloud project ID or BigQuery dataset ID.")
    billing = f"`{project}.{dataset}.billing_daily`"
    apps = f"`{project}.{dataset}.app_daily`"
    sql = {
        "total_spend": f"""
SELECT CAST(ROUND(SUM(billed_cost_usd), 2) AS STRING) AS total_usd,
       CAST(ROUND(SUM(IF(application = 'shared', billed_cost_usd, 0)), 2) AS STRING) AS shared_usd,
       COUNT(*) AS billing_rows
FROM {billing}
""",
        "application_spend": f"""
SELECT application,
       CAST(ROUND(SUM(billed_cost_usd), 2) AS STRING) AS direct_cost_usd,
       SUM(product_requests) AS product_requests
FROM {apps}
GROUP BY application
ORDER BY SUM(billed_cost_usd) DESC
LIMIT 10
""",
        "unit_economics": f"""
SELECT application,
       CAST(ROUND(SAFE_DIVIDE(SUM(billed_cost_usd) * 1000,
                                SUM(product_requests)), 4) AS STRING)
           AS cost_per_1000_requests_usd,
       SUM(product_requests) AS product_requests
FROM {apps}
GROUP BY application
ORDER BY SAFE_DIVIDE(SUM(billed_cost_usd), SUM(product_requests)) DESC
LIMIT 10
""",
    }
    if intent not in sql:
        raise ValueError("Unsupported query category.")
    return sql[intent].strip()


def _money(value: Any) -> str:
    return f"${Decimal(str(value or 0)):,.2f}"


def explain_from_metrics(intent: str, records: list[dict[str, Any]]) -> str:
    """Deterministic, auditable fallback when no Gemini API key is configured."""
    if not records:
        return "The BigQuery query returned no matching data."
    first = records[0]
    if intent == "total_spend":
        return (f"Total billed cost was {_money(first['total_usd'])} across "
                f"{first['billing_rows']} billing rows, including "
                f"{_money(first['shared_usd'])} in shared costs. All costs are synthetic.")
    if intent == "application_spend":
        return (f"{first['application']} had the highest direct billed cost at "
                f"{_money(first['direct_cost_usd'])}. "
                "Shared platform charges are excluded from application totals.")
    if intent == "unit_economics":
        return (f"{first['application']} had the highest direct cost per 1,000 requests "
                f"at {_money(first['cost_per_1000_requests_usd'])}. "
                "This is calculated from aggregate direct cost and request totals.")
    raise ValueError("Unsupported query category.")


def gemini_explanation(question: str, intent: str, records: list[dict[str, Any]]) -> str:
    """Send only aggregated synthetic metrics to Gemini, never credentials or raw rows."""
    from google import genai  # optional dependency; loaded only when enabled

    model = os.getenv("FINOPS_GEMINI_MODEL", "gemini-3.8-flash")
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    response = client.models.generate_content(
        model=model,
        contents=("Question: " + question + "\nApproved metric: " + intent
                  + "\nValidated rows: " + json.dumps(records, default=str)),
        config={
            "system_instruction": (
                "You explain synthetic FinOps metrics. Use ONLY the supplied validated "
                "aggregates. Never invent figures, trends, causes, or recommendations "
                "not supported by the supplied data. Distinguish shared costs from "
                "direct-only application costs. Answer concisely and mention the "
                "data is simulated. Never write or propose SQL."
            ),
            "temperature": 0,
        },
    )
    if not response.text:
        raise RuntimeError("Gemini returned no explanation.")
    return response.text.strip()


def query_bigquery(sql: str, project: str, location: str = "US") -> list[dict[str, Any]]:
    from google.cloud import bigquery

    client = bigquery.Client(project=project, location=location)
    job_cfg = bigquery.QueryJobConfig(
        maximum_bytes_billed=MAX_BYTES_BILLED,
        use_query_cache=True,
        use_legacy_sql=False,
    )
    rows = client.query(sql, location=location, job_config=job_cfg).result(max_results=10)
    return [dict(row.items()) for row in rows]


def answer_question(
    question: str,
    project: str,
    dataset: str = "finops_demo",
    location: str = "US",
    fetch=None,
    narrate=None,
) -> dict[str, Any]:
    intent = classify_question(question)
    sql = approved_sql(intent, project, dataset)
    records = (fetch or (lambda s: query_bigquery(s, project, location)))(sql)
    fallback = explain_from_metrics(intent, records)
    mode = "metrics_only"
    explanation = fallback
    narration_warning = None

    # A key may be present in the shell without the user intending a paid API call.
    # Narration is opt-in; the read-only metrics mode is the safe default.
    narrator_choice = os.getenv("FINOPS_NARRATOR", "metrics_only").strip().lower()
    if narrator_choice not in ("metrics_only", "gemini"):
        raise ValueError("FINOPS_NARRATOR must be metrics_only or gemini.")
    if narrate is not None:
        explanation = narrate(question, intent, records)
        mode = "custom_narrator"
    elif narrator_choice == "gemini" and records:
        if not os.getenv("GEMINI_API_KEY"):
            narration_warning = "Gemini not configured; showing verified metrics instead."
        else:
            try:
                explanation = gemini_explanation(question, intent, records)
                mode = "gemini"
            except Exception:
                # Unavailable billing, quotas, or network must not make verified
                # warehouse metrics unavailable. Never expose raw API errors/secrets.
                narration_warning = "Gemini unavailable; showing verified metrics instead."
    return {
        "question": question,
        "intent": intent,
        "source": f"{project}.{dataset}",
        "mode": mode,
        "explanation": explanation,
        "validated_metrics": records,
        "narration_warning": narration_warning,
        "caveat": "Synthetic demo data. Application metrics exclude unallocated shared costs.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Grounded FinOps assistant")
    parser.add_argument("--question", default="What was total cloud spending?")
    parser.add_argument("--project", default=os.getenv("FINOPS_BQ_PROJECT", "finops-cloud-intelligence-2026"))
    parser.add_argument("--dataset", default=os.getenv("FINOPS_BQ_DATASET", "finops_demo"))
    parser.add_argument("--location", default="US")
    parser.add_argument("--dry-run", action="store_true", help="Print approved query without cloud calls")
    args = parser.parse_args()
    if args.dry_run:
        intent = classify_question(args.question)
        print(json.dumps({"status": "READY", "intent": intent,
                          "sql": approved_sql(intent, args.project, args.dataset)}, indent=2))
    else:
        print(json.dumps(answer_question(args.question, args.project, args.dataset, args.location), indent=2, default=str))


if __name__ == "__main__":
    main()
