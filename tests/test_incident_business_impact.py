from datetime import datetime

from dvi.detection import Symptom
from dvi.incidents import synthesize_incident
from dvi.lineage import Criticality, load_dbt_manifest
from dvi.rca import ChangeEvent, Observation, RootCauseCandidate

CHANGED = "model.shop.fact_orders"


def _manifest(app_maturity="high", magnitude=0.4):
    return {
        "nodes": {
            CHANGED: {"resource_type": "model", "depends_on": {"nodes": []}},
            "model.shop.revenue_daily": {
                "resource_type": "model",
                "depends_on": {"nodes": [CHANGED]},
            },
        },
        "exposures": {
            "exposure.shop.pricing_api": {
                "name": "pricing_api", "type": "application", "maturity": app_maturity,
                "owner": {"name": "platform"}, "meta": {},
                "depends_on": {"nodes": ["model.shop.revenue_daily"]},
            },
        },
    }


def _candidate(magnitude):
    symptom = Symptom(
        signature="value_substitution", column="country", magnitude=magnitude,
        from_value="UK", to_value="United Kingdom", description="UK -> United Kingdom",
    )
    obs = Observation("model.shop.revenue_daily", datetime(2026, 8, 25, 10, 0), symptom)
    change = ChangeEvent("deploy", datetime(2026, 8, 25, 9, 50), [CHANGED], "deploy")
    return RootCauseCandidate(change=change, score=1.0, explained=[obs], evidence=["e"])


def test_material_incident_under_application_escalates_to_critical():
    g = load_dbt_manifest(_manifest())
    incident = synthesize_incident([_candidate(0.4)], g, [])
    assert incident.severity == "critical"
    assert incident.business_impact is not None
    assert incident.business_impact.max_criticality is Criticality.CRITICAL
    assert "pricing_api" in incident.summary or "application" in incident.summary


def test_immaterial_change_stays_low_despite_critical_consumer():
    g = load_dbt_manifest(_manifest())
    incident = synthesize_incident([_candidate(0.05)], g, [])
    assert incident.severity == "low"


def test_no_exposures_leaves_business_impact_none_and_severity_unchanged():
    g = load_dbt_manifest({"nodes": _manifest()["nodes"]})
    incident = synthesize_incident([_candidate(0.4)], g, [])
    assert incident.business_impact is None
    assert incident.severity == "high"  # propagates to revenue_daily, no escalation
