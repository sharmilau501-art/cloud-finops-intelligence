"""Transparent, leakage-free seven-day cost baseline for synthetic FinOps data.

No production claim: this is a rolling seven-observation average, with a
walk-forward holdout against a last-observation naive benchmark.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable

CENT = Decimal("0.01")


@dataclass(frozen=True)
class CostPoint:
    usage_date: date
    application: str
    fully_loaded_cost_usd: Decimal


@dataclass(frozen=True)
class ForecastPoint:
    usage_date: date
    application: str
    predicted_cost_usd: Decimal
    forecast_origin_date: date
    model: str = "trailing_7_day_mean"


@dataclass(frozen=True)
class ForecastCheck:
    application: str
    validation_days: int
    mae_usd: Decimal
    wape_pct: Decimal | None
    naive_mae_usd: Decimal
    naive_wape_pct: Decimal | None


def _money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def _error_metrics(actual: list[Decimal], predicted: list[Decimal]) -> tuple[Decimal, Decimal | None]:
    if not actual or len(actual) != len(predicted):
        raise ValueError("Actual and predicted values must be equal-length and nonempty")
    absolute_errors = [abs(a - p) for a, p in zip(actual, predicted)]
    mae = _money(sum(absolute_errors) / len(actual))
    total_actual = sum(abs(v) for v in actual)
    wape = _money(sum(absolute_errors) * 100 / total_actual) if total_actual else None
    return mae, wape


def forecast_application(
    points: Iterable[CostPoint],
    *,
    horizon: int = 7,
    window: int = 7,
    validation_days: int = 7,
) -> tuple[list[ForecastPoint], ForecastCheck]:
    """Return future daily forecasts and walk-forward holdout diagnostics.

    For each of the last `validation_days` dates, its prediction uses *only*
    previous observations. Future forecasts use the mean of the last window
    of observed days and remain constant within the horizon.
    """
    history = sorted(points, key=lambda x: x.usage_date)
    if horizon < 1 or horizon > 30:
        raise ValueError("horizon must be between 1 and 30")
    if window < 2 or validation_days < 1:
        raise ValueError("window must be >= 2 and validation_days must be >= 1")
    if len(history) < window + validation_days:
        raise ValueError("insufficient daily history for rolling holdout validation")
    app = history[0].application
    if not app or app == "shared":
        raise ValueError("forecasts require a non-shared application")
    for i, p in enumerate(history):
        if p.application != app or not p.fully_loaded_cost_usd.is_finite() or p.fully_loaded_cost_usd < 0:
            raise ValueError("invalid application or nonnegative finite USD cost")
        if i and p.usage_date != history[i - 1].usage_date + timedelta(days=1):
            raise ValueError("daily cost history must be unique and gap-free")

    actual: list[Decimal] = []
    predicted: list[Decimal] = []
    naive: list[Decimal] = []
    for i in range(len(history) - validation_days, len(history)):
        actual.append(history[i].fully_loaded_cost_usd)
        predicted.append(sum((v.fully_loaded_cost_usd for v in history[i-window:i]), Decimal(0)) / window)
        naive.append(history[i-1].fully_loaded_cost_usd)
    mae, wape = _error_metrics(actual, predicted)
    naive_mae, naive_wape = _error_metrics(actual, naive)
    check = ForecastCheck(app, validation_days, mae, wape, naive_mae, naive_wape)
    recent = history[-window:]
    future_mean = _money(sum((v.fully_loaded_cost_usd for v in recent), Decimal(0)) / window)
    origin = history[-1].usage_date
    result = [
        ForecastPoint(origin + timedelta(days=day), app, future_mean, origin)
        for day in range(1, horizon + 1)
    ]
    return result, check


def forecast_all(
    points: Iterable[CostPoint], *, horizon: int = 7,
) -> tuple[list[ForecastPoint], list[ForecastCheck]]:
    by_app: dict[str, list[CostPoint]] = defaultdict(list)
    for p in points:
        by_app[p.application].append(p)
    if not by_app:
        raise ValueError("No cost points to forecast")
    forecasts: list[ForecastPoint] = []
    checks: list[ForecastCheck] = []
    origins: set[date] = set()
    for app in sorted(by_app):
        rows, check = forecast_application(by_app[app], horizon=horizon)
        forecasts.extend(rows)
        checks.append(check)
        origins.add(rows[0].forecast_origin_date)
    if len(origins) != 1:
        raise ValueError("Applications must end on the same observed date")
    return forecasts, checks
