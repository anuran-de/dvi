import json
from pathlib import Path

from scripts.export_fixtures import main


def test_exports_grounded_incident_fixtures(tmp_path: Path):
    written = main(tmp_path)
    assert written, "expected at least one incident fixture"

    index = json.loads((tmp_path / "index.json").read_text())
    assert isinstance(index, list) and len(index) == len(written)

    first = written[0]
    required = {
        "id", "asset", "severity", "title", "summary", "confidence",
        "evidence", "affectedAssets", "changeAt", "detectedAt",
        "rootCause", "businessImpact",
    }
    assert required <= set(first)
    assert first["severity"] in {"low", "medium", "high", "critical"}
    assert first["rootCause"].keys() >= {"label", "targets", "timestamp"}
    # Grounded, not hand-authored: evidence comes from the engine.
    assert isinstance(first["evidence"], list) and first["evidence"]

    # Every id has its own file matching the index entry.
    for entry in index:
        payload = json.loads((tmp_path / f"{entry['id']}.json").read_text())
        assert payload["id"] == entry["id"]


def test_export_is_deterministic(tmp_path: Path):
    a = main(tmp_path / "a")
    b = main(tmp_path / "b")
    assert a == b
