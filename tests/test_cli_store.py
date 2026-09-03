"""End-to-end: `dvi analyze` records incidents to the store when configured.

Recording is opt-in (a `[store]` section) and must never change exit codes or
break the stateless default. Re-running the same snapshot upserts onto one row.
"""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import polars as pl

from dvi.cli.main import main
from dvi.store import SqliteIncidentStore


def _write_manifest(path: Path) -> None:
    manifest = {
        "nodes": {
            "model.shop.stg_orders": {"resource_type": "model",
                                      "depends_on": {"nodes": []}},
            "model.shop.fct_orders": {"resource_type": "model",
                                      "depends_on": {"nodes": ["model.shop.stg_orders"]}},
        },
        "exposures": {},
    }
    path.write_text(json.dumps(manifest), encoding="utf-8")


def _setup(tmp_path, *, same=False, store_path=None):
    _write_manifest(tmp_path / "manifest.json")
    before = pl.DataFrame({"country": ["UK"] * 40 + ["US"] * 40 + ["DE"] * 20})
    after = before if same else pl.DataFrame(
        {"country": ["GB"] * 40 + ["US"] * 40 + ["DE"] * 20}
    )
    before.write_csv(tmp_path / "before.csv")
    after.write_csv(tmp_path / "after.csv")
    change_ts = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    text = (
        'asset = "model.shop.fct_orders"\n'
        'columns = ["country"]\n'
        "[source]\n"
        'kind = "file"\n'
        f'before = "{(tmp_path / "before.csv").as_posix()}"\n'
        f'after = "{(tmp_path / "after.csv").as_posix()}"\n'
        "[lineage]\n"
        f'manifest = "{(tmp_path / "manifest.json").as_posix()}"\n'
        "[[changes]]\n"
        'id = "pr-1"\n'
        'label = "rename country codes"\n'
        'targets = ["model.shop.stg_orders"]\n'
        f"timestamp = {change_ts}\n"
    )
    if store_path is not None:
        text += "[store]\n" f'path = "{Path(store_path).as_posix()}"\n'
    cfg = tmp_path / "dvi.toml"
    cfg.write_text(text, encoding="utf-8")
    return cfg


def test_analyze_records_incident_when_store_configured(tmp_path):
    db = tmp_path / "incidents.db"
    cfg = _setup(tmp_path, store_path=db)

    code = main(["analyze", "--config", str(cfg), "--output-dir", str(tmp_path / "out")])

    assert code == 1  # incident still trips the gate; recording doesn't change that
    store = SqliteIncidentStore(db)
    hist = store.history("model.shop.fct_orders")
    assert len(hist) == 1
    assert hist[0].change_id == "pr-1"
    assert hist[0].column == "country"
    assert hist[0].occurrences == 1


def test_rerun_upserts_onto_one_row(tmp_path):
    db = tmp_path / "incidents.db"
    cfg = _setup(tmp_path, store_path=db)
    out = str(tmp_path / "out")

    main(["analyze", "--config", str(cfg), "--output-dir", out])
    main(["analyze", "--config", str(cfg), "--output-dir", out])

    hist = SqliteIncidentStore(db).history("model.shop.fct_orders")
    assert len(hist) == 1
    assert hist[0].occurrences == 2


def test_clean_run_records_nothing(tmp_path):
    db = tmp_path / "incidents.db"
    cfg = _setup(tmp_path, same=True, store_path=db)

    code = main(["analyze", "--config", str(cfg), "--output-dir", str(tmp_path / "out")])

    assert code == 0
    assert SqliteIncidentStore(db).history("model.shop.fct_orders") == []


def test_no_store_section_writes_no_db(tmp_path):
    cfg = _setup(tmp_path)  # no store configured

    main(["analyze", "--config", str(cfg), "--output-dir", str(tmp_path / "out")])

    assert not (tmp_path / "incidents.db").exists()
