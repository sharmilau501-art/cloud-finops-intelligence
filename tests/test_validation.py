"""Pure validation tests. These run even without DuckDB installed."""
import csv

import pytest

from finops.generate_data import generate
from finops.validation import load_and_validate_csv, parse_value


def edit_csv(path, edit):
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        cols = reader.fieldnames
        rows = list(reader)
    edit(rows)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=cols)
        writer.writeheader()
        writer.writerows(rows)


def test_clean_synthetic_data(tmp_path):
    generate(tmp_path, days=30, seed=42)
    for name, expected in {"billing": 120, "k8s_metrics": 90, "product_usage": 90}.items():
        dataset = load_and_validate_csv(name, tmp_path)
        assert len(dataset.rows) == expected
        assert dataset.source_count == expected
        assert not dataset.rejected
    billing = load_and_validate_csv("billing", tmp_path)
    assert billing.accepted_usd == billing.source_parseable_usd
    assert billing.unparseable_amount_rows == 0


def test_negative_cost_and_duplicate_billing_key_quarantined(tmp_path):
    generate(tmp_path, days=2)
    def corrupt(rows):
        duplicate = rows[0].copy()
        rows[1]["unblended_cost_usd"] = "-13.00"
        rows.append(duplicate)
    edit_csv(tmp_path / "billing.csv", corrupt)
    result = load_and_validate_csv("billing", tmp_path)
    assert result.source_count == 9
    assert len(result.rows) == 7
    assert len(result.rejected) == 2
    assert any("negative" in ";".join(x.reasons) for x in result.rejected)
    assert any("duplicate business key" in ";".join(x.reasons) for x in result.rejected)
    assert result.unparseable_amount_rows == 1


def test_invalid_percentage_and_usage_requests(tmp_path):
    generate(tmp_path, days=2)
    edit_csv(tmp_path / "k8s_metrics.csv", lambda r: r[0].update(cpu_utilization_pct="125"))
    edit_csv(tmp_path / "product_usage.csv", lambda r: r[0].update(product_requests="-20"))
    bad_k8s = load_and_validate_csv("k8s_metrics", tmp_path)
    bad_usage = load_and_validate_csv("product_usage", tmp_path)
    assert len(bad_k8s.rejected) == 1
    assert len(bad_usage.rejected) == 1
    assert "percentage" in ";".join(bad_k8s.rejected[0].reasons)
    assert "nonnegative" in ";".join(bad_usage.rejected[0].reasons)


def test_missing_or_extra_csv_columns_raise(tmp_path):
    generate(tmp_path, days=2)
    file = tmp_path / "billing.csv"
    text = file.read_text(encoding="utf-8")
    file.write_text(text.replace("line_item_id,", "bad_column,", 1), encoding="utf-8")
    with pytest.raises(ValueError, match="header mismatch"):
        load_and_validate_csv("billing", tmp_path)


@pytest.mark.parametrize("value,kind", [
    ("NaN", "money"), ("12.345", "money"), ("infinity", "percentage"),
    ("2026-02-30", "date"), ("2.5", "nonnegative_integer"),
    ("0", "positive_float"),
])
def test_invalid_data_types(value, kind):
    with pytest.raises(ValueError):
        parse_value(value, kind)
