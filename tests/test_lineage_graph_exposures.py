from dvi.lineage import Criticality, load_dbt_manifest


def _manifest():
    return {
        "nodes": {
            "model.shop.fact_orders": {"resource_type": "model", "depends_on": {"nodes": []}},
            "model.shop.revenue_daily": {
                "resource_type": "model",
                "depends_on": {"nodes": ["model.shop.fact_orders"]},
            },
            "model.shop.other": {"resource_type": "model", "depends_on": {"nodes": []}},
        },
        "exposures": {
            "exposure.shop.exec_dashboard": {
                "name": "exec_dashboard",
                "type": "dashboard",
                "maturity": "high",
                "owner": {"name": "jane"},
                "url": "https://bi/exec",
                "meta": {},
                "depends_on": {"nodes": ["model.shop.revenue_daily"]},
            },
            "exposure.shop.pricing_api": {
                "name": "pricing_api",
                "type": "application",
                "maturity": "high",
                "owner": {"email": "platform@shop"},
                "meta": {},
                "depends_on": {"nodes": ["model.shop.other"]},
            },
        },
    }


def test_exposures_become_kind_tagged_nodes():
    g = load_dbt_manifest(_manifest())
    assert "exposure.shop.exec_dashboard" in g.nodes
    assert g.node_kind("exposure.shop.exec_dashboard") == "exposure"
    assert g.node_kind("model.shop.fact_orders") == "data"


def test_exposure_reachable_downstream_of_upstream_model():
    g = load_dbt_manifest(_manifest())
    # fact_orders -> revenue_daily -> exec_dashboard
    exposures = g.exposures_downstream_of({"model.shop.fact_orders"})
    ids = [e.unique_id for e in exposures]
    assert ids == ["exposure.shop.exec_dashboard"]
    assert exposures[0].criticality is Criticality.HIGH
    assert exposures[0].owner == "jane"


def test_exposures_downstream_sorted_by_criticality_then_name():
    g = load_dbt_manifest(_manifest())
    # From both roots: pricing_api (CRITICAL) must sort before exec_dashboard (HIGH).
    exposures = g.exposures_downstream_of(
        {"model.shop.fact_orders", "model.shop.other"}
    )
    assert [e.unique_id for e in exposures] == [
        "exposure.shop.pricing_api",
        "exposure.shop.exec_dashboard",
    ]


def test_exposures_downstream_order_is_total_on_criticality_name_ties():
    # Two exposures with identical criticality AND identical name: the order must
    # not fall back to set/hash iteration. unique_id is the total tiebreaker, so the
    # result is stable regardless of PYTHONHASHSEED / insertion order.
    m = _manifest()
    del m["exposures"]["exposure.shop.pricing_api"]
    twin = {
        "name": "twin",
        "type": "dashboard",
        "maturity": "high",
        "owner": {"name": "sam"},
        "meta": {},
        "depends_on": {"nodes": ["model.shop.revenue_daily"]},
    }
    m["exposures"]["exposure.shop.twin_b"] = dict(twin)
    m["exposures"]["exposure.shop.twin_a"] = dict(twin)
    m["exposures"]["exposure.shop.exec_dashboard"]["name"] = "twin"
    g = load_dbt_manifest(m)
    ids = [e.unique_id for e in g.exposures_downstream_of({"model.shop.fact_orders"})]
    # All three are dashboard/HIGH named "twin"; unique_id breaks the tie ascending.
    assert ids == [
        "exposure.shop.exec_dashboard",
        "exposure.shop.twin_a",
        "exposure.shop.twin_b",
    ]


def test_data_downstream_of_excludes_exposures():
    g = load_dbt_manifest(_manifest())
    data = g.data_downstream_of({"model.shop.fact_orders"})
    assert data == {"model.shop.revenue_daily"}


def test_dangling_exposure_dependency_is_skipped():
    m = _manifest()
    m["exposures"]["exposure.shop.exec_dashboard"]["depends_on"]["nodes"].append("model.ghost")
    g = load_dbt_manifest(m)  # must not raise
    assert "model.ghost" not in g.nodes


def test_manifest_without_exposures_is_unchanged():
    m = _manifest()
    del m["exposures"]
    g = load_dbt_manifest(m)
    assert g.exposures_downstream_of({"model.shop.fact_orders"}) == []
    assert "exposure.shop.exec_dashboard" not in g.nodes
