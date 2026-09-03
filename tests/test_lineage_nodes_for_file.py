from dvi.lineage import load_dbt_manifest

MANIFEST = {
    "nodes": {
        "model.shop.stg_orders": {
            "resource_type": "model",
            "depends_on": {"nodes": []},
            "original_file_path": "models/staging/stg_orders.sql",
        },
        "model.shop.fct_orders": {
            "resource_type": "model",
            "depends_on": {"nodes": ["model.shop.stg_orders"]},
            "original_file_path": "models/marts/fct_orders.sql",
        },
    },
    "exposures": {},
}


def test_exact_path_maps_to_its_node():
    g = load_dbt_manifest(MANIFEST)
    assert g.nodes_for_file("models/staging/stg_orders.sql") == {"model.shop.stg_orders"}


def test_nested_repo_subdir_matches_by_suffix():
    g = load_dbt_manifest(MANIFEST)
    # dbt project lives under warehouse/ in the repo; git reports the repo path.
    assert g.nodes_for_file("warehouse/models/marts/fct_orders.sql") == {
        "model.shop.fct_orders"
    }


def test_backslash_paths_are_normalized():
    g = load_dbt_manifest(MANIFEST)
    assert g.nodes_for_file("models\\staging\\stg_orders.sql") == {"model.shop.stg_orders"}


def test_unknown_or_unmapped_file_returns_empty():
    g = load_dbt_manifest(MANIFEST)
    assert g.nodes_for_file("README.md") == set()
