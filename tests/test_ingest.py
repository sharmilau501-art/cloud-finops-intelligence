"""DuckDB integration tests for Phase 2."""
import csv

import pytest

duckdb = pytest.importorskip("duckdb")

from finops.generate_data import generate
from finops.ingest import ingest
from finops.report import report


def overwrite_field(path, row_number, field, value):
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        columns, rows = reader.fieldnames, list(reader)
    rows[row_number][field] = value
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def test_ingest_clean_inputs_and_reconcile(tmp_path):
    raw, db = tmp_path / "raw", tmp_path / "warehouse" / "finops.duckdb"
    generate(raw, days=30)
    result = ingest(raw, db)
    assert result["datasets"]["billing"]["reconciled"] is True
    assert result["datasets"]["billing"]["accepted"] == 120
    assert result["datasets"]["k8s_metrics"]["loaded"] == 90
    assert result["datasets"]["product_usage"]["loaded"] == 90
    text = report(db)
    assert "checkout" in text
    assert "Billing reconciliation: PASS" in text
    con = duckdb.connect(str(db), read_only=True)
    try:
        assert con.execute("SELECT COUNT(*) FROM ingestion_quarantine").fetchone()[0] == 0
        assert con.execute("SELECT COUNT(*) FROM ingestion_audit").fetchone()[0] == 3
    finally:
        con.close()


def test_quarantine_and_partial_reconciliation(tmp_path):
    raw, db = tmp_path / "raw", tmp_path / "f.duckdb"
    generate(raw, days=2)
    overwrite_field(raw / "billing.csv", 0, "unblended_cost_usd", "not-money")
    overwrite_field(raw / "k8s_metrics.csv", 0, "cpu_utilization_pct", "101")
    result = ingest(raw, db)
    assert result["datasets"]["billing"]["quarantined"] == 1
    assert result["datasets"]["billing"]["reconciled"] is False
    assert result["datasets"]["billing"]["unparseable_amount_rows"] == 1
    assert result["datasets"]["k8s_metrics"]["quarantined"] == 1
    con = duckdb.connect(str(db), read_only=True)
    try:
        assert con.execute("SELECT COUNT(*) FROM ingestion_quarantine").fetchone()[0] == 2
        assert con.execute("SELECT COUNT(*) FROM billing").fetchone()[0] == 7
    finally:
        con.close()


def test_ingest_is_idempotent_and_audit_keeps_history(tmp_path):
    raw, db = tmp_path / "raw", tmp_path / "f.duckdb"
    generate(raw, days=3)
    ingest(raw, db)
    ingest(raw, db)
    con = duckdb.connect(str(db), read_only=True)
    try:
        assert con.execute("SELECT COUNT(*) FROM billing").fetchone()[0] == 12
        assert con.execute("SELECT COUNT(*) FROM ingestion_audit").fetchone()[0] == 6
        assert con.execute("SELECT COUNT(*) FROM ingestion_quarantine").fetchone()[0] == 0
    finally:
        con.close()


def test_bad_header_does_not_modify_existing_warehouse(tmp_path):
    raw, db = tmp_path / "raw", tmp_path / "f.duckdb"
    generate(raw, days=3)
    ingest(raw, db)
    p = raw / "product_usage.csv"
    p.write_text(p.read_text(encoding="utf-8").replace("product_requests", "wrong_name", 1), encoding="utf-8")
    with pytest.raises(ValueError, match="header mismatch"):
        ingest(raw, db)
    con = duckdb.connect(str(db), read_only=True)
    try:
        assert con.execute("SELECT COUNT(*) FROM billing").fetchone()[0] == 12
        assert con.execute("SELECT COUNT(*) FROM ingestion_audit").fetchone()[0] == 3
    finally:
        con.close()


def test_missing_input_does_not_create_database(tmp_path):
    raw, db = tmp_path / "raw", tmp_path / "f.duckdb"
    generate(raw, days=3)
    (raw / "k8s_metrics.csv").unlink()
    with pytest.raises(FileNotFoundError):
        ingest(raw, db)
    assert not db.exists()
