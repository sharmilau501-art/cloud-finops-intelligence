"""Tests never contact Google Cloud and require no credentials."""
import json
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from finops import bigquery_load as loader


@pytest.fixture
def output_dir(tmp_path):
    report = {
        "source_counts": {"billing": 120, "k8s_metrics": 90, "product_usage": 90},
        "output_counts": {"billing_daily": 120, "app_daily": 90},
        "source_billed_usd": "4434.39", "modeled_billed_usd": "4434.39",
        "direct_billed_usd": "3950.37", "shared_billed_usd": "484.02", "reconciled": True,
    }
    (tmp_path / "quality_metrics.json").write_text(json.dumps(report))
    for table in loader.TABLES:
        (tmp_path / table).mkdir()
        (tmp_path / table / "part-00000-abc.parquet").write_bytes(b"PAR1")
    return tmp_path


def test_preflight_passes_on_valid_output(output_dir):
    plan = loader.preflight(output_dir)
    assert plan["status"] == "READY"
    assert plan["expected_counts"] == {"billing_daily": 120, "app_daily": 90}
    assert plan["expected_billing_usd"] == "4434.39"


def test_preflight_rejects_missing_parts(output_dir):
    (output_dir / "app_daily" / "part-00000-abc.parquet").unlink()
    with pytest.raises(ValueError, match="Parquet"):
        loader.preflight(output_dir)


def test_preflight_rejects_bad_reconciliation(output_dir):
    path = output_dir / "quality_metrics.json"
    report = json.loads(path.read_text())
    report["modeled_billed_usd"] = "4433.39"
    path.write_text(json.dumps(report))
    with pytest.raises(ValueError, match="Quality gate FAILED"):
        loader.preflight(output_dir)


def test_identifier_validation_blocks_injection():
    with pytest.raises(ValueError, match="Invalid Google Cloud project"):
        loader.check_identifiers("project`;DROP TABLE foo", "finops_demo")
    with pytest.raises(ValueError, match="Invalid BigQuery dataset"):
        loader.check_identifiers("my-finops-project", "finops.demo")


class FakeClient:
    def __init__(self, amount="4434.39", location="US"):
        self.amount, self.location = amount, location
        self.tables = {}
        self.job_count = 0

    def get_dataset(self, dataset_id):
        return SimpleNamespace(location=self.location)

    def load_table_from_file(self, source, table_id, *, rewind, size, job_config, location):
        assert source.read() == b"PAR1"
        assert size == 4 and location == "US"
        self.job_count += 1
        self.tables[table_id] = 120 if table_id.endswith("billing_daily") else 90
        return SimpleNamespace(result=lambda: None)

    def get_table(self, table_id):
        return SimpleNamespace(num_rows=self.tables[table_id])

    def query(self, sql, location):
        assert "SUM(billed_cost_usd)" in sql
        return SimpleNamespace(result=lambda: [SimpleNamespace(total=Decimal(self.amount))])


class FakeBigQuery:
    class SourceFormat:
        PARQUET = "PARQUET"

    class WriteDisposition:
        WRITE_TRUNCATE = "WRITE_TRUNCATE"

    @staticmethod
    def LoadJobConfig(**kwargs):
        return kwargs


def test_upload_checks_cloud_counts_and_total(output_dir, monkeypatch):
    monkeypatch.setattr(loader, "_consolidate_parts", lambda paths, target: target.write_bytes(b"PAR1"))
    client = FakeClient()
    report = loader.upload(loader.preflight(output_dir), "my-finops-project", "finops_demo", client=client, bq=FakeBigQuery)
    assert report["status"] == "PASS"
    assert report["loaded_counts"]["app_daily"] == 90
    assert client.job_count == 2


def test_upload_rejects_cloud_financial_mismatch(output_dir, monkeypatch):
    monkeypatch.setattr(loader, "_consolidate_parts", lambda paths, target: target.write_bytes(b"PAR1"))
    with pytest.raises(AssertionError, match="billing mismatch"):
        loader.upload(loader.preflight(output_dir), "my-finops-project", "finops_demo", client=FakeClient(amount="4430.00"), bq=FakeBigQuery)


def test_upload_rejects_dataset_region_mismatch(output_dir):
    with pytest.raises(ValueError, match="Dataset region"):
        loader.upload(loader.preflight(output_dir), "my-finops-project", "finops_demo", client=FakeClient(location="EU"), bq=FakeBigQuery)
