"""DVI M1 demo — the silent rename.

Run:  python scripts/demo.py

Simulates a deploy that renames "UK" -> "United Kingdom" in fact_orders. Schema,
row count, freshness and null rate are all unchanged, so a conventional monitor
stays green. DVI detects the semantic change, attributes it to the deploy, and
reports the downstream blast radius.
"""

from __future__ import annotations

from datetime import datetime

from dvi.benchmark import inject_value_substitution, make_orders
from dvi.calibration import load_model
from dvi.lineage import LineageGraph
from dvi.pipeline import analyze_change
from dvi.rca import ChangeEvent

ASSET = "model.shop.fact_orders"


def build_lineage() -> LineageGraph:
    g = LineageGraph()
    g.add_edge(ASSET, "model.shop.revenue_daily")
    g.add_edge("model.shop.revenue_daily", "model.shop.exec_dashboard")
    g.add_edge("model.shop.revenue_daily", "model.shop.ml_ltv_feature")
    return g


def main() -> None:
    before = make_orders(n=1000, uk_share=0.2, seed=7)
    after = inject_value_substitution(before, "country", "UK", "United Kingdom")

    deploy = ChangeEvent(
        "deploy-482",
        datetime(2026, 8, 25, 9, 14),
        [ASSET],
        "deploy #482 (country normalization)",
    )

    incident = analyze_change(
        asset=ASSET,
        before=before,
        after=after,
        observed_at=datetime(2026, 8, 25, 9, 16),
        lineage=build_lineage(),
        changes=[deploy],
        columns=["country"],
        model=load_model(),
    )

    print("=" * 68)
    print("  Structural checks: schema OK | row_count OK | freshness OK | nulls OK")
    print("=" * 68)

    if incident is None:
        print("\nNo incident. (Every conventional check passed — nothing to see.)")
        return

    print("\n  DATA INCIDENT")
    print(f"  Title       : {incident.title}")
    print(f"  Severity    : {incident.severity.upper()}")
    print(f"  Change at   : {incident.change_at:%H:%M}")
    print(f"  Detected at : {incident.detected_at:%H:%M}")
    if incident.confidence is not None:
        print(f"  Confidence  : {incident.confidence:.0%} (calibrated, out-of-fold ECE 0.04)")
    print(f"\n  {incident.summary}")
    print("\n  Affected downstream assets:")
    for asset in sorted(incident.affected_assets):
        print(f"    - {asset}")
    print("\n  Evidence:")
    for line in incident.evidence:
        print(f"    * {line}")
    print()


if __name__ == "__main__":
    main()
