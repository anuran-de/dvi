# Auto-derive Change Events Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Automatically derive candidate `ChangeEvent`s from git commit metadata (narrowed to modeled assets via dbt lineage) and union them with any explicit `[[changes]]`, so RCA works in CI without hand-declaring changes.

**Architecture:** A pure core (`derive_change_events`) turns already-collected commit records + a file→node resolver into `ChangeEvent`s. A thin git adapter (`collect_commits`) shells out to `git log` and is the only side-effecting piece. A range resolver picks the commit range from config/GitHub-env/default. `LineageGraph.nodes_for_file` maps changed files to lineage nodes. `sources.py` wires these together: union + dedup with explicit changes, then hard-error if the combined list is empty.

**Tech Stack:** Python 3.11+, `subprocess` (git), `pydantic` (config), `networkx` (lineage), `pytest`.

**Spec:** `docs/superpowers/specs/2026-09-04-auto-derive-change-events-design.md`

## Global Constraints

- Python **3.11+**. Use `datetime.fromisoformat` (parses offset-aware ISO-8601 on 3.11).
- **No new runtime dependency.** Only stdlib + existing deps (`polars`, `duckdb`, `networkx`, `pydantic`).
- **Deterministic / PYTHONHASHSEED-safe.** Every ordering is an explicit sort; never depend on set/dict iteration order. No wall clock in the decision path.
- **All timestamps normalized to naive-UTC** for cross-comparison (existing code uses naive datetimes, e.g. `src/dvi/benchmark/rca_cases.py`).
- Commits authored as: `git -c user.name="Anuran De" -c user.email="121761842+anuran-de@users.noreply.github.com" commit -m "<msg>" --author="Anuran De <121761842+anuran-de@users.noreply.github.com>"` — NO Co-Authored-By, NO "Generated with" line.
- Conventional Commit prefixes (`feat:`, `test:`, `docs:`).
- Run full suite with `pytest`; lint with `ruff check .`.

---

## File Structure

- Create `src/dvi/changes/__init__.py` — public API re-exports.
- Create `src/dvi/changes/records.py` — `CommitRecord` dataclass.
- Create `src/dvi/changes/derive.py` — `derive_change_events` (pure core).
- Create `src/dvi/changes/ranges.py` — `resolve_range`.
- Create `src/dvi/changes/gitlog.py` — `collect_commits` (git adapter) + parser.
- Modify `src/dvi/lineage/graph.py` — retain `original_file_path`; add `nodes_for_file`.
- Modify `src/dvi/cli/config.py` — `changes` optional; add `GitConfig`.
- Modify `src/dvi/cli/sources.py` — derive + union/dedup; empty→`DviError`.
- Tests: `tests/test_changes_derive.py`, `tests/test_changes_ranges.py`, `tests/test_changes_gitlog.py`, `tests/test_lineage_nodes_for_file.py`, `tests/test_cli_config.py` (additions), `tests/test_cli_sources.py` (additions).
- Docs: `README.md`, `docs/*.md`, `action.yml`, `CHANGELOG.md`.

---

### Task 1: Pure core — `CommitRecord` + `derive_change_events`

**Files:**
- Create: `src/dvi/changes/__init__.py`
- Create: `src/dvi/changes/records.py`
- Create: `src/dvi/changes/derive.py`
- Test: `tests/test_changes_derive.py`

**Interfaces:**
- Consumes: `dvi.rca.ChangeEvent` (`id: str`, `timestamp: datetime`, `targets: list[str]`, `label: str`).
- Produces:
  - `CommitRecord(sha: str, timestamp: datetime, subject: str, changed_files: tuple[str, ...])` — frozen dataclass.
  - `derive_change_events(commits: Iterable[CommitRecord], resolve_targets: Callable[[str], set[str]], *, sha_length: int = 7) -> list[ChangeEvent]`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_changes_derive.py
from datetime import datetime

from dvi.changes import CommitRecord, derive_change_events


def _resolver(mapping):
    return lambda path: set(mapping.get(path, set()))


def test_maps_changed_files_to_targets_one_event_per_commit():
    commits = [
        CommitRecord(
            sha="abcdef1234567890",
            timestamp=datetime(2026, 8, 25, 9, 50),
            subject="deploy stg_orders",
            changed_files=("models/stg_orders.sql",),
        ),
    ]
    resolve = _resolver({"models/stg_orders.sql": {"model.shop.stg_orders"}})

    events = derive_change_events(commits, resolve)

    assert len(events) == 1
    ev = events[0]
    assert ev.id == "abcdef1"                      # short sha, 7 chars
    assert ev.timestamp == datetime(2026, 8, 25, 9, 50)
    assert ev.targets == ["model.shop.stg_orders"]
    assert ev.label == "deploy stg_orders"


def test_drops_commits_with_no_mapped_targets():
    commits = [
        CommitRecord("a" * 40, datetime(2026, 8, 25, 9, 50), "touch readme",
                     ("README.md",)),
    ]
    events = derive_change_events(commits, _resolver({}))
    assert events == []


def test_unions_targets_across_changed_files_and_sorts_them():
    commits = [
        CommitRecord("beef" + "0" * 36, datetime(2026, 8, 25, 9, 50), "two models",
                     ("models/b.sql", "models/a.sql")),
    ]
    resolve = _resolver({
        "models/a.sql": {"model.shop.a"},
        "models/b.sql": {"model.shop.b"},
    })
    events = derive_change_events(commits, resolve)
    assert events[0].targets == ["model.shop.a", "model.shop.b"]  # sorted


def test_events_sorted_by_timestamp_then_id():
    commits = [
        CommitRecord("f" * 40, datetime(2026, 8, 25, 10, 0), "late", ("models/x.sql",)),
        CommitRecord("0" * 40, datetime(2026, 8, 25, 9, 0), "early", ("models/x.sql",)),
    ]
    resolve = _resolver({"models/x.sql": {"model.shop.x"}})
    events = derive_change_events(commits, resolve)
    assert [e.label for e in events] == ["early", "late"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_changes_derive.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'dvi.changes'`.

- [ ] **Step 3: Write minimal implementation**

```python
# src/dvi/changes/records.py
"""A commit as far as change-derivation cares: id, time, subject, files."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class CommitRecord:
    sha: str
    timestamp: datetime
    subject: str
    changed_files: tuple[str, ...]
```

```python
# src/dvi/changes/derive.py
"""Pure core: turn commit records into candidate ChangeEvents.

No git, no I/O. Given commits and a file->nodes resolver, emit one ChangeEvent
per commit that touches at least one modeled asset, dropping the rest.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable

from dvi.rca import ChangeEvent

from .records import CommitRecord


def derive_change_events(
    commits: Iterable[CommitRecord],
    resolve_targets: Callable[[str], set[str]],
    *,
    sha_length: int = 7,
) -> list[ChangeEvent]:
    events: list[ChangeEvent] = []
    for commit in commits:
        targets: set[str] = set()
        for path in commit.changed_files:
            targets |= resolve_targets(path)
        if not targets:
            continue  # commit touches nothing modeled -> not a candidate
        events.append(
            ChangeEvent(
                id=commit.sha[:sha_length],
                timestamp=commit.timestamp,
                targets=sorted(targets),
                label=commit.subject,
            )
        )
    # Explicit sort so ordering never depends on set/dict iteration.
    return sorted(events, key=lambda e: (e.timestamp, e.id))
```

```python
# src/dvi/changes/__init__.py
"""Derive candidate change events from git metadata."""

from .derive import derive_change_events
from .records import CommitRecord

__all__ = ["CommitRecord", "derive_change_events"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_changes_derive.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add src/dvi/changes/__init__.py src/dvi/changes/records.py src/dvi/changes/derive.py tests/test_changes_derive.py
git -c user.name="Anuran De" -c user.email="121761842+anuran-de@users.noreply.github.com" commit -m "feat(changes): derive change events from commit records" --author="Anuran De <121761842+anuran-de@users.noreply.github.com>"
```

---

### Task 2: `LineageGraph.nodes_for_file` + retain `original_file_path`

**Files:**
- Modify: `src/dvi/lineage/graph.py` (add `original_file_path` attr in `load_dbt_manifest`; add `nodes_for_file`)
- Test: `tests/test_lineage_nodes_for_file.py`

**Interfaces:**
- Produces: `LineageGraph.nodes_for_file(path: str) -> set[str]` — lineage node ids whose dbt source file matches `path` (exact or path-suffix match, separator-normalized).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_lineage_nodes_for_file.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_lineage_nodes_for_file.py -v`
Expected: FAIL — `AttributeError: 'LineageGraph' object has no attribute 'nodes_for_file'`.

- [ ] **Step 3: Write minimal implementation**

In `src/dvi/lineage/graph.py`, within `load_dbt_manifest`, add `original_file_path` when adding data nodes (the first `for` loop over `nodes`):

```python
    for unique_id, node in nodes.items():
        graph.add_node(
            unique_id,
            kind="data",
            resource_type=node.get("resource_type"),
            original_file_path=node.get("original_file_path"),
        )
```

Add the method to `LineageGraph` (near `node_kind`):

```python
    def nodes_for_file(self, path: str) -> set[str]:
        """Lineage nodes whose dbt source file is ``path``.

        Matches the manifest's ``original_file_path`` either exactly or as a
        trailing path segment, so a dbt project nested under a repo subdirectory
        still resolves. Separators are normalized to ``/``.
        """
        norm = path.replace("\\", "/").lstrip("./")
        out: set[str] = set()
        for node, attrs in self._g.nodes(data=True):
            fp = attrs.get("original_file_path")
            if not fp:
                continue
            fp = fp.replace("\\", "/")
            if norm == fp or norm.endswith("/" + fp):
                out.add(node)
        return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_lineage_nodes_for_file.py -v`
Expected: PASS (4 tests). Also run `pytest tests/test_lineage.py -v` — still green.

- [ ] **Step 5: Commit**

```bash
git add src/dvi/lineage/graph.py tests/test_lineage_nodes_for_file.py
git -c user.name="Anuran De" -c user.email="121761842+anuran-de@users.noreply.github.com" commit -m "feat(lineage): map a changed file to its lineage node(s)" --author="Anuran De <121761842+anuran-de@users.noreply.github.com>"
```

---

### Task 3: `resolve_range`

**Files:**
- Create: `src/dvi/changes/ranges.py`
- Modify: `src/dvi/changes/__init__.py` (export `resolve_range`)
- Test: `tests/test_changes_ranges.py`

**Interfaces:**
- Produces: `resolve_range(env: Mapping[str, str], base: str | None = None, head: str | None = None) -> tuple[str | None, str]` returning `(base, head)`. Precedence: explicit arg → GitHub env → default (`HEAD~1`, `HEAD`).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_changes_ranges.py
from dvi.changes import resolve_range


def test_default_range_when_nothing_provided():
    assert resolve_range({}) == ("HEAD~1", "HEAD")


def test_github_env_supplies_base_and_head():
    env = {"GITHUB_BASE_REF": "main", "GITHUB_SHA": "deadbeef"}
    assert resolve_range(env) == ("main", "deadbeef")


def test_explicit_args_win_over_env():
    env = {"GITHUB_BASE_REF": "main", "GITHUB_SHA": "deadbeef"}
    assert resolve_range(env, base="v1.0.0", head="v1.1.0") == ("v1.0.0", "v1.1.0")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_changes_ranges.py -v`
Expected: FAIL — `ImportError: cannot import name 'resolve_range'`.

- [ ] **Step 3: Write minimal implementation**

```python
# src/dvi/changes/ranges.py
"""Resolve the commit range to derive change events over.

Precedence: explicit config value -> GitHub Actions env -> a sane default.
Pure over an injected env mapping so it is testable without the real environment.
"""

from __future__ import annotations

from collections.abc import Mapping


def resolve_range(
    env: Mapping[str, str],
    base: str | None = None,
    head: str | None = None,
) -> tuple[str | None, str]:
    resolved_base = base or env.get("GITHUB_BASE_REF") or "HEAD~1"
    resolved_head = head or env.get("GITHUB_SHA") or "HEAD"
    return resolved_base, resolved_head
```

Add to `src/dvi/changes/__init__.py`:

```python
from .derive import derive_change_events
from .ranges import resolve_range
from .records import CommitRecord

__all__ = ["CommitRecord", "derive_change_events", "resolve_range"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_changes_ranges.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add src/dvi/changes/ranges.py src/dvi/changes/__init__.py tests/test_changes_ranges.py
git -c user.name="Anuran De" -c user.email="121761842+anuran-de@users.noreply.github.com" commit -m "feat(changes): resolve commit range from config/env/default" --author="Anuran De <121761842+anuran-de@users.noreply.github.com>"
```

---

### Task 4: `collect_commits` git adapter + naive-UTC normalization

**Files:**
- Create: `src/dvi/changes/gitlog.py`
- Modify: `src/dvi/changes/__init__.py` (export `collect_commits`)
- Test: `tests/test_changes_gitlog.py`

**Interfaces:**
- Consumes: `CommitRecord`.
- Produces: `collect_commits(base: str | None, head: str, cwd: Path) -> list[CommitRecord]`. Best-effort: returns `[]` on any git failure. Timestamps are naive UTC.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_changes_gitlog.py
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest

from dvi.changes import collect_commits


def _git(cwd: Path, *args: str, env=None) -> None:
    subprocess.run(["git", *args], cwd=str(cwd), check=True,
                   capture_output=True, text=True, env=env)


def _init_repo(cwd: Path) -> None:
    _git(cwd, "init", "-q")
    _git(cwd, "config", "user.email", "t@example.com")
    _git(cwd, "config", "user.name", "T")


def _commit(cwd: Path, filename: str, message: str, iso_date: str) -> None:
    (cwd / filename).write_text("x", encoding="utf-8")
    _git(cwd, "add", filename)
    import os
    env = {**os.environ, "GIT_AUTHOR_DATE": iso_date, "GIT_COMMITTER_DATE": iso_date}
    _git(cwd, "commit", "-q", "-m", message, env=env)


def test_collects_commit_metadata_and_changed_files(tmp_path):
    _init_repo(tmp_path)
    _commit(tmp_path, "a.sql", "first", "2026-08-25T09:50:00+00:00")
    _commit(tmp_path, "b.sql", "second", "2026-08-25T10:00:00+00:00")

    records = collect_commits(base=None, head="HEAD", cwd=tmp_path)

    assert [r.subject for r in records] == ["first", "second"] or \
           [r.subject for r in records] == ["second", "first"]
    by_subject = {r.subject: r for r in records}
    assert by_subject["second"].changed_files == ("b.sql",)
    # naive UTC
    ts = by_subject["first"].timestamp
    assert ts.tzinfo is None
    assert ts == datetime(2026, 8, 25, 9, 50, 0)


def test_range_excludes_the_base_commit(tmp_path):
    _init_repo(tmp_path)
    _commit(tmp_path, "a.sql", "first", "2026-08-25T09:50:00+00:00")
    _commit(tmp_path, "b.sql", "second", "2026-08-25T10:00:00+00:00")

    records = collect_commits(base="HEAD~1", head="HEAD", cwd=tmp_path)
    assert [r.subject for r in records] == ["second"]


def test_offset_timestamps_normalized_to_utc(tmp_path):
    _init_repo(tmp_path)
    _commit(tmp_path, "a.sql", "first", "2026-08-25T11:50:00+02:00")
    records = collect_commits(base=None, head="HEAD", cwd=tmp_path)
    assert records[0].timestamp == datetime(2026, 8, 25, 9, 50, 0)  # 11:50 +02:00 -> 09:50Z


def test_missing_repo_returns_empty_best_effort(tmp_path):
    # tmp_path is not a git repo -> git fails -> []
    assert collect_commits(base=None, head="HEAD", cwd=tmp_path) == []


def test_unknown_ref_returns_empty_best_effort(tmp_path):
    _init_repo(tmp_path)
    _commit(tmp_path, "a.sql", "first", "2026-08-25T09:50:00+00:00")
    assert collect_commits(base="does-not-exist", head="HEAD", cwd=tmp_path) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_changes_gitlog.py -v`
Expected: FAIL — `ImportError: cannot import name 'collect_commits'`.

- [ ] **Step 3: Write minimal implementation**

```python
# src/dvi/changes/gitlog.py
"""The only side-effecting piece: read commits from git via subprocess.

Best-effort by contract — any git problem (not a repo, unknown ref, git not on
PATH) yields an empty list so derivation simply contributes nothing rather than
failing the run. Commit timestamps are normalized to naive UTC to match the
rest of the codebase.
"""

from __future__ import annotations

import subprocess
from datetime import UTC, datetime
from pathlib import Path

from .records import CommitRecord

# Unit separators unlikely to appear in a commit subject.
_FIELD = "\x1f"
_RECORD = "\x1e"
_FORMAT = f"{_RECORD}%H{_FIELD}%cI{_FIELD}%s"


def _to_naive_utc(iso: str) -> datetime:
    ts = datetime.fromisoformat(iso)
    if ts.tzinfo is not None:
        ts = ts.astimezone(UTC).replace(tzinfo=None)
    return ts


def _parse(out: str) -> list[CommitRecord]:
    records: list[CommitRecord] = []
    for chunk in out.split(_RECORD):
        chunk = chunk.strip("\n")
        if not chunk:
            continue
        header, _, rest = chunk.partition("\n")
        sha, iso, subject = header.split(_FIELD, 2)
        files = tuple(line for line in rest.splitlines() if line.strip())
        records.append(
            CommitRecord(
                sha=sha,
                timestamp=_to_naive_utc(iso),
                subject=subject,
                changed_files=files,
            )
        )
    return records


def collect_commits(base: str | None, head: str, cwd: Path) -> list[CommitRecord]:
    rng = f"{base}..{head}" if base else head
    try:
        result = subprocess.run(
            ["git", "log", rng, f"--format={_FORMAT}", "--name-only"],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return []
    return _parse(result.stdout)
```

Add to `src/dvi/changes/__init__.py`:

```python
from .derive import derive_change_events
from .gitlog import collect_commits
from .ranges import resolve_range
from .records import CommitRecord

__all__ = ["CommitRecord", "collect_commits", "derive_change_events", "resolve_range"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_changes_gitlog.py -v`
Expected: PASS (5 tests). Note: `git log HEAD` returns commits newest-first; the first test tolerates either order, but `_parse` preserves git's output order — later tasks re-sort via `derive_change_events`.

- [ ] **Step 5: Commit**

```bash
git add src/dvi/changes/gitlog.py src/dvi/changes/__init__.py tests/test_changes_gitlog.py
git -c user.name="Anuran De" -c user.email="121761842+anuran-de@users.noreply.github.com" commit -m "feat(changes): collect commits from git (best-effort, naive UTC)" --author="Anuran De <121761842+anuran-de@users.noreply.github.com>"
```

---

### Task 5: Config — `changes` optional + `[git]` block

**Files:**
- Modify: `src/dvi/cli/config.py`
- Test: `tests/test_cli_config.py` (additions)

**Interfaces:**
- Produces: `DviConfig.changes` defaults to `[]` (no longer `min_length=1`); new `DviConfig.git: GitConfig` with optional `base: str | None`, `head: str | None`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli_config.py  (add these tests; keep existing imports)
from dvi.cli.config import DviConfig


def _base_config(**overrides):
    cfg = {
        "asset": "model.shop.fct_orders",
        "source": {"kind": "file", "before": "b.parquet", "after": "a.parquet"},
        "lineage": {"manifest": "manifest.json"},
    }
    cfg.update(overrides)
    return cfg


def test_changes_may_be_omitted():
    cfg = DviConfig.model_validate(_base_config())
    assert cfg.changes == []


def test_git_block_defaults_to_none_base_and_head():
    cfg = DviConfig.model_validate(_base_config())
    assert cfg.git.base is None
    assert cfg.git.head is None


def test_git_block_accepts_base_and_head():
    cfg = DviConfig.model_validate(_base_config(git={"base": "main", "head": "HEAD"}))
    assert cfg.git.base == "main"
    assert cfg.git.head == "HEAD"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli_config.py -k "changes_may_be_omitted or git_block" -v`
Expected: FAIL — `changes` validation error (min_length) / `git` attribute missing.

- [ ] **Step 3: Write minimal implementation**

In `src/dvi/cli/config.py`, add a `GitConfig` model (near `GateConfig`):

```python
class GitConfig(BaseModel):
    """Optional commit range for auto-deriving change events."""

    model_config = ConfigDict(extra="forbid")
    base: str | None = None
    head: str | None = None
```

Change the `DviConfig` fields:

```python
class DviConfig(BaseModel):
    asset: str
    source: FileSource | WarehouseSource = Field(discriminator="kind")
    lineage: LineageConfig
    changes: list[ChangeConfig] = Field(default_factory=list)
    git: GitConfig = Field(default_factory=GitConfig)
    gate: GateConfig = Field(default_factory=GateConfig)
    store: StoreConfig | None = None
    columns: list[str] | None = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cli_config.py -v`
Expected: PASS (new + existing). Existing tests that declared `[[changes]]` still validate.

- [ ] **Step 5: Commit**

```bash
git add src/dvi/cli/config.py tests/test_cli_config.py
git -c user.name="Anuran De" -c user.email="121761842+anuran-de@users.noreply.github.com" commit -m "feat(config): make [[changes]] optional and add [git] range block" --author="Anuran De <121761842+anuran-de@users.noreply.github.com>"
```

---

### Task 6: Wire derivation into `sources.py` (union + dedup + empty→error)

**Files:**
- Modify: `src/dvi/cli/sources.py`
- Test: `tests/test_cli_sources.py` (additions)

**Interfaces:**
- Consumes: `resolve_range`, `collect_commits`, `derive_change_events`, `LineageGraph.nodes_for_file`.
- Produces: `_lineage_and_changes(config) -> tuple[LineageGraph, list[ChangeEvent]]` now returns the **combined** (explicit + derived, de-duplicated) change list. `incident_from_config` raises `DviError` when that list is empty.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli_sources.py  (add; reuse existing _write_manifest/_frames/_config helpers)
from datetime import datetime

import dvi.cli.sources as sources_mod
from dvi.changes import CommitRecord


def _manifest_with_paths(path):
    import json
    manifest = {
        "nodes": {
            "model.shop.stg_orders": {
                "resource_type": "model",
                "depends_on": {"nodes": []},
                "original_file_path": "models/stg_orders.sql",
            },
            "model.shop.fct_orders": {
                "resource_type": "model",
                "depends_on": {"nodes": ["model.shop.stg_orders"]},
                "original_file_path": "models/fct_orders.sql",
            },
        },
        "exposures": {},
    }
    path.write_text(json.dumps(manifest), encoding="utf-8")


def test_derived_changes_are_unioned_with_none_declared(tmp_path, monkeypatch):
    _manifest_with_paths(tmp_path / "manifest.json")
    before = tmp_path / "b.parquet"
    after = tmp_path / "a.parquet"
    import polars as pl
    b, a = _frames()
    b.write_parquet(before)
    a.write_parquet(after)

    config = DviConfig.model_validate({
        "asset": "model.shop.fct_orders",
        "columns": ["country"],
        "source": {"kind": "file", "before": str(before), "after": str(after)},
        "lineage": {"manifest": str(tmp_path / "manifest.json")},
        # no [[changes]] declared
    })

    monkeypatch.setattr(sources_mod, "collect_commits", lambda *a, **k: [
        CommitRecord("abcdef1234", datetime(2026, 8, 25, 9, 50), "deploy stg",
                     ("models/stg_orders.sql",)),
    ])

    incident = sources_mod.incident_from_config(config)
    assert incident is not None  # derived change drove the analysis


def test_no_declared_and_no_derived_changes_is_an_error(tmp_path, monkeypatch):
    _manifest_with_paths(tmp_path / "manifest.json")
    before = tmp_path / "b.parquet"
    after = tmp_path / "a.parquet"
    b, a = _frames()
    b.write_parquet(before)
    a.write_parquet(after)

    config = DviConfig.model_validate({
        "asset": "model.shop.fct_orders",
        "columns": ["country"],
        "source": {"kind": "file", "before": str(before), "after": str(after)},
        "lineage": {"manifest": str(tmp_path / "manifest.json")},
    })
    monkeypatch.setattr(sources_mod, "collect_commits", lambda *a, **k: [])

    with pytest.raises(DviError, match="no change events"):
        sources_mod.incident_from_config(config)


def test_explicit_and_derived_duplicate_is_collapsed(tmp_path, monkeypatch):
    _manifest_with_paths(tmp_path / "manifest.json")
    before = tmp_path / "b.parquet"
    after = tmp_path / "a.parquet"
    b, a = _frames()
    b.write_parquet(before)
    a.write_parquet(after)

    config = DviConfig.model_validate({
        "asset": "model.shop.fct_orders",
        "columns": ["country"],
        "source": {"kind": "file", "before": str(before), "after": str(after)},
        "lineage": {"manifest": str(tmp_path / "manifest.json")},
        "changes": [{
            "id": "abcdef1",
            "targets": ["model.shop.stg_orders"],
            "timestamp": "2026-08-25T09:50:00",
        }],
    })
    # Derived event identical to the explicit one (same id/targets/timestamp).
    monkeypatch.setattr(sources_mod, "collect_commits", lambda *a, **k: [
        CommitRecord("abcdef1000", datetime(2026, 8, 25, 9, 50), "deploy stg",
                     ("models/stg_orders.sql",)),
    ])

    lineage, changes = sources_mod._lineage_and_changes(config)
    ids_targets = [(c.id, tuple(c.targets), c.timestamp) for c in changes]
    assert ids_targets.count(("abcdef1", ("model.shop.stg_orders",),
                              datetime(2026, 8, 25, 9, 50))) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli_sources.py -k "derived or no_declared or duplicate" -v`
Expected: FAIL — `collect_commits` not referenced in `sources_mod` (AttributeError on monkeypatch) / empty-changes not raising.

- [ ] **Step 3: Write minimal implementation**

In `src/dvi/cli/sources.py`, add imports at the top:

```python
import os

from dvi.changes import collect_commits, derive_change_events, resolve_range
```

Replace `_lineage_and_changes` so it unions derived events and de-duplicates:

```python
def _dedup_key(change: ChangeEvent) -> tuple[str, tuple[str, ...], datetime]:
    return (change.id, tuple(sorted(change.targets)), change.timestamp)


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

    base, head = resolve_range(os.environ, config.git.base, config.git.head)
    commits = collect_commits(base, head, cwd=Path.cwd())
    derived = derive_change_events(commits, lineage.nodes_for_file)

    combined: list[ChangeEvent] = []
    seen: set[tuple[str, tuple[str, ...], datetime]] = set()
    for change in [*changes, *derived]:
        key = _dedup_key(change)
        if key in seen:
            continue
        seen.add(key)
        combined.append(change)
    return lineage, combined
```

Add the required imports for `datetime`:

```python
from datetime import datetime
```

Update `incident_from_config` to use the combined list and hard-error when empty. Replace the current body around the `observed_at` line:

```python
def incident_from_config(config: DviConfig) -> Incident | None:
    """Analyze the configured before/after snapshot and return an incident."""
    lineage, changes = _lineage_and_changes(config)
    if not changes:
        raise DviError(
            "no change events: declare [[changes]] or run in a git repo whose "
            "commits touch a modeled asset"
        )
    model = _load_model(config)
    # Anchor the observation to the newest change (declared or derived), not the
    # wall clock, so re-runs are deterministic and the RCA lead window is stable.
    observed_at = max(c.timestamp for c in changes)
    ...
```

Leave the rest of `incident_from_config` unchanged, but ensure the two `analyze_change*` calls receive `changes=changes` (the combined list) — they already reference the local `changes`, which is now the combined list.

**Note for the implementer:** the current file computes `observed_at = max(c.timestamp for c in config.changes)` — change it to iterate the combined `changes` as shown, and delete the old line so `config.changes` is no longer read here.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cli_sources.py -v`
Expected: PASS (new + existing). Existing sources tests declare `[[changes]]`; derivation against the ambient repo won't match the `shop` manifest paths, so they are unaffected.

- [ ] **Step 5: Run the full suite + lint**

Run: `pytest -q && ruff check .`
Expected: all green. This includes the alternate-`PYTHONHASHSEED` determinism pass if configured.

- [ ] **Step 6: Commit**

```bash
git add src/dvi/cli/sources.py tests/test_cli_sources.py
git -c user.name="Anuran De" -c user.email="121761842+anuran-de@users.noreply.github.com" commit -m "feat(cli): auto-derive and union change events, error when none" --author="Anuran De <121761842+anuran-de@users.noreply.github.com>"
```

---

### Task 7: Action + docs + CHANGELOG

**Files:**
- Modify: `action.yml` (document `fetch-depth: 0` requirement; no input change needed — env flows automatically)
- Modify: `README.md` (Quick start / How it works: `[[changes]]` now optional in CI)
- Modify: `docs/` (the config reference doc — locate with grep below)
- Modify: `CHANGELOG.md` (`## [Unreleased]`)

- [ ] **Step 1: Locate the config-reference doc**

Run: `grep -rln "\[\[changes\]\]\|changes =" docs README.md`
Read each hit; pick the doc that documents `dvi.toml` fields.

- [ ] **Step 2: Update the Action usage docs**

In `action.yml`, extend the top-of-file `description` comment / README Action snippet to note the checkout requirement. The canonical caller snippet (in README/docs) must show:

```yaml
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0        # DVI derives change events from commit history
      - uses: anuran-de/dvi@v1
```

- [ ] **Step 3: Document the behavior in README + config reference**

Add prose: "In CI, DVI auto-derives candidate change events from the commits in the PR range and maps changed dbt model files to the assets they touch, so `[[changes]]` is optional. Declare `[[changes]]` to add events git can't see (e.g. an upstream vendor load); explicit and derived events are unioned. If neither a declared nor a derived change exists, the run errors (exit 2)." Document the optional `[git]` block:

```toml
[git]
base = "main"   # optional; defaults to $GITHUB_BASE_REF, else HEAD~1
head = "HEAD"   # optional; defaults to $GITHUB_SHA, else HEAD
```

- [ ] **Step 4: Update CHANGELOG**

Under `## [Unreleased]` in `CHANGELOG.md`, add:

```markdown
### Added
- Auto-derive candidate change events from git commit history in CI, mapping
  changed dbt model files to lineage nodes; `[[changes]]` is now optional and
  is unioned with derived events (#11). Requires `actions/checkout` with
  `fetch-depth: 0`. A run with no declared or derived change now errors.
```

- [ ] **Step 5: Verify docs build/links + full suite**

Run: `pytest -q && ruff check .`
Expected: green. Manually re-read the edited docs for accuracy.

- [ ] **Step 6: Commit**

```bash
git add action.yml README.md docs CHANGELOG.md
git -c user.name="Anuran De" -c user.email="121761842+anuran-de@users.noreply.github.com" commit -m "docs: auto-derived change events, [git] block, checkout depth" --author="Anuran De <121761842+anuran-de@users.noreply.github.com>"
```

---

## Final verification (before PR)

- [ ] `pytest -q` fully green (incl. determinism pass).
- [ ] `ruff check .` clean.
- [ ] `git log --oneline` shows the 7 focused commits authored as Anuran De.
- [ ] Open PR to `main` with `Closes #11`; do NOT self-merge (maintainer decides).

## Self-review notes (author)

- **Spec coverage:** git-core (T4) + GH-env range (T3) ✓; union + optional changes (T5, T6) ✓; per-commit, drop-unmapped (T1) ✓; file→node via lineage (T2) ✓; hard error on empty (T6) ✓; Action/docs/CHANGELOG (T7) ✓; synthetic-context tests (T1) + temp-repo integration (T4) ✓.
- **Type consistency:** `CommitRecord`, `derive_change_events`, `resolve_range`, `collect_commits`, `nodes_for_file`, `GitConfig` names/signatures match across tasks.
- **Timestamps:** all naive-UTC (T4 normalizes; explicit config timestamps in tests are naive) so `max(...)` and dedup never mix aware/naive.
