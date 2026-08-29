# M5b — CLI + GitHub Action PR reports Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a `dvi` CLI that runs the finished detection pipeline over a before/after snapshot declared in one TOML config, renders a Markdown + JSON report, gates the exit code on severity, and a thin composite GitHub Action that posts the report as a sticky PR comment.

**Architecture:** New `src/dvi/cli/` package (a thin orchestration layer that adds no detection logic): `config.py` (pydantic + `tomllib`), `gate.py` (severity ladder + exit codes), `render.py` (pure Markdown/JSON), `sources.py` (file + warehouse adapters, both → `Incident | None`), `main.py` (argparse entrypoint). Plus a repo-root composite `action.yml` and an example workflow.

**Tech Stack:** Python 3.11, stdlib `argparse` + `tomllib`, pydantic v2, polars, duckdb (all already dependencies). No new runtime dependencies.

**Spec:** `docs/superpowers/specs/2026-08-30-m5b-cli-github-action-design.md`

## Global Constraints

- Python 3.11; runtime deps limited to what `pyproject.toml` already declares (polars, duckdb, networkx, pydantic). **No new runtime dependency** — use stdlib `argparse` and `tomllib`, not click/typer/pyyaml. numpy/pandas/pyarrow/sklearn are unavailable.
- All detection/attribution stays in `dvi.pipeline` / `dvi.detection` / `dvi.rca` / `dvi.incidents`; `cli/` only assembles inputs and formats outputs.
- Config is TOML parsed by `tomllib`, validated by pydantic v2. CLI is `argparse`.
- Exit codes: `0` = clean or below `fail_on`; `1` = incident at/above `fail_on`; `2` = usage/config/runtime error. Severity ladder: `low < medium < high < critical`.
- Single asset per run (v1). Change `timestamp` required. Calibration model default-on (`[gate] model = true`).
- Strict TDD (RED-GREEN-REFACTOR). ruff line-length 100, lint select E, F, I, UP, B.
- Commit as: `git -c user.name="Anuran De" -c user.email="121761842+anuran-de@users.noreply.github.com" commit -m "<msg>" --author="Anuran De <121761842+anuran-de@users.noreply.github.com>"`. **NO Co-Authored-By trailer, NO "Generated with" line.**
- venv: `source .venv/Scripts/activate` (Windows Git Bash). `pytest -q` may not print the trailing summary line in this shell; use `python -m pytest -o addopts="" ...` to force it, or read individual `-v` PASS lines.

---

### Task 1: Config models + loader

**Files:**
- Create: `src/dvi/cli/__init__.py`
- Create: `src/dvi/cli/config.py`
- Test: `tests/test_cli_config.py`

**Interfaces:**
- Consumes: nothing from the codebase (pydantic + stdlib only).
- Produces:
  - `class DviError(Exception)` — the CLI's clear-error type (raised for all expected config/runtime failures).
  - `class FileSource(BaseModel)`: `kind: Literal["file"]`, `before: str`, `after: str`.
  - `class WarehouseSource(BaseModel)`: `kind: Literal["warehouse"]`, `database: str`, `before_table: str`, `after_table: str`.
  - `class LineageConfig(BaseModel)`: `manifest: str`.
  - `class ChangeConfig(BaseModel)`: `id: str`, `label: str = ""`, `targets: list[str]`, `timestamp: datetime`.
  - `class GateConfig(BaseModel)`: `fail_on: Literal["low","medium","high","critical"] = "high"`, `model: bool = True`.
  - `class DviConfig(BaseModel)`: `asset: str`, `source: FileSource | WarehouseSource` (discriminated on `kind`), `lineage: LineageConfig`, `changes: list[ChangeConfig]` (min length 1), `gate: GateConfig` (default), `columns: list[str] | None = None`.
  - `def load_config(path: str | Path) -> DviConfig` — reads a TOML file, validates, and wraps any failure in `DviError`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli_config.py
import pytest
from pydantic import ValidationError

from dvi.cli.config import DviConfig, DviError, load_config

_BASE = {
    "asset": "model.shop.fct_orders",
    "lineage": {"manifest": "target/manifest.json"},
    "changes": [
        {"id": "pr-1", "targets": ["model.shop.stg_orders"],
         "timestamp": "2026-08-30T12:00:00Z"}
    ],
}


def _with_source(source):
    return {**_BASE, "source": source}


def test_file_config_parses_with_defaults():
    cfg = DviConfig.model_validate(
        _with_source({"kind": "file", "before": "b.csv", "after": "a.csv"})
    )
    assert cfg.source.kind == "file"
    assert cfg.source.before == "b.csv"
    assert cfg.gate.fail_on == "high"   # default
    assert cfg.gate.model is True       # default
    assert cfg.columns is None


def test_warehouse_config_parses():
    cfg = DviConfig.model_validate(
        _with_source({"kind": "warehouse", "database": "w.duckdb",
                      "before_table": "prod.x", "after_table": "pr.x"})
    )
    assert cfg.source.kind == "warehouse"
    assert cfg.source.before_table == "prod.x"


def test_mixed_source_keys_rejected():
    # a file source carrying a warehouse-only key must fail (extra=forbid)
    with pytest.raises(ValidationError):
        DviConfig.model_validate(
            _with_source({"kind": "file", "before": "b", "after": "a",
                          "database": "w.duckdb"})
        )


def test_empty_changes_rejected():
    bad = {**_BASE, "changes": [],
           "source": {"kind": "file", "before": "b", "after": "a"}}
    with pytest.raises(ValidationError):
        DviConfig.model_validate(bad)


def test_bad_fail_on_rejected():
    with pytest.raises(ValidationError):
        DviConfig.model_validate({
            **_with_source({"kind": "file", "before": "b", "after": "a"}),
            "gate": {"fail_on": "severe"},
        })


def test_load_config_reads_toml_file(tmp_path):
    p = tmp_path / "dvi.toml"
    p.write_text(
        'asset = "model.shop.fct_orders"\n'
        "[source]\n"
        'kind = "file"\n'
        'before = "b.csv"\n'
        'after = "a.csv"\n'
        "[lineage]\n"
        'manifest = "target/manifest.json"\n'
        "[[changes]]\n"
        'id = "pr-1"\n'
        'targets = ["model.shop.stg_orders"]\n'
        "timestamp = 2026-08-30T12:00:00Z\n",
        encoding="utf-8",
    )
    cfg = load_config(p)
    assert cfg.asset == "model.shop.fct_orders"
    assert cfg.source.kind == "file"


def test_load_config_missing_file_raises_dvi_error():
    with pytest.raises(DviError):
        load_config("does-not-exist.toml")


def test_load_config_bad_toml_raises_dvi_error(tmp_path):
    p = tmp_path / "bad.toml"
    p.write_text("this = = broken", encoding="utf-8")
    with pytest.raises(DviError):
        load_config(p)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/Scripts/activate && python -m pytest tests/test_cli_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'dvi.cli'`.

- [ ] **Step 3: Write minimal implementation**

```python
# src/dvi/cli/__init__.py
"""DVI command-line surface: config-driven analysis + report rendering."""
```

```python
# src/dvi/cli/config.py
"""Declarative config for the DVI CLI: parse dvi.toml, validate with pydantic.

The config is the single source of truth for a run — what asset to analyze,
where its before/after data lives, the lineage manifest, the change list RCA
attributes to, and the gate. Every expected failure surfaces as a DviError so
the CLI can map it to exit code 2 instead of a raw traceback.
"""

from __future__ import annotations

import tomllib
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError


class DviError(Exception):
    """A clear, user-facing error (bad config, missing input, unresolved target)."""


class FileSource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["file"]
    before: str
    after: str


class WarehouseSource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["warehouse"]
    database: str
    before_table: str
    after_table: str


class LineageConfig(BaseModel):
    manifest: str


class ChangeConfig(BaseModel):
    id: str
    targets: list[str] = Field(min_length=1)
    timestamp: datetime
    label: str = ""


class GateConfig(BaseModel):
    fail_on: Literal["low", "medium", "high", "critical"] = "high"
    model: bool = True


class DviConfig(BaseModel):
    asset: str
    source: FileSource | WarehouseSource = Field(discriminator="kind")
    lineage: LineageConfig
    changes: list[ChangeConfig] = Field(min_length=1)
    gate: GateConfig = Field(default_factory=GateConfig)
    columns: list[str] | None = None


def load_config(path: str | Path) -> DviConfig:
    """Load and validate a dvi.toml, wrapping any failure in DviError."""
    p = Path(path)
    try:
        with p.open("rb") as f:
            raw = tomllib.load(f)
    except FileNotFoundError as e:
        raise DviError(f"config file not found: {p}") from e
    except tomllib.TOMLDecodeError as e:
        raise DviError(f"invalid TOML in {p}: {e}") from e
    try:
        return DviConfig.model_validate(raw)
    except ValidationError as e:
        raise DviError(f"invalid config {p}:\n{e}") from e
```

- [ ] **Step 4: Run test to verify it passes**

Run: `source .venv/Scripts/activate && python -m pytest tests/test_cli_config.py -v`
Expected: PASS (all 8).

- [ ] **Step 5: Lint + commit**

```bash
source .venv/Scripts/activate && ruff check src/dvi/cli/config.py tests/test_cli_config.py
git add src/dvi/cli/__init__.py src/dvi/cli/config.py tests/test_cli_config.py
git -c user.name="Anuran De" -c user.email="121761842+anuran-de@users.noreply.github.com" commit -m "feat(cli): dvi.toml config models + tomllib loader" --author="Anuran De <121761842+anuran-de@users.noreply.github.com>"
```

---

### Task 2: Severity gate + exit codes

**Files:**
- Create: `src/dvi/cli/gate.py`
- Test: `tests/test_cli_gate.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `SEVERITY_LEVELS: tuple[str, ...] = ("low", "medium", "high", "critical")`.
  - `def gate_failed(severity: str | None, fail_on: str) -> bool` — True when `severity` is at or above `fail_on`; False when `severity is None`.
  - `def exit_code(severity: str | None, fail_on: str) -> int` — `1` if `gate_failed`, else `0`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli_gate.py
import pytest

from dvi.cli.gate import SEVERITY_LEVELS, exit_code, gate_failed


@pytest.mark.parametrize(
    "severity,fail_on,expected",
    [
        ("high", "high", True),
        ("critical", "high", True),
        ("medium", "high", False),
        ("low", "low", True),
        ("medium", "low", True),
        (None, "low", False),
        (None, "high", False),
        ("low", "critical", False),
    ],
)
def test_gate_failed_matrix(severity, fail_on, expected):
    assert gate_failed(severity, fail_on) is expected


def test_exit_code_maps_gate():
    assert exit_code("high", "high") == 1
    assert exit_code("medium", "high") == 0
    assert exit_code(None, "high") == 0


def test_severity_levels_ordered():
    assert SEVERITY_LEVELS == ("low", "medium", "high", "critical")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/Scripts/activate && python -m pytest tests/test_cli_gate.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'dvi.cli.gate'`.

- [ ] **Step 3: Write minimal implementation**

```python
# src/dvi/cli/gate.py
"""The CI gate: does the incident's severity meet the fail threshold?

The severity ladder mirrors dvi.incidents.impact's ordering. Kept here as an
explicit public tuple so the CLI contract (exit codes) does not depend on a
private name in another package.
"""

from __future__ import annotations

SEVERITY_LEVELS: tuple[str, ...] = ("low", "medium", "high", "critical")


def gate_failed(severity: str | None, fail_on: str) -> bool:
    """True when a detected incident is severe enough to block the PR."""
    if severity is None:
        return False
    return SEVERITY_LEVELS.index(severity) >= SEVERITY_LEVELS.index(fail_on)


def exit_code(severity: str | None, fail_on: str) -> int:
    """1 when the gate trips, else 0. (Error exit 2 is handled by the CLI.)"""
    return 1 if gate_failed(severity, fail_on) else 0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `source .venv/Scripts/activate && python -m pytest tests/test_cli_gate.py -v`
Expected: PASS (all cases).

- [ ] **Step 5: Lint + commit**

```bash
source .venv/Scripts/activate && ruff check src/dvi/cli/gate.py tests/test_cli_gate.py
git add src/dvi/cli/gate.py tests/test_cli_gate.py
git -c user.name="Anuran De" -c user.email="121761842+anuran-de@users.noreply.github.com" commit -m "feat(cli): severity gate + exit-code mapping" --author="Anuran De <121761842+anuran-de@users.noreply.github.com>"
```

---

### Task 3: Report rendering (Markdown + JSON)

**Files:**
- Create: `src/dvi/cli/render.py`
- Test: `tests/test_cli_render.py`

**Interfaces:**
- Consumes: `dvi.incidents.Incident`, `dvi.incidents.render_business_impact`.
- Produces:
  - `def render_markdown(incident: Incident | None, *, asset: str, fail_on: str, gate_failed: bool) -> str` — the sticky PR comment; always ends with the literal marker `<!-- dvi-report -->`.
  - `def render_json(incident: Incident | None, *, asset: str, fail_on: str, gate_failed: bool, generated_at: datetime) -> dict` — the machine artifact.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli_render.py
from datetime import datetime, timezone

from dvi.cli.render import render_json, render_markdown
from dvi.incidents import Incident
from dvi.rca import ChangeEvent, RootCauseCandidate


def _incident():
    change = ChangeEvent(
        id="pr-1",
        timestamp=datetime(2026, 8, 30, tzinfo=timezone.utc),
        targets=["model.shop.stg_orders"],
        label="rename country codes",
    )
    return Incident(
        title="Semantic change in country - rename country codes",
        severity="high",
        summary="Suspected data incident from change 'rename country codes'.",
        primary_cause=RootCauseCandidate(change=change, score=1.0),
        affected_assets={"model.shop.fct_orders"},
        evidence=["country: UK -> GB (40 rows)"],
        confidence=0.87,
    )


def test_markdown_incident_has_verdict_and_marker():
    md = render_markdown(_incident(), asset="model.shop.fct_orders",
                         fail_on="high", gate_failed=True)
    assert "High-severity semantic change detected" in md
    assert "country: UK -> GB (40 rows)" in md
    assert "`model.shop.fct_orders`" in md
    assert "87%" in md               # confidence rendered
    assert "FAILED" in md            # gate line
    assert md.rstrip().endswith("<!-- dvi-report -->")


def test_markdown_no_incident_is_green_report():
    md = render_markdown(None, asset="model.shop.fct_orders",
                         fail_on="high", gate_failed=False)
    assert "No semantic change detected" in md
    assert "<!-- dvi-report -->" in md
    assert "FAILED" not in md


def test_json_incident_schema():
    js = render_json(_incident(), asset="model.shop.fct_orders",
                     fail_on="high", gate_failed=True,
                     generated_at=datetime(2026, 8, 30, tzinfo=timezone.utc))
    assert js["asset"] == "model.shop.fct_orders"
    assert js["severity"] == "high"
    assert js["gate"] == {"fail_on": "high", "failed": True}
    assert js["incident"]["title"].startswith("Semantic change in country")
    assert js["incident"]["affected_assets"] == ["model.shop.fct_orders"]
    assert js["incident"]["confidence"] == 0.87
    assert js["generated_at"] == "2026-08-30T00:00:00+00:00"


def test_json_no_incident_is_null():
    js = render_json(None, asset="a", fail_on="high", gate_failed=False,
                     generated_at=datetime(2026, 8, 30, tzinfo=timezone.utc))
    assert js["incident"] is None
    assert js["severity"] is None
    assert js["gate"]["failed"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/Scripts/activate && python -m pytest tests/test_cli_render.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'dvi.cli.render'`.

- [ ] **Step 3: Write minimal implementation**

```python
# src/dvi/cli/render.py
"""Render an Incident (or its absence) into a Markdown PR comment and JSON.

Both artifacts come from the same Incident, so the human and machine views can
never disagree. The Markdown always ends with an HTML marker so the GitHub
Action can find and update the same sticky comment on each run.
"""

from __future__ import annotations

from datetime import datetime

from dvi.incidents import Incident, render_business_impact

MARKER = "<!-- dvi-report -->"
_EMOJI = {"low": "🟢", "medium": "🟡", "high": "🔴", "critical": "🔴"}


def render_markdown(
    incident: Incident | None,
    *,
    asset: str,
    fail_on: str,
    gate_failed: bool,
) -> str:
    lines: list[str] = []
    if incident is None:
        lines.append("✅ **No semantic change detected**")
        lines.append("")
        lines.append(f"Asset: `{asset}`")
    else:
        emoji = _EMOJI.get(incident.severity, "🔴")
        lines.append(
            f"{emoji} **{incident.severity.capitalize()}-severity "
            f"semantic change detected**"
        )
        lines.append("")
        lines.append(f"### {incident.title}")
        lines.append("")
        lines.append(incident.summary)
        if incident.confidence is not None:
            lines.append("")
            lines.append(f"**Confidence:** {incident.confidence:.0%}")
        if incident.evidence:
            lines.append("")
            lines.append("**Evidence:**")
            lines.extend(f"- {e}" for e in incident.evidence)
        if incident.affected_assets:
            rendered = ", ".join(f"`{a}`" for a in sorted(incident.affected_assets))
            lines.append("")
            lines.append(f"**Affected downstream assets:** {rendered}")
        if incident.business_impact is not None:
            lines.append("")
            lines.extend(bl.strip() for bl in render_business_impact(incident.business_impact))
    lines.append("")
    lines.append(f"_Gate: fail_on=`{fail_on}` — {'FAILED' if gate_failed else 'passed'}_")
    lines.append("")
    lines.append(MARKER)
    return "\n".join(lines)


def render_json(
    incident: Incident | None,
    *,
    asset: str,
    fail_on: str,
    gate_failed: bool,
    generated_at: datetime,
) -> dict:
    inc: dict | None = None
    if incident is not None:
        business = None
        if incident.business_impact is not None:
            impact = incident.business_impact
            business = {
                "exposures": [
                    {
                        "name": e.name,
                        "type": e.type,
                        "criticality": e.criticality.name,
                        "owner": e.owner,
                    }
                    for e in impact.exposures
                ],
                "max_criticality": (
                    impact.max_criticality.name if impact.max_criticality else None
                ),
            }
        inc = {
            "title": incident.title,
            "severity": incident.severity,
            "summary": incident.summary,
            "confidence": incident.confidence,
            "affected_assets": sorted(incident.affected_assets),
            "evidence": list(incident.evidence),
            "business_impact": business,
        }
    return {
        "asset": asset,
        "severity": incident.severity if incident else None,
        "incident": inc,
        "gate": {"fail_on": fail_on, "failed": gate_failed},
        "generated_at": generated_at.isoformat(),
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `source .venv/Scripts/activate && python -m pytest tests/test_cli_render.py -v`
Expected: PASS (all 4).

- [ ] **Step 5: Lint + commit**

```bash
source .venv/Scripts/activate && ruff check src/dvi/cli/render.py tests/test_cli_render.py
git add src/dvi/cli/render.py tests/test_cli_render.py
git -c user.name="Anuran De" -c user.email="121761842+anuran-de@users.noreply.github.com" commit -m "feat(cli): Markdown + JSON incident report renderers" --author="Anuran De <121761842+anuran-de@users.noreply.github.com>"
```

---

### Task 4: Source adapters (file + warehouse → Incident)

**Files:**
- Create: `src/dvi/cli/sources.py`
- Test: `tests/test_cli_sources.py`

**Interfaces:**
- Consumes: `DviConfig`, `DviError` (Task 1); `dvi.lineage.load_dbt_manifest`; `dvi.rca.ChangeEvent`; `dvi.pipeline.analyze_change`, `dvi.pipeline.analyze_change_from_profiles`; `dvi.warehouse.DuckDBDialect`, `dvi.warehouse.SqlProfileSource`; `dvi.calibration.loader.load_model` (imported function-locally to avoid any import-order cycle with the pipeline/calibration packages).
- Produces:
  - `def incident_from_config(config: DviConfig) -> Incident | None` — builds lineage + change list + optional model, dispatches on `config.source.kind`, returns the analyzed incident.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli_sources.py
import json
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
            "timestamp": "2026-01-01T00:00:00Z",
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/Scripts/activate && python -m pytest tests/test_cli_sources.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'dvi.cli.sources'`.

- [ ] **Step 3: Write minimal implementation**

```python
# src/dvi/cli/sources.py
"""Turn a validated DviConfig into an Incident (or None).

Two adapters converge on the same pipeline call:
- file:      polars reads the two columnar files -> analyze_change (frames)
- warehouse: DuckDB drives the M5a pushdown path -> analyze_change_from_profiles

Everything except *how profiles are produced* (lineage, change list, model) is
shared, so the two producers cannot decide differently — the M5a seam.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import polars as pl

from dvi.incidents import Incident
from dvi.lineage import LineageGraph, load_dbt_manifest
from dvi.pipeline import analyze_change, analyze_change_from_profiles
from dvi.rca import ChangeEvent
from dvi.warehouse import DuckDBDialect, SqlProfileSource

from .config import DviConfig, DviError

_READERS = {
    ".parquet": pl.read_parquet,
    ".csv": pl.read_csv,
    ".ndjson": pl.read_ndjson,
}


def _read_frame(path: str) -> pl.DataFrame:
    p = Path(path)
    if not p.exists():
        raise DviError(f"source file not found: {p}")
    reader = _READERS.get(p.suffix.lower())
    if reader is None:
        raise DviError(
            f"unsupported source file extension {p.suffix!r} for {p} "
            f"(use one of {', '.join(sorted(_READERS))})"
        )
    try:
        return reader(p)
    except Exception as e:  # noqa: BLE001 - surface any read failure as a clear error
        raise DviError(f"could not read source file {p}: {e}") from e


def _lineage_and_changes(config: DviConfig) -> tuple[LineageGraph, list[ChangeEvent]]:
    manifest_path = Path(config.lineage.manifest)
    if not manifest_path.exists():
        raise DviError(f"lineage manifest not found: {manifest_path}")
    try:
        lineage = load_dbt_manifest(manifest_path)
    except Exception as e:  # noqa: BLE001
        raise DviError(f"could not read lineage manifest {manifest_path}: {e}") from e

    changes: list[ChangeEvent] = []
    for change in config.changes:
        for target in change.targets:
            if target not in lineage.nodes:
                raise DviError(
                    f"change {change.id!r} target {target!r} is not a node in "
                    f"lineage manifest {config.lineage.manifest!r}"
                )
        changes.append(
            ChangeEvent(
                id=change.id,
                timestamp=change.timestamp,
                targets=list(change.targets),
                label=change.label,
            )
        )
    return lineage, changes


def _load_model(config: DviConfig):
    if not config.gate.model:
        return None
    # Imported here (not at module top) to avoid any import-order cycle between
    # the pipeline and calibration packages when dvi.cli is first imported.
    from dvi.calibration.loader import load_model

    return load_model()


def incident_from_config(config: DviConfig) -> Incident | None:
    """Analyze the configured before/after snapshot and return an incident."""
    lineage, changes = _lineage_and_changes(config)
    model = _load_model(config)
    observed_at = datetime.now(timezone.utc)

    source = config.source
    if source.kind == "file":
        before = _read_frame(source.before)
        after = _read_frame(source.after)
        return analyze_change(
            asset=config.asset,
            before=before,
            after=after,
            observed_at=observed_at,
            lineage=lineage,
            changes=changes,
            columns=config.columns,
            model=model,
        )

    # warehouse
    import duckdb

    db = Path(source.database)
    if not db.exists():
        raise DviError(f"warehouse database not found: {db}")
    try:
        con = duckdb.connect(str(db), read_only=True)
    except Exception as e:  # noqa: BLE001
        raise DviError(f"could not open warehouse database {db}: {e}") from e
    try:
        def execute(sql: str):
            return con.execute(sql).fetchall()

        dialect = DuckDBDialect()
        try:
            before = SqlProfileSource(
                execute, source.before_table, dialect=dialect
            ).profile(config.columns)
            after = SqlProfileSource(
                execute, source.after_table, dialect=dialect
            ).profile(config.columns)
        except Exception as e:  # noqa: BLE001 - clear error, not a raw DB traceback
            raise DviError(f"warehouse profiling failed: {e}") from e
    finally:
        con.close()

    return analyze_change_from_profiles(
        asset=config.asset,
        before=before,
        after=after,
        observed_at=observed_at,
        lineage=lineage,
        changes=changes,
        columns=config.columns,
        model=model,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `source .venv/Scripts/activate && python -m pytest tests/test_cli_sources.py -v`
Expected: PASS (all 5). If an import-order cycle surfaces (it should not, given the function-local `load_model` import), the failure will be at collection — resolve by keeping calibration imports function-local.

- [ ] **Step 5: Lint + commit**

```bash
source .venv/Scripts/activate && ruff check src/dvi/cli/sources.py tests/test_cli_sources.py
git add src/dvi/cli/sources.py tests/test_cli_sources.py
git -c user.name="Anuran De" -c user.email="121761842+anuran-de@users.noreply.github.com" commit -m "feat(cli): file + warehouse source adapters to Incident" --author="Anuran De <121761842+anuran-de@users.noreply.github.com>"
```

---

### Task 5: CLI entrypoint + console script

**Files:**
- Create: `src/dvi/cli/main.py`
- Modify: `pyproject.toml` (add `[project.scripts]`)
- Modify: `src/dvi/cli/__init__.py` (export `main`)
- Test: `tests/test_cli_main.py`

**Interfaces:**
- Consumes: `load_config`, `DviError` (Task 1); `gate_failed` (Task 2); `render_markdown`, `render_json` (Task 3); `incident_from_config` (Task 4).
- Produces:
  - `def main(argv: list[str] | None = None) -> int` — parse args, run, write `dvi-report.md` + `dvi-report.json` to `--output-dir`, echo Markdown to stdout, return exit code (0/1/2). Wired as console script `dvi = "dvi.cli.main:main"`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli_main.py
import json
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
        "timestamp = 2026-01-01T00:00:00Z\n"
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/Scripts/activate && python -m pytest tests/test_cli_main.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'dvi.cli.main'`.

- [ ] **Step 3: Write minimal implementation**

```python
# src/dvi/cli/main.py
"""The `dvi` command-line entrypoint.

`dvi analyze --config dvi.toml --output-dir <dir>`:
load + validate config, analyze the before/after snapshot, render the Markdown
and JSON reports, and return an exit code the CI gate reads (0 clean/below
threshold, 1 gate tripped, 2 could-not-run).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from .config import DviConfig, DviError, load_config
from .gate import gate_failed
from .render import render_json, render_markdown
from .sources import incident_from_config


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dvi", description="Data Versioning Intelligence")
    sub = parser.add_subparsers(dest="command", required=True)
    analyze = sub.add_parser("analyze", help="Analyze a before/after snapshot and report.")
    analyze.add_argument("--config", default="dvi.toml", help="Path to the dvi.toml config.")
    analyze.add_argument("--output-dir", default=".", help="Directory for report artifacts.")
    analyze.add_argument("--source-before", help="Override the file source 'before' path.")
    analyze.add_argument("--source-after", help="Override the file source 'after' path.")
    return parser


def _apply_overrides(config: DviConfig, args: argparse.Namespace) -> DviConfig:
    if args.source_before is None and args.source_after is None:
        return config
    if config.source.kind != "file":
        raise DviError("--source-before/--source-after apply only to a file source")
    if args.source_before is not None:
        config.source.before = args.source_before
    if args.source_after is not None:
        config.source.after = args.source_after
    return config


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        config = load_config(args.config)
        config = _apply_overrides(config, args)
        incident = incident_from_config(config)
    except DviError as e:
        print(f"dvi: error: {e}", file=sys.stderr)
        return 2

    failed = gate_failed(incident.severity if incident else None, config.gate.fail_on)
    markdown = render_markdown(
        incident, asset=config.asset, fail_on=config.gate.fail_on, gate_failed=failed
    )
    payload = render_json(
        incident,
        asset=config.asset,
        fail_on=config.gate.fail_on,
        gate_failed=failed,
        generated_at=datetime.now(timezone.utc),
    )

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "dvi-report.md").write_text(markdown, encoding="utf-8")
    (out_dir / "dvi-report.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(markdown)

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
```

Then add to `src/dvi/cli/__init__.py`:

```python
"""DVI command-line surface: config-driven analysis + report rendering."""

from .main import main

__all__ = ["main"]
```

Then add to `pyproject.toml` after the `[project.urls]` block:

```toml
[project.scripts]
dvi = "dvi.cli.main:main"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `source .venv/Scripts/activate && python -m pytest tests/test_cli_main.py -v`
Expected: PASS (all 5).

- [ ] **Step 5: Lint + commit**

```bash
source .venv/Scripts/activate && ruff check src/dvi/cli/main.py src/dvi/cli/__init__.py tests/test_cli_main.py
source .venv/Scripts/activate && python -m pytest -o addopts="" tests/ | tail -3
git add src/dvi/cli/main.py src/dvi/cli/__init__.py pyproject.toml tests/test_cli_main.py
git -c user.name="Anuran De" -c user.email="121761842+anuran-de@users.noreply.github.com" commit -m "feat(cli): dvi analyze entrypoint + console script" --author="Anuran De <121761842+anuran-de@users.noreply.github.com>"
```

---

### Task 6: GitHub Action + example workflow + lint

**Files:**
- Create: `action.yml` (repo root)
- Create: `.github/workflows/dvi-example.yml`
- Test: `tests/test_action_yml.py`

**Interfaces:**
- Consumes: the `dvi analyze` CLI (Task 5) and its `dvi-report.md` artifact.
- Produces: a composite action that installs DVI, runs `dvi analyze`, posts a sticky PR comment via `gh`, and re-raises the CLI exit code.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_action_yml.py
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_ACTION = _ROOT / "action.yml"
_WORKFLOW = _ROOT / ".github" / "workflows" / "dvi-example.yml"


def test_action_yml_exists_and_is_composite():
    text = _ACTION.read_text(encoding="utf-8")
    assert "name:" in text
    assert "description:" in text
    assert "runs:" in text
    assert "composite" in text


def test_action_declares_and_references_inputs():
    text = _ACTION.read_text(encoding="utf-8")
    for name in ("config", "output-dir"):
        assert f"{name}:" in text            # declared under inputs:
        assert f"inputs.{name}" in text      # referenced in a step


def test_action_runs_cli_and_posts_sticky_comment():
    text = _ACTION.read_text(encoding="utf-8")
    assert "dvi analyze" in text
    assert "<!-- dvi-report -->" in text     # sticky-comment marker
    assert "gh " in text                     # posts via the gh CLI


def test_example_workflow_wires_pull_request():
    text = _WORKFLOW.read_text(encoding="utf-8")
    assert "pull_request" in text
    assert "pull-requests: write" in text
    assert "uses: ./" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/Scripts/activate && python -m pytest tests/test_action_yml.py -v`
Expected: FAIL — `FileNotFoundError` on `action.yml`.

- [ ] **Step 3: Write minimal implementation**

```yaml
# action.yml
name: "DVI semantic data-change report"
description: "Run DVI on a pull request and post a semantic-data-change report."
inputs:
  config:
    description: "Path to the dvi.toml config file."
    required: false
    default: "dvi.toml"
  output-dir:
    description: "Directory for the rendered report artifacts."
    required: false
    default: ".dvi"
runs:
  using: "composite"
  steps:
    - name: Set up Python
      uses: actions/setup-python@v5
      with:
        python-version: "3.11"
    - name: Install DVI
      shell: bash
      run: pip install "${{ github.action_path }}"
    - name: Run DVI analyze
      id: dvi
      shell: bash
      run: |
        set +e
        dvi analyze --config "${{ inputs.config }}" --output-dir "${{ inputs.output-dir }}"
        echo "exit_code=$?" >> "$GITHUB_OUTPUT"
    - name: Post sticky PR comment
      if: ${{ github.event.pull_request.number != '' }}
      shell: bash
      env:
        GITHUB_TOKEN: ${{ github.token }}
      run: |
        marker="<!-- dvi-report -->"
        body_file="${{ inputs.output-dir }}/dvi-report.md"
        repo="${{ github.repository }}"
        pr="${{ github.event.pull_request.number }}"
        existing=$(gh api "repos/$repo/issues/$pr/comments" \
          --jq ".[] | select(.body | contains(\"$marker\")) | .id" | head -n1)
        if [ -n "$existing" ]; then
          gh api -X PATCH "repos/$repo/issues/comments/$existing" -F body=@"$body_file"
        else
          gh api -X POST "repos/$repo/issues/$pr/comments" -F body=@"$body_file"
        fi
    - name: Enforce gate
      shell: bash
      run: exit ${{ steps.dvi.outputs.exit_code }}
```

```yaml
# .github/workflows/dvi-example.yml
name: DVI
on:
  pull_request:
permissions:
  contents: read
  pull-requests: write
jobs:
  dvi:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: ./
        with:
          config: dvi.toml
```

- [ ] **Step 4: Run test to verify it passes**

Run: `source .venv/Scripts/activate && python -m pytest tests/test_action_yml.py -v`
Expected: PASS (all 4).

- [ ] **Step 5: Commit**

```bash
git add action.yml .github/workflows/dvi-example.yml tests/test_action_yml.py
git -c user.name="Anuran De" -c user.email="121761842+anuran-de@users.noreply.github.com" commit -m "feat(action): composite GitHub Action + example workflow" --author="Anuran De <121761842+anuran-de@users.noreply.github.com>"
```

---

### Task 7: Documentation + roadmap

**Files:**
- Create: `docs/cli.md`
- Modify: `README.md`
- Modify: `CHANGELOG.md`
- Modify: `docs/architecture.md`

**Interfaces:**
- Consumes: the delivered CLI + Action (Tasks 1-6).
- Produces: user-facing docs; no code.

- [ ] **Step 1: Create `docs/cli.md`**

Write the following content:

````markdown
# DVI CLI + GitHub Action

DVI runs its semantic-change detectors over a before/after snapshot of one
asset, declared in a single `dvi.toml`, and reports an incident (or a clean
bill of health) as Markdown + JSON. A thin GitHub Action posts that report as a
sticky pull-request comment and fails the check when the incident is severe
enough.

## Install

```bash
pip install dvi          # provides the `dvi` command
```

## Configure — `dvi.toml`

```toml
asset = "model.shop.fct_orders"           # the asset being analyzed
columns = ["revenue", "country"]          # optional; omit = all shared columns

[source]                                  # exactly one shape, keyed by `kind`
kind = "file"                             # "file" | "warehouse"
before = "artifacts/fct_orders.main.parquet"
after  = "artifacts/fct_orders.pr.parquet"
# --- OR ---
# kind = "warehouse"
# database = "warehouse.duckdb"
# before_table = "prod.fct_orders"
# after_table  = "pr.fct_orders"

[lineage]
manifest = "target/manifest.json"         # dbt manifest → models + exposures

[[changes]]                               # one or more; RCA attributes to these
id = "pr-1234"
label = "Refactor revenue rollup"
targets = ["model.shop.stg_orders"]       # must be nodes in the manifest
timestamp = 2026-08-30T12:00:00Z          # required, ISO-8601

[gate]
fail_on = "high"                          # low | medium | high | critical
model = true                              # attach calibrated confidence
```

- **File source:** `.parquet`, `.csv`, `.ndjson`, read natively by polars.
- **Warehouse source:** a DuckDB database file DVI opens read-only; profiling is
  pushed into SQL (the M5a path). See *Snowflake* below.

## Run

```bash
dvi analyze --config dvi.toml --output-dir .dvi
```

Writes `.dvi/dvi-report.md` and `.dvi/dvi-report.json`, echoes the Markdown, and
exits:

| Exit | Meaning |
|------|---------|
| `0`  | No incident, or an incident below `fail_on`. |
| `1`  | Incident at/above `fail_on` — the gate tripped. |
| `2`  | Could not run (bad config, missing input, unresolved target). |

CI can inject PR-specific paths without rewriting the config:

```bash
dvi analyze --config dvi.toml --source-before prod.parquet --source-after pr.parquet
```

## GitHub Action

```yaml
name: DVI
on:
  pull_request:
permissions:
  contents: read
  pull-requests: write
jobs:
  dvi:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: anuran-de/dvi@main
        with:
          config: dvi.toml
```

The action installs DVI, runs `dvi analyze`, posts the report as a **sticky**
comment (updated in place on each run, keyed off a hidden `<!-- dvi-report -->`
marker) via the runner's `gh` CLI, and fails the check on the CLI's exit code.
No third-party action is required.

## Snowflake

The warehouse source runs against DuckDB out of the box. Snowflake uses the same
`SqlProfileSource` seam with `SnowflakeDialect`; its driver is not exercised in
CI (it pulls `pyarrow`, which DVI avoids), so wire it in your own environment by
constructing the profiles and calling `analyze_change_from_profiles` directly —
see `docs/warehouse-pushdown.md`.
````

- [ ] **Step 2: Update `README.md`**

- Change the M5b roadmap table row from `| **M5b** | ... |` to mark it delivered (`✅`) in the same style as the M5a row, e.g.:
  `| **M5b** ✅ | CLI (`dvi analyze`) + composite GitHub Action posting sticky PR reports, severity-gated | Real-user adoption path |`
- Update the **Status** block at the top to note M5b delivered (a short paragraph mirroring the existing M5a note: a `dvi` CLI + GitHub Action drive the pipeline on a PR from one `dvi.toml`, rendering a severity-gated Markdown/JSON report; link `docs/cli.md`).
- In the "Explicitly not built yet" list, update the CLI/Action bullet (currently "A CLI / GitHub Action surface for the pushdown path (M5b).") to reflect that it now exists, e.g. remove it or reword to the remaining gaps (auto-derived changes, multi-asset runs, forges beyond GitHub).
- If the README states a test count, update it to the actual current count from Step 4.

- [ ] **Step 3: Update `CHANGELOG.md`**

Add an M5b section in the same style as the existing entries (match heading level and bullet style). Cover: the `dvi analyze` CLI, `dvi.toml` config (file + warehouse sources), Markdown + JSON reports, the configurable severity gate + exit-code contract (0/1/2), and the composite GitHub Action with sticky PR comments. Use today's date, 2026-08-30. Do not invent a version tag beyond the existing scheme.

- [ ] **Step 4: Update `docs/architecture.md`**

Add a "CLI + GitHub Action" subsection (match existing section style) describing: the `dvi.cli` package as a thin orchestration layer over the pipeline (config → source adapter → render → exit code); that all detection stays in the pipeline; the two source adapters converging on `Incident | None`; and the composite action as a thin wrapper that posts a sticky comment and gates on exit code.

Then run the suite to get the real count for the README:

Run: `source .venv/Scripts/activate && python -m pytest -o addopts="" tests/ | tail -3`
Expected: all pass; note the total for the README test-count update.

- [ ] **Step 5: Commit**

```bash
git add docs/cli.md README.md CHANGELOG.md docs/architecture.md
git -c user.name="Anuran De" -c user.email="121761842+anuran-de@users.noreply.github.com" commit -m "docs(m5b): CLI + GitHub Action usage; mark M5b delivered" --author="Anuran De <121761842+anuran-de@users.noreply.github.com>"
```

---

## Self-Review

**1. Spec coverage:**
- §2.1 both file + warehouse sources → Task 4 (both adapters, both tested). ✅
- §2.2 changes explicit in config → Task 1 `ChangeConfig`, Task 4 `ChangeEvent` build. ✅
- §2.3 configurable severity gate → Task 2 `gate_failed`/`exit_code`, Task 5 wiring. ✅
- §2.4 TOML/`tomllib` + pydantic; argparse → Task 1, Task 5. ✅
- §2.5 warehouse = DuckDB, Snowflake documented → Task 4 DuckDB adapter, Task 7 docs. ✅
- §2.6 single asset per run → config models one asset; no multi-asset path. ✅
- §2.7 timestamp required → `ChangeConfig.timestamp: datetime` (no default). ✅
- §2.8 model default-on → `GateConfig.model = True`. ✅
- §3.1 config schema → Task 1. §3.2 sources → Task 4. §3.3 render → Task 3. §3.4 main + console script → Task 5. §3.5 action → Task 6. ✅
- §4 error handling (clear DviError, exit 2 paths) → Task 4 `DviError` raises, Task 5 catch. ✅
- §5 exit codes 0/1/2 → Task 2 + Task 5. ✅
- §6 all six test files → Tasks 1-6. ✅
- §7 files touched → all created/modified across tasks. ✅
- §8 YAGNI (no auto-derive, single asset, DuckDB+Snowflake, GitHub-only) → respected. ✅

**2. Placeholder scan:** No TBD/TODO; every code and test step has concrete content; docs task specifies exact `docs/cli.md` content and precise edit targets for README/CHANGELOG/architecture. ✅

**3. Type consistency:** `DviConfig`/`DviError` (Task 1) consumed unchanged in Tasks 4-5; `gate_failed(severity, fail_on)` signature identical in Task 2 def and Task 5 call; `render_markdown`/`render_json` keyword signatures identical in Task 3 def and Task 5 call; `incident_from_config(config)` identical in Task 4 def and Task 5 call; `SqlProfileSource(execute, table, *, dialect, top_k)` and `analyze_change*` calls match the real signatures read from source. `MARKER`/`<!-- dvi-report -->` string identical in render (Task 3) and action lint (Task 6). ✅

## Execution Handoff

(Handled by the controller — this plan is executed via subagent-driven-development.)
