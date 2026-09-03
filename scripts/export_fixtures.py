"""Generate operator-UI fixtures from REAL DVI pipeline runs.

Runs the same detection path the CLI uses (`analyze_change`) over constructed
before/after scenarios with hand-built lineage, then serializes each resulting
Incident into the JSON shape the web app consumes. Detection, severity,
evidence, blast radius, and business impact are all real engine output — only
the input scenario (data + lineage + change) is constructed, exactly as
scripts/demo.py does. No incident field is hand-authored.

Run:  python scripts/export_fixtures.py
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import polars as pl

from dvi.benchmark import inject_value_substitution, make_orders
from dvi.calibration import load_model
from dvi.incidents import Incident
from dvi.lineage import Criticality, Exposure, LineageGraph
from dvi.pipeline import analyze_change
from dvi.rca import ChangeEvent

DEFAULT_OUT = Path(__file__).resolve().parent.parent / "dvi" / "content" / "incidents"


@dataclass(frozen=True)
class Scenario:
    id: str
    asset: str
    change_id: str
    change_label: str
    lineage: LineageGraph
    seed: int
    uk_share: float
    change_at: datetime
    observed_at: datetime


def _leaf_lineage(asset: str, exposures: list[Exposure]) -> LineageGraph:
    """Changed asset is a leaf (no downstream data); exposures hang off it."""
    g = LineageGraph()
    g.add_node(asset, kind="data")
    for e in exposures:
        g.add_node(e.unique_id, kind="exposure", exposure=e)
        for dep in e.depends_on:
            g.add_edge(dep, e.unique_id)
    return g


def _chain_lineage(asset: str, downstream: str, exposures: list[Exposure]) -> LineageGraph:
    """Changed asset -> one downstream data asset; exposures hang off downstream."""
    g = LineageGraph()
    g.add_node(asset, kind="data")
    g.add_node(downstream, kind="data")
    g.add_edge(asset, downstream)
    for e in exposures:
        g.add_node(e.unique_id, kind="exposure", exposure=e)
        for dep in e.depends_on:
            g.add_edge(dep, e.unique_id)
    return g


def _scenarios() -> list[Scenario]:
    # 1. CRITICAL: change propagates to a downstream data asset (base high) and
    #    reaches a customer-facing application at CRITICAL criticality -> critical.
    s1_asset, s1_down = "model.shop.fct_orders", "model.shop.revenue_daily"
    s1 = Scenario(
        "critical-pricing-api",
        s1_asset,
        "deploy-482",
        "deploy #482 (country normalization)",
        _chain_lineage(
            s1_asset,
            s1_down,
            [
                Exposure(
                    "exposure.shop.pricing_api", "pricing_api", "application",
                    Criticality.CRITICAL, "platform", "https://api/pricing",
                    frozenset({s1_down}),
                ),
                Exposure(
                    "exposure.shop.exec_dashboard", "exec_dashboard", "dashboard",
                    Criticality.HIGH, "jane", "https://bi/exec",
                    frozenset({s1_down}),
                ),
            ],
        ),
        seed=7,
        uk_share=0.20,
        change_at=datetime(2026, 8, 25, 9, 14),
        observed_at=datetime(2026, 8, 25, 9, 16),
    )

    # 2. HIGH: change is a leaf (base medium); a HIGH-criticality dashboard hangs
    #    directly off it -> escalates medium -> high.
    s2_asset = "model.marketing.dim_country"
    s2 = Scenario(
        "high-marketing-dashboard",
        s2_asset,
        "pr-1187",
        "PR #1187 (dim_country refactor)",
        _leaf_lineage(
            s2_asset,
            [
                Exposure(
                    "exposure.marketing.campaign_dash", "campaign_dashboard", "dashboard",
                    Criticality.HIGH, "marketing-ops", "https://bi/campaign",
                    frozenset({s2_asset}),
                ),
            ],
        ),
        seed=23,
        uk_share=0.28,
        change_at=datetime(2026, 8, 24, 22, 47),
        observed_at=datetime(2026, 8, 25, 6, 32),
    )

    # 3. MEDIUM: change is a leaf (base medium) with NO exposures downstream ->
    #    stays medium, no business impact.
    s3_asset = "model.finance.stg_ledger"
    s3 = Scenario(
        "medium-ledger-refactor",
        s3_asset,
        "pr-1203",
        "PR #1203 (ledger country cleanup)",
        _leaf_lineage(s3_asset, []),
        seed=41,
        uk_share=0.10,
        change_at=datetime(2026, 8, 25, 11, 3),
        observed_at=datetime(2026, 8, 25, 11, 9),
    )

    return [s1, s2, s3]


def _impact(incident: Incident) -> dict | None:
    bi = incident.business_impact
    if bi is None:
        return None
    return {
        "exposures": [
            {
                "name": e.name,
                "type": e.type,
                "criticality": e.criticality.name,
                "owner": e.owner,
            }
            for e in bi.exposures
        ],
        "maxCriticality": bi.max_criticality.name if bi.max_criticality else None,
    }


def _serialize(scenario: Scenario, incident: Incident) -> dict:
    top = incident.primary_cause
    return {
        "id": scenario.id,
        "asset": scenario.asset,
        "severity": incident.severity,
        "title": incident.title,
        "summary": incident.summary,
        "confidence": incident.confidence,
        "evidence": list(incident.evidence),
        "affectedAssets": sorted(incident.affected_assets),
        "changeAt": incident.change_at.isoformat() if incident.change_at else "",
        "detectedAt": incident.detected_at.isoformat() if incident.detected_at else "",
        "rootCause": {
            "label": top.change.label or top.change.id,
            "targets": sorted(top.change.targets),
            "timestamp": top.change.timestamp.isoformat(),
        },
        "businessImpact": _impact(incident),
    }


def main(out_dir: Path = DEFAULT_OUT) -> list[dict]:
    out_dir.mkdir(parents=True, exist_ok=True)
    model = load_model()

    written: list[dict] = []
    for scenario in _scenarios():
        # Real detection input, per scenario: a silent category rename that passes
        # every structural check. make_orders + inject_value_substitution are the
        # same proven helpers scripts/demo.py uses.
        before: pl.DataFrame = make_orders(n=1000, uk_share=scenario.uk_share, seed=scenario.seed)
        after: pl.DataFrame = inject_value_substitution(before, "country", "UK", "United Kingdom")
        change = ChangeEvent(
            scenario.change_id, scenario.change_at, [scenario.asset], scenario.change_label
        )
        incident = analyze_change(
            asset=scenario.asset,
            before=before,
            after=after,
            observed_at=scenario.observed_at,
            lineage=scenario.lineage,
            changes=[change],
            columns=["country"],
            model=model,
        )
        if incident is None:
            continue
        payload = _serialize(scenario, incident)
        (out_dir / f"{payload['id']}.json").write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n"
        )
        written.append(payload)

    written.sort(key=lambda p: p["id"])
    index = [
        {
            "id": p["id"],
            "asset": p["asset"],
            "severity": p["severity"],
            "title": p["title"],
            "confidence": p["confidence"],
            "detectedAt": p["detectedAt"],
            "changeAt": p["changeAt"],
        }
        for p in written
    ]
    (out_dir / "index.json").write_text(json.dumps(index, indent=2) + "\n")
    return written


if __name__ == "__main__":
    written = main()
    print(f"Wrote {len(written)} incident fixtures to {DEFAULT_OUT}")
