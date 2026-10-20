"""Generate deterministic, synthetic (not actual AWS) cloud-finance datasets."""
from __future__ import annotations

import argparse
import csv
import random
from datetime import date, timedelta
from pathlib import Path

SERVICES = (
    ("checkout", "commerce", "AmazonEC2", "compute", 68.0),
    ("catalog", "commerce", "AmazonRDS", "database", 38.0),
    ("streaming", "media", "AmazonS3", "storage", 25.0),
    ("shared", "platform", "AmazonVPC", "network", 16.0),
)


def write_csv(path: Path, fieldnames: list[str], records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)


def generate(output: Path, days: int = 30, seed: int = 42) -> dict[str, int]:
    if days < 1:
        raise ValueError("days must be >= 1")
    rng = random.Random(seed)
    start = date(2026, 9, 1)
    billing, telemetry, usage = [], [], []
    for day in range(days):
        current = (start + timedelta(days=day)).isoformat()
        for app, team, product, category, base in SERVICES:
            cost = round(base * rng.uniform(0.85, 1.20), 2)
            billing.append({
                "usage_date": current,
                "line_item_id": f"SIM-{day:03d}-{app}",
                "line_item_product_code": product,
                "resource_id": f"sim-{app}-resource",
                "application": app,
                "team": team,
                "cost_category": category,
                "unblended_cost_usd": f"{cost:.2f}",
                "usage_quantity": round(cost * 1.7, 3),
                "usage_unit": "synthetic_units",
            })
            if app != "shared":
                cpu = round(rng.uniform(12, 82), 2)
                mem = round(rng.uniform(28, 89), 2)
                telemetry.append({
                    "usage_date": current,
                    "application": app,
                    "namespace": team,
                    "cpu_utilization_pct": cpu,
                    "memory_utilization_pct": mem,
                    "requested_cpu_cores": 4,
                    "requested_memory_gib": 16,
                })
                usage.append({
                    "usage_date": current,
                    "application": app,
                    "product_requests": rng.randint(15000, 90000),
                    "active_users": rng.randint(600, 6000),
                })
    write_csv(output / "billing.csv", list(billing[0]), billing)
    write_csv(output / "k8s_metrics.csv", list(telemetry[0]), telemetry)
    write_csv(output / "product_usage.csv", list(usage[0]), usage)
    return {"billing": len(billing), "k8s_metrics": len(telemetry), "product_usage": len(usage)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("data/raw"))
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    print(generate(args.output, args.days, args.seed))


if __name__ == "__main__":
    main()
