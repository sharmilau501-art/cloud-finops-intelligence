"""Unit tests for deterministic, cloud-independent quality checks."""

from copy import deepcopy
from finops.quality_gate import assess_report


GOOD_REPORT = {
    "source_counts": {"billing": 120, "k8s_metrics": 90, "product_usage": 90},
    "output_counts": {"billing_daily": 120, "app_daily": 90},
    "source_billed_usd": "4434.39",
    "modeled_billed_usd": "4434.39",
    "direct_billed_usd": "3950.37",
    "shared_billed_usd": "484.02",
    "reconciled": True,
}


def test_valid_report_passes():
    assert assess_report(GOOD_REPORT) == []


def test_source_to_model_mismatch_fails():
    report = deepcopy(GOOD_REPORT)
    report["modeled_billed_usd"] = "4433.39"
    assert any("Source billed" in issue for issue in assess_report(report))


def test_shared_cost_reconciliation_fails():
    report = deepcopy(GOOD_REPORT)
    report["shared_billed_usd"] = "484.01"
    assert any("Direct plus shared" in issue for issue in assess_report(report))


def test_missing_joined_app_record_fails():
    report = deepcopy(GOOD_REPORT)
    report["output_counts"]["app_daily"] = 89
    assert any("records may be lost" in issue for issue in assess_report(report))


def test_invalid_count_fails():
    report = deepcopy(GOOD_REPORT)
    report["source_counts"]["billing"] = -1
    assert any("positive integer" in issue for issue in assess_report(report))


def test_reconciled_flag_required():
    report = deepcopy(GOOD_REPORT)
    report["reconciled"] = False
    assert any("reconciled=true" in issue for issue in assess_report(report))


def test_invalid_cost_is_rejected():
    report = deepcopy(GOOD_REPORT)
    report["shared_billed_usd"] = "NaN"
    assert any("nonnegative finite" in issue for issue in assess_report(report))


def test_missing_report_properties_fail():
    assert assess_report({})
