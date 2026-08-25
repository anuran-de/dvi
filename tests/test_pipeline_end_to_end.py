"""The M1 hypothesis test.

A transformation silently renames a category ("UK" -> "United Kingdom"). Schema,
row count, freshness and null rate are all unchanged. DVI must still detect the
change, attribute it to the deploy, and report the downstream blast radius.
"""

from datetime import datetime

from dvi.benchmark import inject_value_substitution, make_orders
from dvi.incidents import Incident
from dvi.lineage import LineageGraph
from dvi.pipeline import analyze_change
from dvi.rca import ChangeEvent

ASSET = "model.shop.fact_orders"


def _lineage() -> LineageGraph:
    g = LineageGraph()
    g.add_edge(ASSET, "model.shop.revenue_daily")
    g.add_edge("model.shop.revenue_daily", "model.shop.exec_dashboard")
    return g


def test_detects_attributes_and_scopes_the_silent_rename():
    before = make_orders(n=1000, uk_share=0.2, seed=7)
    after = inject_value_substitution(before, "country", "UK", "United Kingdom")

    deploy = ChangeEvent(
        "deploy-482", datetime(2026, 8, 25, 9, 14), [ASSET], "deploy #482"
    )

    incident = analyze_change(
        asset=ASSET,
        before=before,
        after=after,
        observed_at=datetime(2026, 8, 25, 9, 16),
        lineage=_lineage(),
        changes=[deploy],
        columns=["country"],
    )

    assert isinstance(incident, Incident)
    assert incident.primary_cause.change.id == "deploy-482"
    worst = incident.primary_cause.explained[0].symptom
    assert worst.from_value == "UK"
    assert worst.to_value == "United Kingdom"
    assert incident.severity == "high"
    assert incident.affected_assets >= {
        "model.shop.revenue_daily",
        "model.shop.exec_dashboard",
    }


def test_no_incident_without_a_corroborating_change():
    before = make_orders(n=1000, uk_share=0.2, seed=7)
    after = inject_value_substitution(before, "country", "UK", "United Kingdom")

    incident = analyze_change(
        asset=ASSET,
        before=before,
        after=after,
        observed_at=datetime(2026, 8, 25, 9, 16),
        lineage=_lineage(),
        changes=[],  # no deployment recorded
        columns=["country"],
    )

    # A real change happened, but with nothing to corroborate it, DVI keeps it a
    # symptom rather than crying "incident".
    assert incident is None
