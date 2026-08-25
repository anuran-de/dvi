from dvi.lineage import LineageGraph, load_dbt_manifest

MANIFEST = {
    "nodes": {
        "model.shop.orders_raw": {"resource_type": "model", "depends_on": {"nodes": []}},
        "model.shop.orders_clean": {
            "resource_type": "model",
            "depends_on": {"nodes": ["model.shop.orders_raw"]},
        },
        "model.shop.fact_orders": {
            "resource_type": "model",
            "depends_on": {"nodes": ["model.shop.orders_clean"]},
        },
        "model.shop.revenue_daily": {
            "resource_type": "model",
            "depends_on": {"nodes": ["model.shop.fact_orders"]},
        },
        "model.shop.customer_metrics": {
            "resource_type": "model",
            "depends_on": {"nodes": ["model.shop.fact_orders"]},
        },
    }
}


def test_loads_manifest_into_lineage_graph():
    graph = load_dbt_manifest(MANIFEST)
    assert isinstance(graph, LineageGraph)
    assert "model.shop.fact_orders" in graph.nodes


def test_downstream_is_transitive():
    graph = load_dbt_manifest(MANIFEST)
    assert graph.downstream("model.shop.fact_orders") == {
        "model.shop.revenue_daily",
        "model.shop.customer_metrics",
    }


def test_upstream_is_transitive():
    graph = load_dbt_manifest(MANIFEST)
    assert graph.upstream("model.shop.revenue_daily") == {
        "model.shop.fact_orders",
        "model.shop.orders_clean",
        "model.shop.orders_raw",
    }


def test_direct_downstream_excludes_indirect():
    graph = load_dbt_manifest(MANIFEST)
    assert graph.downstream("model.shop.orders_raw", transitive=False) == {
        "model.shop.orders_clean"
    }


def test_reachable_marks_downstream_as_affected():
    graph = load_dbt_manifest(MANIFEST)
    assert graph.is_downstream_of(
        "model.shop.revenue_daily", "model.shop.orders_raw"
    )
    assert not graph.is_downstream_of(
        "model.shop.orders_raw", "model.shop.revenue_daily"
    )
