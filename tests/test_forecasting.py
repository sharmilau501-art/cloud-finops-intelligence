from datetime import date, timedelta
from decimal import Decimal

import pytest

from finops.forecasting import CostPoint, forecast_all, forecast_application

START = date(2026, 9, 1)


def make_points(app='catalog', n=30, value='10.00'):
    return [CostPoint(START + timedelta(days=i), app, Decimal(value)) for i in range(n)]


def test_forecast_stays_outside_training_range():
    f, checks = forecast_application(make_points())
    assert len(f) == 7
    assert f[0].usage_date == START + timedelta(days=30)
    assert f[-1].usage_date == START + timedelta(days=36)
    assert all(p.predicted_cost_usd == Decimal('10.00') for p in f)
    assert checks.mae_usd == Decimal('0.00')
    assert checks.naive_mae_usd == Decimal('0.00')


def test_rolling_backtest_does_not_look_ahead():
    points = make_points()
    points[-1] = CostPoint(points[-1].usage_date, 'catalog', Decimal('710.00'))
    forecasts, check = forecast_application(points)
    # Final-day spike is NOT included in the prediction for that final holdout day.
    # Earlier holdout days cost $10.00 each; final actual is $710.00.
    assert check.mae_usd == Decimal('100.00')
    assert forecasts[0].predicted_cost_usd == Decimal('110.00')


def test_nonconsecutive_dates_fail():
    points = make_points()
    points[5] = CostPoint(points[5].usage_date + timedelta(days=2), 'catalog', Decimal('10.00'))
    with pytest.raises(ValueError, match='gap-free'):
        forecast_application(points)


def test_duplicate_dates_fail():
    points = make_points()
    points[9] = points[8]
    with pytest.raises(ValueError, match='gap-free'):
        forecast_application(points)


def test_negative_amounts_fail():
    points = make_points()
    points[6] = CostPoint(points[6].usage_date, 'catalog', Decimal('-2.00'))
    with pytest.raises(ValueError, match='nonnegative'):
        forecast_application(points)


def test_too_few_days_fail():
    with pytest.raises(ValueError, match='insufficient'):
        forecast_application(make_points(n=13))


def test_horizon_restricted():
    with pytest.raises(ValueError, match='horizon'):
        forecast_application(make_points(), horizon=0)


def test_zero_actuals_have_no_wape():
    f, check = forecast_application(make_points(value='0.00'))
    assert check.wape_pct is None
    assert check.naive_wape_pct is None
    assert all(p.predicted_cost_usd == 0 for p in f)


def test_uses_same_last_date_across_apps():
    cat = make_points('catalog')
    checkout = make_points('checkout')
    f, checks = forecast_all(cat + checkout)
    assert len(f) == 14 and len(checks) == 2
    assert {p.application for p in f} == {'checkout', 'catalog'}


def test_mismatched_app_date_fails():
    catalog = make_points('catalog')
    checkout = make_points('checkout')[:-1]
    with pytest.raises(ValueError, match='same observed date'):
        forecast_all(catalog + checkout)


def test_shared_not_forecast():
    with pytest.raises(ValueError, match='non-shared'):
        forecast_application(make_points('shared'))
