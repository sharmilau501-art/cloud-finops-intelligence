"""Strict CSV validation before records enter the DuckDB warehouse.

These datasets are simulated and intentionally small. All rules are explicit to
make ingestion behavior auditable and testable.
"""
from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Column:
    name: str
    logical_type: str
    sql_type: str


SCHEMAS: dict[str, tuple[Column, ...]] = {
    "billing": (
        Column("usage_date", "date", "DATE"),
        Column("line_item_id", "string", "VARCHAR"),
        Column("line_item_product_code", "string", "VARCHAR"),
        Column("resource_id", "string", "VARCHAR"),
        Column("application", "string", "VARCHAR"),
        Column("team", "string", "VARCHAR"),
        Column("cost_category", "string", "VARCHAR"),
        Column("unblended_cost_usd", "money", "DECIMAL(18, 2)"),
        Column("usage_quantity", "nonnegative_float", "DOUBLE"),
        Column("usage_unit", "string", "VARCHAR"),
    ),
    "k8s_metrics": (
        Column("usage_date", "date", "DATE"),
        Column("application", "string", "VARCHAR"),
        Column("namespace", "string", "VARCHAR"),
        Column("cpu_utilization_pct", "percentage", "DOUBLE"),
        Column("memory_utilization_pct", "percentage", "DOUBLE"),
        Column("requested_cpu_cores", "positive_float", "DOUBLE"),
        Column("requested_memory_gib", "positive_float", "DOUBLE"),
    ),
    "product_usage": (
        Column("usage_date", "date", "DATE"),
        Column("application", "string", "VARCHAR"),
        Column("product_requests", "nonnegative_integer", "BIGINT"),
        Column("active_users", "nonnegative_integer", "BIGINT"),
    ),
}


@dataclass(frozen=True)
class Rejected:
    row_number: int  # physical CSV line number, including the header
    reasons: tuple[str, ...]
    raw_json: str


@dataclass
class ValidatedDataset:
    name: str
    rows: list[tuple[Any, ...]]
    rejected: list[Rejected]
    source_count: int
    source_parseable_usd: Decimal = Decimal("0.00")
    accepted_usd: Decimal = Decimal("0.00")
    rejected_parseable_usd: Decimal = Decimal("0.00")
    unparseable_amount_rows: int = 0


def parse_value(raw: str | None, kind: str) -> Any:
    if raw is None or not raw.strip():
        raise ValueError("missing value")
    value = raw.strip()
    if kind == "string":
        return value
    if kind == "date":
        try:
            return date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("invalid ISO date") from exc
    if kind == "money":
        try:
            amount = Decimal(value)
        except InvalidOperation as exc:
            raise ValueError("invalid currency amount") from exc
        if not amount.is_finite() or amount < 0 or amount.as_tuple().exponent < -2:
            raise ValueError("cost must be nonnegative with at most 2 decimal places")
        if amount >= Decimal("10000000000000000"):
            raise ValueError("currency amount exceeds DECIMAL(18,2)")
        return amount.quantize(Decimal("0.01"))
    if kind == "nonnegative_integer":
        try:
            result = int(value)
        except ValueError as exc:
            raise ValueError("expected integer") from exc
        if result < 0 or result > 9_223_372_036_854_775_807:
            raise ValueError("integer must be nonnegative and fit BIGINT")
        return result
    try:
        result = float(value)
    except ValueError as exc:
        raise ValueError("expected number") from exc
    if not math.isfinite(result):
        raise ValueError("number must be finite")
    if kind == "nonnegative_float" and result < 0:
        raise ValueError("quantity must be nonnegative")
    if kind == "positive_float" and result <= 0:
        raise ValueError("requested capacity must be positive")
    if kind == "percentage" and not (0 <= result <= 100):
        raise ValueError("percentage must be between 0 and 100")
    return result


def load_and_validate_csv(name: str, raw_dir: Path) -> ValidatedDataset:
    if name not in SCHEMAS:
        raise ValueError(f"unknown dataset: {name}")
    path = raw_dir / f"{name}.csv"
    if not path.is_file():
        raise FileNotFoundError(f"missing dataset: {path}")

    result = ValidatedDataset(name=name, rows=[], rejected=[], source_count=0)
    columns = SCHEMAS[name]
    expected_columns = [col.name for col in columns]
    seen_keys: set[Any] = set()

    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != expected_columns:
            raise ValueError(
                f"{path.name} CSV header mismatch. Expected {expected_columns}; "
                f"received {reader.fieldnames}. Fix schema before ingestion."
            )
        for row in reader:
            result.source_count += 1
            reasons: list[str] = []
            converted: dict[str, Any] = {}

            # Track independently parseable raw billing amounts, including
            # those on rows rejected for a different field.
            raw_cost: Decimal | None = None
            if name == "billing":
                try:
                    raw_cost = parse_value(row.get("unblended_cost_usd"), "money")
                    result.source_parseable_usd += raw_cost
                except ValueError:
                    result.unparseable_amount_rows += 1

            for col in columns:
                try:
                    converted[col.name] = parse_value(row.get(col.name), col.logical_type)
                except ValueError as exc:
                    reasons.append(f"{col.name}: {exc}")
            if None in row:
                reasons.append("unexpected extra CSV value(s)")

            if not reasons:
                if name == "billing":
                    key = converted["line_item_id"]
                else:
                    key = (converted["usage_date"], converted["application"])
                if key in seen_keys:
                    reasons.append(f"duplicate business key: {key}")
                else:
                    seen_keys.add(key)

            if reasons:
                # JSON keys must be strings (DictReader uses None for extra data).
                raw_for_json = {str(k) if k is not None else "__extra__": v for k, v in row.items()}
                result.rejected.append(
                    Rejected(
                        row_number=reader.line_num,
                        reasons=tuple(reasons),
                        raw_json=json.dumps(raw_for_json, sort_keys=True),
                    )
                )
                if raw_cost is not None:
                    result.rejected_parseable_usd += raw_cost
            else:
                result.rows.append(tuple(converted[col.name] for col in columns))
                if raw_cost is not None:
                    result.accepted_usd += raw_cost

    if result.source_count != len(result.rows) + len(result.rejected):
        raise AssertionError("source/accepted/rejected count mismatch")
    if name == "billing" and (
        result.source_parseable_usd != result.accepted_usd + result.rejected_parseable_usd
    ):
        raise AssertionError("billing source amount partition mismatch")
    return result
