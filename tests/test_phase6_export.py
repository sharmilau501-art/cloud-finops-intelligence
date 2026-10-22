from datetime import date
from decimal import Decimal

import pytest

from finops.phase6_export import validate_cost_export, write_csv


def row(usage_date, app, direct='10.00', allocated='1.00', fully='11.00'):
    return (usage_date, app, 1000, Decimal(direct), Decimal(allocated), Decimal(fully), Decimal('11.00'), 'request_share')


def test_financial_reconciliation_ok():
    entries = [row(date(2026, 9, 1), 'catalog'), row(date(2026, 9, 1), 'checkout')]
    validate_cost_export(entries, Decimal('22.00'))


def test_missing_cost_fails():
    with pytest.raises(ValueError, match='reconciliation'):
        validate_cost_export([row(date(2026, 9, 1), 'catalog')], Decimal('12.00'))


def test_duplicate_key_fails():
    item = row(date(2026, 9, 1), 'catalog')
    with pytest.raises(ValueError, match='Duplicate'):
        validate_cost_export([item, item], Decimal('22.00'))


def test_reject_shared_fact():
    with pytest.raises(ValueError, match='shared'):
        validate_cost_export([row(date(2026, 9, 1), 'shared')], Decimal('11.00'))


def test_csv_writes_currency_and_true_false(tmp_path):
    path = tmp_path / 'out.csv'
    write_csv(path, ['usage_date', 'amount', 'flag', 'app'],
              [(date(2026, 9, 1), Decimal('11.20'), True, 'catalog')])
    assert path.read_text().splitlines() == [
        'usage_date,amount,flag,app', '2026-09-01,11.20,true,catalog'
    ]
