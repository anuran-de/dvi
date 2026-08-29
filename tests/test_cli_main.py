import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import polars as pl

from dvi.cli.main import main


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


def _config_text(tmp_path: Path, before: str, after: str, target: str) -> str:
    change_ts = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    return (
        'asset = "model.shop.fct_orders"\n'
        'columns = ["country"]\n'
        "[source]\n"
        'kind = "file"\n'
        f'before = "{before}"\n'
        f'after = "{after}"\n'
        "[lineage]\n"
        f'manifest = "{(tmp_path / "manifest.json").as_posix()}"\n'
        "[[changes]]\n"
        'id = "pr-1"\n'
        'label = "rename country codes"\n'
        f'targets = ["{target}"]\n'
        f"timestamp = {change_ts}\n"
    )


def _setup(tmp_path, *, same=False, target="model.shop.stg_orders"):
    _write_manifest(tmp_path / "manifest.json")
    before = pl.DataFrame({"country": ["UK"] * 40 + ["US"] * 40 + ["DE"] * 20})
    after = before if same else pl.DataFrame(
        {"country": ["GB"] * 40 + ["US"] * 40 + ["DE"] * 20}
    )
    before.write_csv(tmp_path / "before.csv")
    after.write_csv(tmp_path / "after.csv")
    cfg = tmp_path / "dvi.toml"
    cfg.write_text(
        _config_text(tmp_path, (tmp_path / "before.csv").as_posix(),
                     (tmp_path / "after.csv").as_posix(), target),
        encoding="utf-8",
    )
    return cfg


def test_main_incident_fails_gate(tmp_path, capsys):
    cfg = _setup(tmp_path)
    out = tmp_path / "out"

    code = main(["analyze", "--config", str(cfg), "--output-dir", str(out)])

    assert code == 1
    assert (out / "dvi-report.md").exists()
    data = json.loads((out / "dvi-report.json").read_text(encoding="utf-8"))
    assert data["incident"] is not None
    assert data["gate"]["failed"] is True
    assert "semantic change detected" in capsys.readouterr().out


def test_main_clean_run_passes(tmp_path):
    cfg = _setup(tmp_path, same=True)
    out = tmp_path / "out"

    code = main(["analyze", "--config", str(cfg), "--output-dir", str(out)])

    assert code == 0
    data = json.loads((out / "dvi-report.json").read_text(encoding="utf-8"))
    assert data["incident"] is None


def test_main_config_error_returns_2(tmp_path, capsys):
    cfg = _setup(tmp_path, target="model.shop.does_not_exist")
    out = tmp_path / "out"

    code = main(["analyze", "--config", str(cfg), "--output-dir", str(out)])

    assert code == 2
    assert "error" in capsys.readouterr().err.lower()


def test_main_missing_config_returns_2(tmp_path):
    code = main(["analyze", "--config", str(tmp_path / "nope.toml"),
                 "--output-dir", str(tmp_path / "out")])
    assert code == 2


def test_main_source_override(tmp_path):
    # Config points at a non-existent 'after'; override supplies the real one.
    cfg = _setup(tmp_path)
    # Rewrite config's after path to a bogus file, then override on the CLI.
    bogus = tmp_path / "bogus.csv"
    text = (tmp_path / "dvi.toml").read_text(encoding="utf-8").replace(
        (tmp_path / "after.csv").as_posix(), bogus.as_posix()
    )
    (tmp_path / "dvi.toml").write_text(text, encoding="utf-8")
    out = tmp_path / "out"

    code = main([
        "analyze", "--config", str(cfg), "--output-dir", str(out),
        "--source-after", (tmp_path / "after.csv").as_posix(),
    ])

    assert code == 1  # override restored the real 'after' → incident fires
