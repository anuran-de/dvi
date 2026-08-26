from dvi.incidents.impact import (
    BusinessImpact,
    assess_impact,
    criticality_to_severity,
    escalate_severity,
    render_business_impact,
)
from dvi.lineage import Criticality, load_dbt_manifest


def _manifest():
    return {
        "nodes": {
            "model.shop.fact_orders": {"resource_type": "model", "depends_on": {"nodes": []}},
            "model.shop.revenue_daily": {
                "resource_type": "model",
                "depends_on": {"nodes": ["model.shop.fact_orders"]},
            },
        },
        "exposures": {
            "exposure.shop.exec_dashboard": {
                "name": "exec_dashboard", "type": "dashboard", "maturity": "high",
                "owner": {"name": "jane"}, "meta": {},
                "depends_on": {"nodes": ["model.shop.revenue_daily"]},
            },
            "exposure.shop.pricing_api": {
                "name": "pricing_api", "type": "application", "maturity": "high",
                "owner": {"name": "platform"}, "meta": {},
                "depends_on": {"nodes": ["model.shop.revenue_daily"]},
            },
        },
    }


def test_assess_impact_groups_by_type_and_records_worst():
    g = load_dbt_manifest(_manifest())
    impact = assess_impact({"model.shop.fact_orders"}, g)
    assert impact.max_criticality is Criticality.CRITICAL
    assert set(impact.by_type) == {"dashboard", "application"}
    assert [e.name for e in impact.by_type["application"]] == ["pricing_api"]


def test_assess_impact_empty_when_no_exposures_downstream():
    g = load_dbt_manifest({"nodes": _manifest()["nodes"]})
    impact = assess_impact({"model.shop.fact_orders"}, g)
    assert impact.exposures == ()
    assert impact.max_criticality is None
    assert render_business_impact(impact) == []


def test_criticality_to_severity_mapping():
    assert criticality_to_severity(Criticality.LOW) == "low"
    assert criticality_to_severity(Criticality.MEDIUM) == "medium"
    assert criticality_to_severity(Criticality.HIGH) == "high"
    assert criticality_to_severity(Criticality.CRITICAL) == "critical"


def _impact(max_crit):
    return BusinessImpact(exposures=(), by_type={}, max_criticality=max_crit)


def test_escalation_raises_to_critical_when_material():
    assert escalate_severity("medium", _impact(Criticality.CRITICAL), 0.5) == "critical"


def test_escalation_never_lowers_severity():
    assert escalate_severity("high", _impact(Criticality.LOW), 0.5) == "high"


def test_escalation_is_gated_on_materiality():
    # Immaterial magnitude: a critical consumer must NOT lift severity off "low".
    assert escalate_severity("low", _impact(Criticality.CRITICAL), 0.05) == "low"


def test_escalation_noop_when_no_external_impact():
    assert escalate_severity("medium", _impact(None), 0.9) == "medium"


def test_render_is_grouped_ordered_and_shows_owners():
    g = load_dbt_manifest(_manifest())
    impact = assess_impact({"model.shop.fact_orders"}, g)
    lines = render_business_impact(impact)
    assert lines[0].strip() == "Business impact:"
    # application group precedes dashboard group (fixed type order).
    body = "\n".join(lines)
    assert body.index("pricing_api") < body.index("exec_dashboard")
    assert "@platform" in body and "@jane" in body
    assert "CRITICAL" in body
