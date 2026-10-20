"""Pure-Python reference allocator for independent unit testing.

The production dbt model uses equivalent largest-remainder allocation.
All amounts here are integer cents; weights are request counts.
"""
from __future__ import annotations

from collections.abc import Mapping


def allocate_shared_cents(shared_cents: int, daily_requests: Mapping[str, int]) -> dict[str, int]:
    """Return exact cents per consumer, with deterministic tie-breaking by name.

    Zero-total requests use equal weighting. A day with no consumers is an
    error rather than silently dropping its shared charges.
    """
    if not isinstance(shared_cents, int) or isinstance(shared_cents, bool) or shared_cents < 0:
        raise ValueError("shared_cents must be a nonnegative integer")
    if not daily_requests:
        raise ValueError("at least one consumer is required")
    if any(
        not isinstance(v, int) or isinstance(v, bool) or v < 0
        for v in daily_requests.values()
    ):
        raise ValueError("request counts must be nonnegative integers")
    if any(not isinstance(k, str) or not k for k in daily_requests):
        raise ValueError("application names must be nonempty strings")

    total_requests = sum(daily_requests.values())
    weights = dict(daily_requests) if total_requests else {app: 1 for app in daily_requests}
    total_weight = sum(weights.values())
    parts = {app: divmod(shared_cents * w, total_weight) for app, w in weights.items()}
    allocated = {app: base for app, (base, _) in parts.items()}
    remaining = shared_cents - sum(allocated.values())
    priority = sorted(parts, key=lambda app: (-parts[app][1], app))
    for app in priority[:remaining]:
        allocated[app] += 1
    assert sum(allocated.values()) == shared_cents
    return allocated
