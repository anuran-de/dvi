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
from dvi.incidents import render_business_impact
from dvi.lineage import Criticality, Exposure, LineageGraph
from dvi.pipeline import analyze_change
from dvi.rca import ChangeEvent

ASSET = "model.shop.fact_orders"


def build_lineage() -> LineageGraph:
    g = LineageGraph()
    g.add_node(ASSET, kind="data")
    g.add_node("model.shop.revenue_daily", kind="data")
    g.add_edge(ASSET, "model.shop.revenue_daily")

    exec_dash = Exposure(
        "exposure.shop.exec_dashboard", "exec_dashboard", "dashboard",
        Criticality.HIGH, "jane", "https://bi/exec",
        frozenset({"model.shop.revenue_daily"}),
    )
    pricing_api = Exposure(
        "exposure.shop.pricing_api", "pricing_api", "application",
        Criticality.CRITICAL, "platform", "https://api/pricing",
        frozenset({"model.shop.revenue_daily"}),
    )
    for e in (exec_dash, pricing_api):
        g.add_node(e.unique_id, kind="exposure", exposure=e)
        for dep in e.depends_on:
            g.add_edge(dep, e.unique_id)
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

    model = load_model()
    incident = analyze_change(
        asset=ASSET,
        before=before,
        after=after,
        observed_at=datetime(2026, 8, 25, 9, 16),
        lineage=build_lineage(),
        changes=[deploy],
        columns=["country"],
        model=model,
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
        ece = model.metadata.get("kfold_ece")
        ece_note = f", out-of-fold ECE {ece:.2f}" if ece is not None else ""
        print(f"  Confidence  : {incident.confidence:.0%} (calibrated{ece_note})")
    print(f"\n  {incident.summary}")
    print("\n  Affected downstream assets:")
    for asset in sorted(incident.affected_assets):
        print(f"    - {asset}")
    if incident.business_impact is not None:
        print()
        for line in render_business_impact(incident.business_impact):
            print(line)
    print("\n  Evidence:")
    for line in incident.evidence:
        print(f"    * {line}")
    print()


if __name__ == "__main__":
    main()
