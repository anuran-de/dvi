from datetime import datetime

from dvi.detection import Symptom
from dvi.incidents import Incident, synthesize_incident
from dvi.lineage import LineageGraph
from dvi.rca import ChangeEvent, Observation, rank_root_causes


def _lineage() -> LineageGraph:
    g = LineageGraph()
    g.add_edge("model.shop.fact_orders", "model.shop.revenue_daily")
    g.add_edge("model.shop.revenue_daily", "model.shop.exec_dashboard")
    return g


def _observation() -> Observation:
    sym = Symptom(
        signature="value_substitution",
        column="country",
        magnitude=0.2,
        from_value="UK",
        to_value="United Kingdom",
        description="Value 'UK' (20.0%) appears replaced by 'United Kingdom' (19.8%).",
    )
    return Observation("model.shop.fact_orders", datetime(2026, 8, 25, 9, 16), sym)


def test_no_incident_when_no_corroborated_cause():
    incident = synthesize_incident([], _lineage(), [_observation()])
    assert incident is None


def test_builds_incident_from_top_candidate():
    changes = [
        ChangeEvent("c1", datetime(2026, 8, 25, 9, 14), ["model.shop.fact_orders"], "deploy #482")
    ]
    ranked = rank_root_causes([_observation()], changes, _lineage())

    incident = synthesize_incident(ranked, _lineage(), [_observation()])

    assert isinstance(incident, Incident)
    assert incident.primary_cause.change.id == "c1"
    # propagates downstream of the changed model -> high severity
    assert incident.severity == "high"
    assert "model.shop.revenue_daily" in incident.affected_assets
    assert "model.shop.exec_dashboard" in incident.affected_assets


def test_incident_evidence_is_carried_from_the_cause():
    changes = [
        ChangeEvent("c1", datetime(2026, 8, 25, 9, 14), ["model.shop.fact_orders"], "deploy #482")
    ]
    ranked = rank_root_causes([_observation()], changes, _lineage())

    incident = synthesize_incident(ranked, _lineage(), [_observation()])

    assert any("deploy #482" in line for line in incident.evidence)
    assert "United Kingdom" in incident.summary
