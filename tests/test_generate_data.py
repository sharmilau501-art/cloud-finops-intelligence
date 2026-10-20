import csv
from pathlib import Path

import pytest

from finops.generate_data import generate


def rows(path: Path):
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_expected_counts(tmp_path):
    assert generate(tmp_path, days=30) == {"billing": 120, "k8s_metrics": 90, "product_usage": 90}
    assert len(rows(tmp_path / "billing.csv")) == 120
    assert len(rows(tmp_path / "k8s_metrics.csv")) == 90
    assert len(rows(tmp_path / "product_usage.csv")) == 90


def test_unique_line_items_and_nonnegative_costs(tmp_path):
    generate(tmp_path)
    billing = rows(tmp_path / "billing.csv")
    ids = [r["line_item_id"] for r in billing]
    assert len(ids) == len(set(ids))
    assert all(float(r["unblended_cost_usd"]) >= 0 for r in billing)


def test_reproducibility(tmp_path):
    first, second = tmp_path / "first", tmp_path / "second"
    generate(first, seed=42)
    generate(second, seed=42)
    assert (first / "billing.csv").read_bytes() == (second / "billing.csv").read_bytes()


def test_invalid_day_count(tmp_path):
    with pytest.raises(ValueError, match="days"):
        generate(tmp_path, days=0)
