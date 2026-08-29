import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import duckdb
import polars as pl
import pytest

from dvi.cli.config import DviConfig, DviError
from dvi.cli.sources import incident_from_config


def _write_manifest(path: Path) -> None:
    manifest = {
        "nodes": {
            "model.shop.stg_orders": {
                "resource_type": "model",
                "depends_on": {"nodes": []},
            },
            "model.shop.fct_orders": {
                "resource_type": "model",
                "depends_on": {"nodes": ["model.shop.stg_orders"]},
            },
        },
        "exposures": {},
    }
    path.write_text(json.dumps(manifest), encoding="utf-8")


def _frames():
    # A clean value-substitution: the dominant 'UK' category is renamed to 'GB'.
    before = pl.DataFrame({"country": ["UK"] * 40 + ["US"] * 40 + ["DE"] * 20})
    after = pl.DataFrame({"country": ["GB"] * 40 + ["US"] * 40 + ["DE"] * 20})
    return before, after


def _config(tmp_path: Path, source: dict) -> DviConfig:
    return DviConfig.model_validate({
        "asset": "model.shop.fct_orders",
        "columns": ["country"],
        "source": source,
        "lineage": {"manifest": str(tmp_path / "manifest.json")},
        "changes": [{
            "id": "pr-1",
            "label": "rename country codes",
            "targets": ["model.shop.stg_orders"],
            "timestamp": datetime.now(UTC) - timedelta(hours=1),
        }],
    })


def test_file_source_produces_incident(tmp_path):
    _write_manifest(tmp_path / "manifest.json")
    before, after = _frames()
    before.write_csv(tmp_path / "before.csv")
    after.write_csv(tmp_path / "after.csv")
    cfg = _config(tmp_path, {
        "kind": "file",
        "before": str(tmp_path / "before.csv"),
        "after": str(tmp_path / "after.csv"),
    })

    inc = incident_from_config(cfg)

    assert inc is not None
    assert inc.severity == "high"
    assert inc.primary_cause.explained[0].symptom.signature == "value_substitution"


def test_warehouse_source_matches_file_decision(tmp_path):
    _write_manifest(tmp_path / "manifest.json")
    before, after = _frames()
    dbfile = tmp_path / "w.duckdb"
    con = duckdb.connect(str(dbfile))
    for name, df in [("before_orders", before), ("after_orders", after)]:
        con.execute(f"CREATE TABLE {name}(country VARCHAR)")
        con.executemany(f"INSERT INTO {name} VALUES (?)", list(df.iter_rows()))
    con.close()
    cfg = _config(tmp_path, {
        "kind": "warehouse",
        "database": str(dbfile),
        "before_table": "before_orders",
        "after_table": "after_orders",
    })

    inc = incident_from_config(cfg)

    assert inc is not None
    assert inc.severity == "high"
    assert inc.primary_cause.explained[0].symptom.signature == "value_substitution"


def test_clean_data_yields_no_incident(tmp_path):
    _write_manifest(tmp_path / "manifest.json")
    before, _ = _frames()
    before.write_csv(tmp_path / "same.csv")
    cfg = _config(tmp_path, {
        "kind": "file",
        "before": str(tmp_path / "same.csv"),
        "after": str(tmp_path / "same.csv"),
    })

    assert incident_from_config(cfg) is None


def test_unresolved_target_raises_dvi_error(tmp_path):
    _write_manifest(tmp_path / "manifest.json")
    before, after = _frames()
    before.write_csv(tmp_path / "before.csv")
    after.write_csv(tmp_path / "after.csv")
    cfg = _config(tmp_path, {
        "kind": "file",
        "before": str(tmp_path / "before.csv"),
        "after": str(tmp_path / "after.csv"),
    })
    cfg.changes[0].targets = ["model.shop.does_not_exist"]

    with pytest.raises(DviError):
        incident_from_config(cfg)


def test_missing_source_file_raises_dvi_error(tmp_path):
    _write_manifest(tmp_path / "manifest.json")
    cfg = _config(tmp_path, {
        "kind": "file",
        "before": str(tmp_path / "nope.csv"),
        "after": str(tmp_path / "nope.csv"),
    })

    with pytest.raises(DviError):
        incident_from_config(cfg)


def test_unsupported_file_extension_raises_dvi_error(tmp_path):
    _write_manifest(tmp_path / "manifest.json")
    unsupported = tmp_path / "before.txt"
    unsupported.write_text("country\nUK\n", encoding="utf-8")
    cfg = _config(tmp_path, {
        "kind": "file",
        "before": str(unsupported),
        "after": str(unsupported),
    })

    with pytest.raises(DviError):
        incident_from_config(cfg)


def test_missing_warehouse_database_raises_dvi_error(tmp_path):
    _write_manifest(tmp_path / "manifest.json")
    cfg = _config(tmp_path, {
        "kind": "warehouse",
        "database": str(tmp_path / "does_not_exist.duckdb"),
        "before_table": "before_orders",
        "after_table": "after_orders",
    })

    with pytest.raises(DviError):
        incident_from_config(cfg)


def test_warehouse_profiling_failure_raises_dvi_error(tmp_path):
    _write_manifest(tmp_path / "manifest.json")
    dbfile = tmp_path / "empty.duckdb"
    con = duckdb.connect(str(dbfile))
    con.close()
    cfg = _config(tmp_path, {
        "kind": "warehouse",
        "database": str(dbfile),
        "before_table": "before_orders",
        "after_table": "after_orders",
    })

    with pytest.raises(DviError):
        incident_from_config(cfg)
