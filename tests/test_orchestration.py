"""Host-Python tests for Phase 5 quality gates (no Airflow installation required)."""
import csv
from pathlib import Path

import pytest

from finops.orchestration import check_sources, check_ingestion, check_marts, write_report
from finops.validation import SCHEMAS


def sample_sources(tmp_path: Path):
    for name, cols in SCHEMAS.items():
        with (tmp_path / (name + ".csv")).open("w", newline="") as file:
            writer = csv.writer(file)
            writer.writerow([c.name for c in cols])
            writer.writerow(["placeholder"] * len(cols))


def test_source_checks_accept_all_required_datasets(tmp_path):
    sample_sources(tmp_path)
    assert check_sources(tmp_path) == {name: 1 for name in SCHEMAS}


def test_source_checks_fail_on_missing_dataset(tmp_path):
    sample_sources(tmp_path)
    (tmp_path / "billing.csv").unlink()
    with pytest.raises(FileNotFoundError, match="billing"):
        check_sources(tmp_path)


def test_source_checks_fail_on_wrong_header(tmp_path):
    sample_sources(tmp_path)
    (tmp_path / "billing.csv").write_text("wrong,columns\n1,2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Incorrect columns"):
        check_sources(tmp_path)


def test_source_checks_fail_on_empty_dataset(tmp_path):
    sample_sources(tmp_path)
    file = tmp_path / "product_usage.csv"
    with file.open("w", newline="") as handle:
        csv.writer(handle).writerow([c.name for c in SCHEMAS["product_usage"]])
    with pytest.raises(ValueError, match="empty"):
        check_sources(tmp_path)


def test_ingestion_check_rejects_missing_db(tmp_path):
    with pytest.raises(FileNotFoundError, match="warehouse"):
        check_ingestion(tmp_path / "missing.duckdb")


def test_mart_report_rejects_missing_db(tmp_path):
    with pytest.raises(FileNotFoundError):
        check_marts(tmp_path / "missing.duckdb")


def test_write_report_reuses_checks(tmp_path, monkeypatch):
    import finops.orchestration as mod
    monkeypatch.setattr(mod, "check_ingestion", lambda db: {"billing": 2})
    monkeypatch.setattr(mod, "check_marts", lambda db: "Billing reconciliation: PASS")
    output = tmp_path / "reports" / "latest.txt"
    assert write_report(tmp_path / "sample.duckdb", output) == output
    assert "Billing reconciliation: PASS" in output.read_text(encoding="utf-8")
    assert not (output.with_name(output.name + ".tmp")).exists()
