import pytest
from finops.assistant import (
    answer_question, approved_sql, classify_question, explain_from_metrics,
)


def test_question_total():
    assert classify_question("How much total spending?") == "total_spend"


def test_question_app():
    assert classify_question("Which application has the highest cost?") == "application_spend"


def test_question_unit():
    assert classify_question("Cost per 1,000 requests by app?") == "unit_economics"


def test_unknown_refused():
    with pytest.raises(ValueError, match="Supported topics"):
        classify_question("Delete all tables")


def test_long_refused():
    with pytest.raises(ValueError):
        classify_question("x" * 501)


def test_sql_injection_dataset_refused():
    with pytest.raises(ValueError, match="Invalid"):
        approved_sql("total_spend", "finops-cloud-intelligence-2026", "finops_demo`; DROP TABLE")


def test_sql_injection_project_refused():
    with pytest.raises(ValueError, match="Invalid"):
        approved_sql("total_spend", "bad`project", "finops_demo")


def test_only_read_only_sql():
    for intent in ("total_spend", "application_spend", "unit_economics"):
        sql = approved_sql(intent, "finops-cloud-intelligence-2026", "finops_demo")
        assert sql.startswith("SELECT ")
        assert "`finops-cloud-intelligence-2026.finops_demo." in sql


def test_total_summary_explains_shared(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    result = answer_question("total spend", "finops-cloud-intelligence-2026", fetch=lambda _: [
        {"total_usd": "4434.39", "shared_usd": "484.02", "billing_rows": 120}
    ])
    assert "$4,434.39" in result["explanation"]
    assert "$484.02" in result["explanation"]
    assert result["mode"] == "metrics_only"


def test_direct_cost_warning():
    text = explain_from_metrics("application_spend", [{"application": "catalog", "direct_cost_usd": "1200.50"}])
    assert "shared" in text.lower()


def test_zero_divide_protection():
    sql = approved_sql("unit_economics", "finops-cloud-intelligence-2026", "finops_demo")
    assert "SAFE_DIVIDE" in sql


def test_empty_rows():
    assert "no matching data" in explain_from_metrics("total_spend", []).lower()


def test_health_endpoint():
    from fastapi.testclient import TestClient
    from finops.assistant_api import app
    response = TestClient(app).get('/health')
    assert response.status_code == 200
    assert response.json() == {'status': 'ok'}


def test_browser_interface_available():
    from fastapi.testclient import TestClient
    from finops.assistant_api import app
    response = TestClient(app).get('/')
    assert response.status_code == 200
    assert 'FinOps Analytics Assistant' in response.text


def test_api_blocks_unsupported_questions_without_cloud_calls(monkeypatch):
    from fastapi.testclient import TestClient
    from finops.assistant_api import app
    response = TestClient(app).post('/ask', json={'question': 'Delete all tables'})
    assert response.status_code == 400


def test_metrics_only_default_even_with_gemini_key(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "dummy-do-not-call")
    monkeypatch.delenv("FINOPS_NARRATOR", raising=False)
    def fail(*args, **kwargs):
        raise AssertionError("Gemini must not be called in the default mode")
    monkeypatch.setattr("finops.assistant.gemini_explanation", fail)
    result = answer_question("total spend", "finops-cloud-intelligence-2026", fetch=lambda _: [
        {"total_usd": "4434.39", "shared_usd": "484.02", "billing_rows": 120}
    ])
    assert result["mode"] == "metrics_only"
    assert result["narration_warning"] is None


def test_opt_in_gemini_falls_back_if_credits_depleted(monkeypatch):
    monkeypatch.setenv("FINOPS_NARRATOR", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "dummy-do-not-call")
    def exhausted(*args, **kwargs):
        raise RuntimeError("402 RESOURCE_EXHAUSTED")
    monkeypatch.setattr("finops.assistant.gemini_explanation", exhausted)
    result = answer_question("total spend", "finops-cloud-intelligence-2026", fetch=lambda _: [
        {"total_usd": "4434.39", "shared_usd": "484.02", "billing_rows": 120}
    ])
    assert result["mode"] == "metrics_only"
    assert result["narration_warning"]
    assert "$4,434.39" in result["explanation"]


def test_opt_in_gemini_without_key_stays_metrics_only(monkeypatch):
    monkeypatch.setenv("FINOPS_NARRATOR", "gemini")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    result = answer_question("total spend", "finops-cloud-intelligence-2026", fetch=lambda _: [
        {"total_usd": "4434.39", "shared_usd": "484.02", "billing_rows": 120}
    ])
    assert result["mode"] == "metrics_only"
    assert "not configured" in result["narration_warning"]


def test_gemini_explicit_opt_in(monkeypatch):
    monkeypatch.setenv("FINOPS_NARRATOR", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "dummy-do-not-call")
    monkeypatch.setattr("finops.assistant.gemini_explanation", lambda *args: "Grounded explanation")
    result = answer_question("total spend", "finops-cloud-intelligence-2026", fetch=lambda _: [
        {"total_usd": "4434.39", "shared_usd": "484.02", "billing_rows": 120}
    ])
    assert result["mode"] == "gemini"
    assert result["explanation"] == "Grounded explanation"


def test_unsupported_narrator_refused(monkeypatch):
    monkeypatch.setenv("FINOPS_NARRATOR", "ollama")
    with pytest.raises(ValueError, match="FINOPS_NARRATOR"):
        answer_question("total spend", "finops-cloud-intelligence-2026", fetch=lambda _: [
            {"total_usd": "4434.39", "shared_usd": "484.02", "billing_rows": 120}
        ])
