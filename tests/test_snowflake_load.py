"""Phase 7 local tests. Live Snowflake login is intentionally not needed."""
from decimal import Decimal
from pathlib import Path

import pytest

from finops.snowflake_load import (
    DATASET_NAMES, create_table_sql, expected_summaries, insert_sql,
    table_name, validate_sources,
)


SAMPLE_DATA = Path("data/raw")


def test_validate_sample_data():
    datasets = validate_sources(SAMPLE_DATA)
    assert [d.name for d in datasets] == list(DATASET_NAMES)
    assert [len(d.rows) for d in datasets] == [120, 90, 90]
    assert datasets[0].accepted_usd == Decimal("4434.39")


def test_expected_summary():
    summary = expected_summaries(validate_sources(SAMPLE_DATA))
    assert summary == {
        "billing": 120,
        "k8s_metrics": 90,
        "product_usage": 90,
        "billing_total_usd": Decimal("4434.39"),
    }


@pytest.mark.parametrize("dataset,count", [
    ("billing", 10), ("k8s_metrics", 7), ("product_usage", 4)
])
def test_insert_statement_is_typed_and_parameterized(dataset, count):
    statement = insert_sql(dataset)
    assert statement.startswith(f"INSERT INTO FINOPS_DB.RAW.{dataset.upper()}")
    assert statement.count("%s") == count


def test_create_table_statement():
    query = create_table_sql("billing")
    assert "UNBLENDED_COST_USD DECIMAL(18, 2)" in query
    assert "USAGE_DATE DATE" in query
    assert "CREATE TABLE IF NOT EXISTS FINOPS_DB.RAW.BILLING" in query


def test_bad_identifier_is_rejected():
    with pytest.raises(ValueError, match="Unknown dataset"):
        table_name("billing; DROP TABLE X")


def test_missing_source_files_abort(tmp_path):
    with pytest.raises(FileNotFoundError):
        validate_sources(tmp_path)


def test_invalid_records_abort(tmp_path):
    import csv
    from finops.validation import SCHEMAS
    for name in DATASET_NAMES:
        columns = [c.name for c in SCHEMAS[name]]
        with (tmp_path / f"{name}.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns)
            writer.writeheader()
            writer.writerow({k: "" for k in columns})
    with pytest.raises(ValueError, match="invalid records"):
        validate_sources(tmp_path)
