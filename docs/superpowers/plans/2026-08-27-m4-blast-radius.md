# M4 — Blast-radius + External-asset Lineage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Trace a semantic data incident past the warehouse to the dashboards, ML features, and applications that consume it, name them, and raise incident severity when a business-critical consumer is in the blast radius.

**Architecture:** dbt *exposures* (from `manifest.json`) become `kind="exposure"` nodes in the existing `networkx` lineage graph, with edges `model → exposure`. A new `assess_impact` groups the exposures reachable from an incident's blast radius and reports the worst criticality; incident severity is raised (never lowered), gated on materiality, when that criticality warrants it. A labeled benchmark with decoys proves the affected-exposure set and per-case severity.

**Tech Stack:** Python 3.11, networkx, dataclasses, `enum.IntEnum`, pytest, ruff (line-length 100). No numpy/pandas/sklearn.

**Spec:** `docs/superpowers/specs/2026-08-27-m4-blast-radius-design.md`

## Global Constraints

- **Reliability wins** over breadth: severity escalation is raise-only and materiality-gated; an immaterial change (`magnitude < MAGNITUDE_MATERIAL = 0.1`) never escalates.
- **Backward compatible:** a manifest with no `exposures` key builds an identical graph to today; an incident with no affected exposures behaves exactly as before (`business_impact = None`, severity/summary/render unchanged).
- **Strict TDD:** RED (write failing test) → GREEN (minimal code) → REFACTOR. One behavior per test.
- **ruff line-length 100.** Match surrounding docstring/comment density.
- **Determinism:** all ordering is explicit (criticality desc, then name); no reliance on dict/set iteration order. CI runs under an alternate `PYTHONHASHSEED`.
- **Commits authored as Anuran De, NO Co-Authored-By trailer.** Each commit step uses:
  ```bash
  git -c user.name="Anuran De" -c user.email="121761842+anuran-de@users.noreply.github.com" \
    commit -m "<message>" --author="Anuran De <121761842+anuran-de@users.noreply.github.com>"
  ```
- **Activate the venv first:** `source .venv/Scripts/activate` (Windows Git Bash).
- After the code lands, update `README.md`, `CHANGELOG.md`, `docs/architecture.md` (Task 7) and push.

## File Structure

- `src/dvi/lineage/exposure.py` — **new.** `Criticality` (IntEnum), `Exposure` (frozen dataclass), `derive_criticality`. Pure data + one derivation function; no graph knowledge.
- `src/dvi/lineage/graph.py` — **modify.** Second parse pass over `manifest["exposures"]`; `kind`-tagged nodes; two traversal helpers.
- `src/dvi/lineage/__init__.py` — **modify.** Export new names.
- `src/dvi/incidents/impact.py` — **new.** `BusinessImpact` (frozen dataclass), `assess_impact`, `criticality_to_severity`, `escalate_severity`, `render_business_impact`. Owns the impact→severity mapping and the rendering.
- `src/dvi/incidents/incident.py` — **modify.** New `business_impact` field; wire impact + escalation + summary clause.
- `src/dvi/incidents/__init__.py` — **modify.** Export new names.
- `src/dvi/benchmark/blast_radius.py` — **new.** `BlastRadiusCase`, `build_blast_radius_cases`, `BlastRadiusReport`, `evaluate_blast_radius`.
- `src/dvi/benchmark/__init__.py` — **modify.** Export new names.
- `scripts/demo.py` — **modify.** Add exposures to the demo lineage, print the impact block.
- `scripts/benchmark.py` — **modify.** Print the blast-radius section.
- Tests: `tests/test_lineage_exposure.py`, `tests/test_lineage_graph_exposures.py`, `tests/test_incidents_impact.py`, `tests/test_incident_business_impact.py`, `tests/test_benchmark_blast_radius.py`.

---

### Task 1: Criticality + Exposure data model

**Files:**
- Create: `src/dvi/lineage/exposure.py`
- Test: `tests/test_lineage_exposure.py`

**Interfaces:**
- Consumes: nothing (leaf module).
- Produces:
  - `class Criticality(IntEnum)` with `LOW=1, MEDIUM=2, HIGH=3, CRITICAL=4`.
  - `@dataclass(frozen=True) class Exposure` with fields `unique_id: str, name: str, type: str, criticality: Criticality, owner: str, url: str, depends_on: frozenset[str]`.
  - `derive_criticality(type: str, maturity: str, meta: dict) -> Criticality`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_lineage_exposure.py
from dvi.lineage import Criticality, Exposure, derive_criticality


def test_criticality_is_ordered_for_worst_of():
    assert Criticality.LOW < Criticality.MEDIUM < Criticality.HIGH < Criticality.CRITICAL
    assert max(Criticality.LOW, Criticality.HIGH) is Criticality.HIGH


def test_meta_override_wins_over_derivation():
    # An otherwise-medium dashboard flagged critical by its owner.
    c = derive_criticality("dashboard", "medium", {"criticality": "critical"})
    assert c is Criticality.CRITICAL


def test_customer_facing_application_at_high_maturity_is_critical():
    assert derive_criticality("application", "high", {}) is Criticality.CRITICAL


def test_application_below_high_maturity_is_high():
    assert derive_criticality("application", "medium", {}) is Criticality.HIGH


def test_ml_is_high():
    assert derive_criticality("ml", "low", {}) is Criticality.HIGH


def test_dashboard_maps_maturity():
    assert derive_criticality("dashboard", "high", {}) is Criticality.HIGH
    assert derive_criticality("dashboard", "medium", {}) is Criticality.MEDIUM
    assert derive_criticality("dashboard", "low", {}) is Criticality.LOW
    assert derive_criticality("dashboard", "", {}) is Criticality.MEDIUM  # default


def test_notebook_and_analysis_are_low():
    assert derive_criticality("notebook", "high", {}) is Criticality.LOW
    assert derive_criticality("analysis", "high", {}) is Criticality.LOW


def test_unknown_type_defaults_to_medium():
    assert derive_criticality("whatever", "high", {}) is Criticality.MEDIUM


def test_invalid_meta_override_falls_back_to_derivation():
    # A garbage override string must not crash; fall back to type/maturity.
    assert derive_criticality("ml", "low", {"criticality": "bogus"}) is Criticality.HIGH


def test_exposure_is_frozen_and_hashable():
    e = Exposure("exposure.shop.d", "d", "dashboard", Criticality.HIGH, "jane", "", frozenset({"m"}))
    assert e.criticality is Criticality.HIGH
    assert hash(e)  # frozen dataclass is hashable
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_lineage_exposure.py -v`
Expected: FAIL with `ImportError: cannot import name 'Criticality'`.

- [ ] **Step 3: Write the implementation**

```python
# src/dvi/lineage/exposure.py
"""External consumers of the warehouse — dbt *exposures* — and their business
criticality.

An exposure is a dashboard, ML feature/model, application, or notebook that
reads one or more dbt models. Criticality is an ordered scale so the *worst*
consumer in a blast radius is just a ``max()``. It is either declared explicitly
in the exposure's ``meta.criticality`` or inferred from its ``type`` and dbt
``maturity``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum


class Criticality(IntEnum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


@dataclass(frozen=True)
class Exposure:
    unique_id: str
    name: str
    type: str
    criticality: Criticality
    owner: str
    url: str
    depends_on: frozenset[str]


_OVERRIDE = {
    "low": Criticality.LOW,
    "medium": Criticality.MEDIUM,
    "high": Criticality.HIGH,
    "critical": Criticality.CRITICAL,
}

_MATURITY = {"high": Criticality.HIGH, "medium": Criticality.MEDIUM, "low": Criticality.LOW}


def derive_criticality(type: str, maturity: str, meta: dict) -> Criticality:
    """Business criticality of an exposure.

    Precedence: an explicit ``meta.criticality`` override wins; otherwise a
    customer-facing ``application`` at ``maturity == "high"`` is CRITICAL; then
    per-type defaults (application/ml -> HIGH, dashboard -> its maturity,
    notebook/analysis -> LOW, anything else -> MEDIUM).
    """
    override = str((meta or {}).get("criticality", "")).lower()
    if override in _OVERRIDE:
        return _OVERRIDE[override]

    if type == "application":
        if maturity == "high":
            return Criticality.CRITICAL
        return Criticality.HIGH
    if type == "ml":
        return Criticality.HIGH
    if type == "dashboard":
        return _MATURITY.get(maturity, Criticality.MEDIUM)
    if type in {"notebook", "analysis"}:
        return Criticality.LOW
    return Criticality.MEDIUM
```

- [ ] **Step 4: Wire exports**

Modify `src/dvi/lineage/__init__.py` to:

```python
"""Lineage: reconstruct the data dependency graph from dbt metadata."""

from .exposure import Criticality, Exposure, derive_criticality
from .graph import LineageGraph, load_dbt_manifest

__all__ = [
    "Criticality",
    "Exposure",
    "LineageGraph",
    "derive_criticality",
    "load_dbt_manifest",
]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_lineage_exposure.py -v && ruff check src/dvi/lineage/exposure.py`
Expected: PASS, ruff clean.

- [ ] **Step 6: Commit**

```bash
git add src/dvi/lineage/exposure.py src/dvi/lineage/__init__.py tests/test_lineage_exposure.py
git -c user.name="Anuran De" -c user.email="121761842+anuran-de@users.noreply.github.com" \
  commit -m "feat(lineage): exposure model + business criticality derivation" \
  --author="Anuran De <121761842+anuran-de@users.noreply.github.com>"
```

---

### Task 2: Parse exposures into the lineage graph + traversal helpers

**Files:**
- Modify: `src/dvi/lineage/graph.py`
- Test: `tests/test_lineage_graph_exposures.py`

**Interfaces:**
- Consumes: `Exposure`, `Criticality`, `derive_criticality` from Task 1.
- Produces:
  - `load_dbt_manifest` now also reads `manifest["exposures"]`, adding each as a node with attrs `kind="exposure", exposure=<Exposure>`, edges `model → exposure.unique_id` for known models; existing data nodes gain `kind="data"`.
  - `LineageGraph.exposures_downstream_of(assets: set[str]) -> list[Exposure]` — exposures reachable downstream from any asset, sorted by `(-criticality, name)`.
  - `LineageGraph.data_downstream_of(assets: set[str]) -> set[str]` — descendants excluding exposure nodes.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_lineage_graph_exposures.py
from dvi.lineage import Criticality, LineageGraph, load_dbt_manifest


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_lineage_graph_exposures.py -v`
Expected: FAIL (`node_kind`/`exposures_downstream_of` missing, exposures not parsed).

- [ ] **Step 3: Add the traversal helpers to `LineageGraph`**

In `src/dvi/lineage/graph.py`, add the import at the top:

```python
from .exposure import Exposure, derive_criticality
```

Add these methods to `LineageGraph` (after `is_downstream_of`):

```python
    def node_kind(self, node: str) -> str | None:
        """``"data"`` | ``"exposure"`` | ``None`` if the node is unknown."""
        if node not in self._g:
            return None
        return self._g.nodes[node].get("kind")

    def _reachable(self, assets: set[str]) -> set[str]:
        out: set[str] = set()
        for asset in assets:
            out |= self.downstream(asset)
        return out

    def exposures_downstream_of(self, assets: set[str]) -> list[Exposure]:
        """Exposure objects reachable downstream from any of ``assets``.

        Sorted by criticality (worst first), then name — deterministic.
        """
        found = [
            self._g.nodes[n]["exposure"]
            for n in self._reachable(assets)
            if self._g.nodes[n].get("kind") == "exposure"
        ]
        return sorted(found, key=lambda e: (-int(e.criticality), e.name))

    def data_downstream_of(self, assets: set[str]) -> set[str]:
        """Descendants of ``assets`` that are data nodes (exposures excluded)."""
        return {n for n in self._reachable(assets) if self._g.nodes[n].get("kind") != "exposure"}
```

- [ ] **Step 4: Parse exposures in `load_dbt_manifest`**

Replace the body of `load_dbt_manifest` (keep the docstring, extend it) so data nodes are tagged `kind="data"` and a second pass adds exposures:

```python
    graph = LineageGraph()
    nodes: dict[str, dict] = manifest.get("nodes", {})
    for unique_id, node in nodes.items():
        graph.add_node(
            unique_id,
            kind="data",
            resource_type=node.get("resource_type"),
        )
    for unique_id, node in nodes.items():
        for dependency in node.get("depends_on", {}).get("nodes", []):
            if dependency in nodes:
                graph.add_edge(dependency, unique_id)

    exposures: dict[str, dict] = manifest.get("exposures", {})
    for unique_id, raw in exposures.items():
        owner = raw.get("owner") or {}
        exposure = Exposure(
            unique_id=unique_id,
            name=raw.get("name", unique_id),
            type=raw.get("type", ""),
            criticality=derive_criticality(
                raw.get("type", ""), raw.get("maturity", ""), raw.get("meta", {})
            ),
            owner=owner.get("name") or owner.get("email") or "",
            url=raw.get("url", ""),
            depends_on=frozenset(raw.get("depends_on", {}).get("nodes", [])),
        )
        graph.add_node(unique_id, kind="exposure", exposure=exposure)
        for dependency in exposure.depends_on:
            if dependency in nodes:
                graph.add_edge(dependency, unique_id)
    return graph
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_lineage_graph_exposures.py tests/test_lineage_exposure.py -v && ruff check src/dvi/lineage`
Expected: PASS, ruff clean.

- [ ] **Step 6: Run the full lineage/existing suite for regressions**

Run: `pytest tests/ -k "lineage or manifest or rca or incident" -q`
Expected: PASS (backward compatibility holds).

- [ ] **Step 7: Commit**

```bash
git add src/dvi/lineage/graph.py tests/test_lineage_graph_exposures.py
git -c user.name="Anuran De" -c user.email="121761842+anuran-de@users.noreply.github.com" \
  commit -m "feat(lineage): parse dbt exposures + downstream-exposure traversal" \
  --author="Anuran De <121761842+anuran-de@users.noreply.github.com>"
```

---

### Task 3: BusinessImpact + assess_impact + severity escalation + rendering

**Files:**
- Create: `src/dvi/incidents/impact.py`
- Modify: `src/dvi/incidents/__init__.py`
- Test: `tests/test_incidents_impact.py`

**Interfaces:**
- Consumes: `Criticality`, `Exposure`, `LineageGraph` from lineage.
- Produces:
  - `@dataclass(frozen=True) class BusinessImpact` with `exposures: tuple[Exposure, ...]`, `by_type: dict[str, list[Exposure]]`, `max_criticality: Criticality | None`.
  - `assess_impact(affected_assets: set[str], lineage: LineageGraph) -> BusinessImpact`.
  - `criticality_to_severity(c: Criticality) -> str` → `"low"|"medium"|"high"|"critical"`.
  - `escalate_severity(base: str, impact: BusinessImpact, max_magnitude: float) -> str` — raise-only, materiality-gated.
  - `render_business_impact(impact: BusinessImpact) -> list[str]` — grouped terminal lines (empty list when no exposures).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_incidents_impact.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_incidents_impact.py -v`
Expected: FAIL (`No module named 'dvi.incidents.impact'`).

- [ ] **Step 3: Write the implementation**

```python
# src/dvi/incidents/impact.py
"""Business-level blast radius: which external consumers a data incident reaches,
and how that lifts severity.

An incident's data-asset blast radius is projected onto the dbt *exposures*
downstream of it. The worst consumer criticality can *raise* incident severity
(never lower it), and only for a *material* change — an immaterial flicker under
a critical dashboard stays low. Rendering groups the affected consumers by type
for the operator.
"""

from __future__ import annotations

from dataclasses import dataclass

from dvi.lineage import Criticality, Exposure, LineageGraph

# Kept in sync with incidents.incident.MAGNITUDE_MATERIAL; imported there too.
MAGNITUDE_MATERIAL = 0.1

_SEVERITY_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}
_CRIT_TO_SEVERITY = {
    Criticality.LOW: "low",
    Criticality.MEDIUM: "medium",
    Criticality.HIGH: "high",
    Criticality.CRITICAL: "critical",
}
# Fixed display order + human labels for the grouped block.
_TYPE_ORDER = ["application", "ml", "dashboard", "notebook", "analysis"]
_TYPE_LABEL = {
    "application": "Applications",
    "ml": "ML features",
    "dashboard": "Dashboards",
    "notebook": "Notebooks",
    "analysis": "Analyses",
}


@dataclass(frozen=True)
class BusinessImpact:
    exposures: tuple[Exposure, ...]
    by_type: dict[str, list[Exposure]]
    max_criticality: Criticality | None


def assess_impact(affected_assets: set[str], lineage: LineageGraph) -> BusinessImpact:
    """Exposures reachable from the incident's data-asset blast radius."""
    exposures = tuple(lineage.exposures_downstream_of(affected_assets))
    by_type: dict[str, list[Exposure]] = {}
    for exposure in exposures:
        by_type.setdefault(exposure.type, []).append(exposure)
    worst = max((e.criticality for e in exposures), default=None)
    return BusinessImpact(exposures=exposures, by_type=by_type, max_criticality=worst)


def criticality_to_severity(criticality: Criticality) -> str:
    return _CRIT_TO_SEVERITY[criticality]


def escalate_severity(base: str, impact: BusinessImpact, max_magnitude: float) -> str:
    """Raise ``base`` to the consumer-implied severity — only if material."""
    if max_magnitude < MAGNITUDE_MATERIAL or impact.max_criticality is None:
        return base
    implied = criticality_to_severity(impact.max_criticality)
    return max(base, implied, key=_SEVERITY_ORDER.__getitem__)


def render_business_impact(impact: BusinessImpact) -> list[str]:
    """Grouped, deterministically-ordered terminal lines (empty if no impact)."""
    if not impact.exposures:
        return []
    lines = ["  Business impact:"]
    for type_ in _TYPE_ORDER:
        group = impact.by_type.get(type_)
        if not group:
            continue
        rendered = ", ".join(
            f"{e.name} [{e.criticality.name}]" + (f" @{e.owner}" if e.owner else "")
            for e in group
        )
        lines.append(f"    {_TYPE_LABEL[type_]} ({len(group)}): {rendered}")
    return lines
```

Note: `by_type` groups preserve the criticality-then-name order from `exposures_downstream_of` (Task 2), since we append in that order.

- [ ] **Step 4: Wire exports**

Modify `src/dvi/incidents/__init__.py`:

```python
"""Incident synthesis: turn a corroborated cause into an evidence-backed incident."""

from .impact import (
    BusinessImpact,
    assess_impact,
    criticality_to_severity,
    escalate_severity,
    render_business_impact,
)
from .incident import Incident, synthesize_incident

__all__ = [
    "BusinessImpact",
    "Incident",
    "assess_impact",
    "criticality_to_severity",
    "escalate_severity",
    "render_business_impact",
    "synthesize_incident",
]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_incidents_impact.py -v && ruff check src/dvi/incidents/impact.py`
Expected: PASS, ruff clean.

- [ ] **Step 6: Commit**

```bash
git add src/dvi/incidents/impact.py src/dvi/incidents/__init__.py tests/test_incidents_impact.py
git -c user.name="Anuran De" -c user.email="121761842+anuran-de@users.noreply.github.com" \
  commit -m "feat(incidents): business-impact assessment + severity escalation" \
  --author="Anuran De <121761842+anuran-de@users.noreply.github.com>"
```

---

### Task 4: Wire business impact into the Incident

**Files:**
- Modify: `src/dvi/incidents/incident.py`
- Test: `tests/test_incident_business_impact.py`

**Interfaces:**
- Consumes: `assess_impact`, `escalate_severity`, `BusinessImpact` (Task 3); `load_dbt_manifest` (Task 2).
- Produces: `Incident` gains `business_impact: BusinessImpact | None = None`; `synthesize_incident` sets it, applies escalated severity, and appends a summary clause when exposures are affected.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_incident_business_impact.py
from datetime import datetime

from dvi.detection import Symptom
from dvi.incidents import synthesize_incident
from dvi.lineage import Criticality, load_dbt_manifest
from dvi.rca import ChangeEvent, Observation, RootCauseCandidate

CHANGED = "model.shop.fact_orders"


def _manifest(app_maturity="high", magnitude=0.4):
    return {
        "nodes": {
            CHANGED: {"resource_type": "model", "depends_on": {"nodes": []}},
            "model.shop.revenue_daily": {
                "resource_type": "model",
                "depends_on": {"nodes": [CHANGED]},
            },
        },
        "exposures": {
            "exposure.shop.pricing_api": {
                "name": "pricing_api", "type": "application", "maturity": app_maturity,
                "owner": {"name": "platform"}, "meta": {},
                "depends_on": {"nodes": ["model.shop.revenue_daily"]},
            },
        },
    }


def _candidate(magnitude):
    symptom = Symptom(
        signature="value_substitution", column="country", magnitude=magnitude,
        from_value="UK", to_value="United Kingdom", description="UK -> United Kingdom",
    )
    obs = Observation("model.shop.revenue_daily", datetime(2026, 8, 25, 10, 0), symptom)
    change = ChangeEvent("deploy", datetime(2026, 8, 25, 9, 50), [CHANGED], "deploy")
    return RootCauseCandidate(change=change, score=1.0, explained=[obs], evidence=["e"])


def test_material_incident_under_application_escalates_to_critical():
    g = load_dbt_manifest(_manifest())
    incident = synthesize_incident([_candidate(0.4)], g, [])
    assert incident.severity == "critical"
    assert incident.business_impact is not None
    assert incident.business_impact.max_criticality is Criticality.CRITICAL
    assert "pricing_api" in incident.summary or "application" in incident.summary


def test_immaterial_change_stays_low_despite_critical_consumer():
    g = load_dbt_manifest(_manifest())
    incident = synthesize_incident([_candidate(0.05)], g, [])
    assert incident.severity == "low"


def test_no_exposures_leaves_business_impact_none_and_severity_unchanged():
    g = load_dbt_manifest({"nodes": _manifest()["nodes"]})
    incident = synthesize_incident([_candidate(0.4)], g, [])
    assert incident.business_impact is None
    assert incident.severity == "high"  # propagates to revenue_daily, no escalation
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_incident_business_impact.py -v`
Expected: FAIL (`Incident` has no `business_impact`; severity not escalated).

- [ ] **Step 3: Modify `incident.py`**

Add the import near the top (after the existing `from dvi.rca import ...`):

```python
from .impact import BusinessImpact, assess_impact, escalate_severity, render_business_impact
```

Add the field to the `Incident` dataclass (after `confidence`):

```python
    business_impact: BusinessImpact | None = None
```

In `synthesize_incident`, after `affected`/`propagates`/`max_magnitude`/`severity` are computed, insert the impact assessment and escalation (the impact scope includes the change targets so an exposure hanging directly off a changed model is caught):

```python
    impact_scope = affected | set(top.change.targets)
    impact = assess_impact(impact_scope, lineage)
    severity = escalate_severity(severity, impact, max_magnitude)
```

Extend the summary with a business clause when exposures are affected (build it after the existing `summary = (...)` assignment):

```python
    if impact.exposures:
        counts = ", ".join(
            f"{len(group)} {type_}" for type_, group in impact.by_type.items()
        )
        summary += (
            f" Reaches {len(impact.exposures)} external consumer(s): {counts} "
            f"(worst: {impact.max_criticality.name})."
        )
```

Pass the impact into the returned `Incident`:

```python
        confidence=worst.symptom.confidence,
        business_impact=impact,
```

Note: `impact` is always a `BusinessImpact`; when nothing external is reached it has `exposures == ()` and `max_criticality is None`. Per the spec, expose `None` in that case — set `business_impact=impact if impact.exposures else None` in the constructor call instead of `business_impact=impact`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_incident_business_impact.py tests/test_incidents_impact.py -v && ruff check src/dvi/incidents`
Expected: PASS, ruff clean.

- [ ] **Step 5: Full regression**

Run: `pytest tests/ -q`
Expected: PASS — existing incident tests unaffected (no-exposures path is unchanged).

- [ ] **Step 6: Commit**

```bash
git add src/dvi/incidents/incident.py tests/test_incident_business_impact.py
git -c user.name="Anuran De" -c user.email="121761842+anuran-de@users.noreply.github.com" \
  commit -m "feat(incidents): surface business impact + escalate severity on incidents" \
  --author="Anuran De <121761842+anuran-de@users.noreply.github.com>"
```

---

### Task 5: Blast-radius benchmark (labeled cases + evaluation)

**Files:**
- Create: `src/dvi/benchmark/blast_radius.py`
- Modify: `src/dvi/benchmark/__init__.py`
- Test: `tests/test_benchmark_blast_radius.py`

**Interfaces:**
- Consumes: `LineageGraph`, `assess_impact`, `escalate_severity`, `synthesize_incident`, `Criticality`.
- Produces:
  - `@dataclass(frozen=True) class BlastRadiusCase` with `name, lineage, changed: str, expected_exposures: set[str], expected_severity: str, note`.
  - `build_blast_radius_cases() -> list[BlastRadiusCase]`.
  - `@dataclass(frozen=True) class BlastRadiusCaseResult` with `case, found_exposures: set[str], severity: str, exposures_correct: bool, severity_correct: bool`.
  - `@dataclass(frozen=True) class BlastRadiusReport` with `results`, and properties `precision`, `recall`, `severity_accuracy`, `wrong`.
  - `evaluate_blast_radius(cases=None) -> BlastRadiusReport`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_benchmark_blast_radius.py
from dvi.benchmark import build_blast_radius_cases, evaluate_blast_radius


def test_suite_has_positives_and_decoys():
    cases = build_blast_radius_cases()
    assert len(cases) >= 5
    names = {c.name for c in cases}
    assert "sibling_decoy" in names
    assert "notebook_no_escalation" in names


def test_blast_radius_is_perfect_on_the_labeled_suite():
    report = evaluate_blast_radius()
    assert report.precision == 1.0
    assert report.recall == 1.0
    assert report.severity_accuracy == 1.0
    assert report.wrong == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_benchmark_blast_radius.py -v`
Expected: FAIL (`cannot import name 'build_blast_radius_cases'`).

- [ ] **Step 3: Write the benchmark module**

```python
# src/dvi/benchmark/blast_radius.py
"""Labeled blast-radius cases: does DVI name the right external consumers, and
does a business-critical consumer lift severity — without false alarms?

Each case is a hand-built lineage with a changed data asset, the ground-truth
set of affected exposures, and the expected incident severity. Decoys must NOT
appear in the affected set or escalate severity:

  * ``sibling_decoy`` — an exposure fed by a *sibling* table, off the blast path;
  * ``ancestor_decoy`` — an exposure on an *upstream* asset, not downstream;
  * ``notebook_no_escalation`` — a LOW notebook is affected but must not escalate.

Positives exercise each escalation path: a high-maturity dashboard (-> high), a
customer-facing application at high maturity (-> critical), and an explicit
``meta.criticality: critical`` override on an otherwise-medium exposure.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from dvi.detection import Symptom
from dvi.incidents import synthesize_incident
from dvi.lineage import LineageGraph, load_dbt_manifest
from dvi.rca import ChangeEvent, Observation, RootCauseCandidate


@dataclass(frozen=True)
class BlastRadiusCase:
    name: str
    lineage: LineageGraph
    changed: str
    expected_exposures: set[str]
    expected_severity: str
    note: str = ""


@dataclass(frozen=True)
class BlastRadiusCaseResult:
    case: BlastRadiusCase
    found_exposures: set[str]
    severity: str
    exposures_correct: bool
    severity_correct: bool


@dataclass(frozen=True)
class BlastRadiusReport:
    results: list[BlastRadiusCaseResult]

    @property
    def precision(self) -> float:
        tp = fp = 0
        for r in self.results:
            tp += len(r.found_exposures & r.case.expected_exposures)
            fp += len(r.found_exposures - r.case.expected_exposures)
        denom = tp + fp
        return tp / denom if denom else 1.0

    @property
    def recall(self) -> float:
        tp = fn = 0
        for r in self.results:
            tp += len(r.found_exposures & r.case.expected_exposures)
            fn += len(r.case.expected_exposures - r.found_exposures)
        denom = tp + fn
        return tp / denom if denom else 1.0

    @property
    def severity_accuracy(self) -> float:
        if not self.results:
            return 1.0
        return sum(r.severity_correct for r in self.results) / len(self.results)

    @property
    def wrong(self) -> list[str]:
        return [
            r.case.name
            for r in self.results
            if not (r.exposures_correct and r.severity_correct)
        ]


def _exposure(uid, name, type_, maturity, deps, meta=None):
    return {
        uid: {
            "name": name, "type": type_, "maturity": maturity,
            "owner": {"name": "owner"}, "meta": meta or {},
            "depends_on": {"nodes": list(deps)},
        }
    }


def _model(uid, deps=()):
    return {uid: {"resource_type": "model", "depends_on": {"nodes": list(deps)}}}


def build_blast_radius_cases() -> list[BlastRadiusCase]:
    cases: list[BlastRadiusCase] = []

    # 1. High-maturity dashboard downstream -> severity high.
    nodes = {**_model("m.fact"), **_model("m.rev", ["m.fact"])}
    exp = _exposure("e.dash", "exec_dashboard", "dashboard", "high", ["m.rev"])
    cases.append(
        BlastRadiusCase(
            "dashboard_high", load_dbt_manifest({"nodes": nodes, "exposures": exp}),
            "m.fact", {"e.dash"}, "high",
            note="material change reaching a high-maturity dashboard",
        )
    )

    # 2. Customer-facing application at high maturity -> critical.
    exp = _exposure("e.api", "pricing_api", "application", "high", ["m.rev"])
    cases.append(
        BlastRadiusCase(
            "application_critical", load_dbt_manifest({"nodes": nodes, "exposures": exp}),
            "m.fact", {"e.api"}, "critical",
            note="application at maturity:high escalates to critical",
        )
    )

    # 3. meta.criticality override lifts an otherwise-medium dashboard to critical.
    exp = _exposure(
        "e.ovr", "flagged", "dashboard", "medium", ["m.rev"], meta={"criticality": "critical"}
    )
    cases.append(
        BlastRadiusCase(
            "override_critical", load_dbt_manifest({"nodes": nodes, "exposures": exp}),
            "m.fact", {"e.ovr"}, "critical",
            note="explicit meta override wins over derivation",
        )
    )

    # 4. Sibling decoy: exposure fed by a sibling of the changed asset, not downstream.
    nodes4 = {
        **_model("m.root"), **_model("m.a", ["m.root"]), **_model("m.b", ["m.root"]),
    }
    exp4 = _exposure("e.sib", "sibling_dash", "dashboard", "high", ["m.b"])
    cases.append(
        BlastRadiusCase(
            "sibling_decoy", load_dbt_manifest({"nodes": nodes4, "exposures": exp4}),
            "m.a", set(), "medium",
            note="exposure on a sibling branch must not appear or escalate",
        )
    )

    # 5. Ancestor decoy: exposure attached upstream of the change, not reachable downstream.
    nodes5 = {**_model("m.up"), **_model("m.mid", ["m.up"]), **_model("m.down", ["m.mid"])}
    exp5 = _exposure("e.anc", "up_dash", "dashboard", "high", ["m.up"])
    cases.append(
        BlastRadiusCase(
            "ancestor_decoy", load_dbt_manifest({"nodes": nodes5, "exposures": exp5}),
            "m.mid", set(), "high",
            note="upstream exposure is not in the downstream blast radius",
        )
    )

    # 6. Notebook is affected but LOW -> must not escalate above the base severity.
    exp6 = _exposure("e.nb", "scratch", "notebook", "high", ["m.rev"])
    cases.append(
        BlastRadiusCase(
            "notebook_no_escalation", load_dbt_manifest({"nodes": nodes, "exposures": exp6}),
            "m.fact", {"e.nb"}, "high",
            note="LOW notebook is named but severity stays at the base (propagates=high)",
        )
    )

    return cases


def _symptom() -> Symptom:
    return Symptom(
        signature="value_substitution", column="country", magnitude=0.4,
        from_value="UK", to_value="United Kingdom", description="UK -> United Kingdom",
    )


def _incident_for(case: BlastRadiusCase):
    # Symptom lands on the nearest downstream data asset (or the changed asset when
    # it has no downstream data), so the change corroborates it.
    data_down = sorted(case.lineage.data_downstream_of({case.changed}))
    asset = data_down[0] if data_down else case.changed
    obs = Observation(asset, datetime(2026, 8, 25, 10, 0), _symptom())
    change = ChangeEvent("deploy", datetime(2026, 8, 25, 9, 50), [case.changed], "deploy")
    candidate = RootCauseCandidate(change=change, score=1.0, explained=[obs], evidence=["e"])
    return synthesize_incident([candidate], case.lineage, [])


def evaluate_blast_radius(cases: list[BlastRadiusCase] | None = None) -> BlastRadiusReport:
    if cases is None:
        cases = build_blast_radius_cases()
    results: list[BlastRadiusCaseResult] = []
    for case in cases:
        incident = _incident_for(case)
        impact = incident.business_impact
        found = {e.unique_id for e in impact.exposures} if impact else set()
        exposures_correct = found == case.expected_exposures
        severity_correct = incident.severity == case.expected_severity
        results.append(
            BlastRadiusCaseResult(
                case, found, incident.severity, exposures_correct, severity_correct
            )
        )
    return BlastRadiusReport(results)
```

- [ ] **Step 4: Wire exports**

Add to `src/dvi/benchmark/__init__.py` — import block and `__all__` (insert alphabetically):

```python
from .blast_radius import (
    BlastRadiusCase,
    BlastRadiusCaseResult,
    BlastRadiusReport,
    build_blast_radius_cases,
    evaluate_blast_radius,
)
```

Add `"BlastRadiusCase"`, `"BlastRadiusCaseResult"`, `"BlastRadiusReport"`, `"build_blast_radius_cases"`, `"evaluate_blast_radius"` to `__all__`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_benchmark_blast_radius.py -v && ruff check src/dvi/benchmark/blast_radius.py`
Expected: PASS (precision/recall/severity all 1.0), ruff clean.

If a decoy case fails severity: confirm the base `_severity` for that lineage. `sibling_decoy` changes `m.a` which has no downstream data asset and no exposure, so `propagates=False`, `max_magnitude=0.4` → base `medium`, no escalation → `medium` (matches label). `ancestor_decoy` changes `m.mid` → downstream `m.down` (data) so `propagates=True` → `high`, no exposure escalation → `high` (matches).

- [ ] **Step 6: Commit**

```bash
git add src/dvi/benchmark/blast_radius.py src/dvi/benchmark/__init__.py tests/test_benchmark_blast_radius.py
git -c user.name="Anuran De" -c user.email="121761842+anuran-de@users.noreply.github.com" \
  commit -m "feat(benchmark): labeled blast-radius suite with decoys (100% precision/recall)" \
  --author="Anuran De <121761842+anuran-de@users.noreply.github.com>"
```

---

### Task 6: Demo + benchmark scripts

**Files:**
- Modify: `scripts/demo.py`
- Modify: `scripts/benchmark.py`

**Interfaces:**
- Consumes: `render_business_impact` (Task 3), `evaluate_blast_radius` (Task 5).
- Produces: no importable API; visible output only. Manually run and eyeball.

- [ ] **Step 1: Add exposures to the demo lineage**

In `scripts/demo.py`, replace `build_lineage` so the demo carries one high-criticality consumer and one decoy, and import the renderer. Change the import block to add:

```python
from dvi.incidents import render_business_impact
from dvi.lineage import Criticality, Exposure
```

Replace `build_lineage`:

```python
def build_lineage() -> LineageGraph:
    g = LineageGraph()
    g.add_node(ASSET, kind="data")
    g.add_node("model.shop.revenue_daily", kind="data")
    g.add_edge(ASSET, "model.shop.revenue_daily")

    exec_dash = Exposure(
        "exposure.shop.exec_dashboard", "exec_dashboard", "dashboard",
        Criticality.HIGH, "jane", "https://bi/exec",
        frozenset({"model.shop.revenue_daily"}),
    )
    pricing_api = Exposure(
        "exposure.shop.pricing_api", "pricing_api", "application",
        Criticality.CRITICAL, "platform", "https://api/pricing",
        frozenset({"model.shop.revenue_daily"}),
    )
    for e in (exec_dash, pricing_api):
        g.add_node(e.unique_id, kind="exposure", exposure=e)
        for dep in e.depends_on:
            g.add_edge(dep, e.unique_id)
    return g
```

- [ ] **Step 2: Print the impact block in the demo**

After the "Affected downstream assets" loop in `main`, add:

```python
    if incident.business_impact is not None:
        print()
        for line in render_business_impact(incident.business_impact):
            print(line)
```

- [ ] **Step 3: Run the demo and eyeball**

Run: `python scripts/demo.py`
Expected: severity now `CRITICAL`; a "Business impact:" block lists `pricing_api [CRITICAL] @platform` and `exec_dashboard [HIGH] @jane`.

- [ ] **Step 4: Add the blast-radius section to the benchmark script**

In `scripts/benchmark.py`, add `evaluate_blast_radius` to the `from dvi.benchmark import (...)` block. After the RCA section (before the real-data section), add:

```python
    blast = evaluate_blast_radius()
    print("\n  Blast-radius / business impact (labeled, with decoys):")
    print(f"    cases              : {len(blast.results)}")
    print(f"    exposure precision : {blast.precision:.0%}")
    print(f"    exposure recall    : {blast.recall:.0%}")
    print(f"    severity accuracy  : {blast.severity_accuracy:.0%}")
    if blast.wrong:
        print(f"    wrong              : {', '.join(blast.wrong)}")
```

- [ ] **Step 5: Run the benchmark and eyeball**

Run: `python scripts/benchmark.py`
Expected: a "Blast-radius / business impact" section with 100% precision/recall/severity, no `wrong`.

- [ ] **Step 6: Commit**

```bash
git add scripts/demo.py scripts/benchmark.py
git -c user.name="Anuran De" -c user.email="121761842+anuran-de@users.noreply.github.com" \
  commit -m "feat(scripts): demo + benchmark surface business impact and blast radius" \
  --author="Anuran De <121761842+anuran-de@users.noreply.github.com>"
```

---

### Task 7: Docs — README, CHANGELOG, architecture

**Files:**
- Modify: `README.md`
- Modify: `CHANGELOG.md`
- Modify: `docs/architecture.md`

**Interfaces:** none (documentation only).

- [ ] **Step 1: Update `docs/architecture.md`**

Change the blast-radius row (line ~21) from `_(M4)_` planned to done, and add a short subsection describing exposures-as-nodes, `assess_impact`, and materiality-gated severity escalation. Read the surrounding table first to match its format exactly.

- [ ] **Step 2: Update `README.md`**

- Mark M4 done in the roadmap/milestone list.
- Add a "Business-level impact" bullet to the feature list: DVI names affected dashboards/ML/apps and escalates severity (new `critical` tier) for business-critical consumers, materiality-gated.
- Update the test count to the new total (run `pytest tests/ -q` and read the summary line for the exact number).

- [ ] **Step 3: Update `CHANGELOG.md`**

Add an M4 section: exposure parsing from dbt `manifest.json`, `Criticality`/`Exposure`, `assess_impact` + `render_business_impact`, `critical` severity tier with raise-only materiality-gated escalation, and the labeled blast-radius benchmark (100% precision/recall). Match the existing changelog entry style.

- [ ] **Step 4: Full verification**

Run: `source .venv/Scripts/activate && pytest tests/ -q && ruff check src tests scripts && python scripts/demo.py && python scripts/benchmark.py`
Expected: all tests pass, ruff clean, both scripts show the new business-impact output.

- [ ] **Step 5: Commit and push**

```bash
git add README.md CHANGELOG.md docs/architecture.md
git -c user.name="Anuran De" -c user.email="121761842+anuran-de@users.noreply.github.com" \
  commit -m "docs(m4): document blast-radius + business-level impact" \
  --author="Anuran De <121761842+anuran-de@users.noreply.github.com>"
git push
```

---

## Self-Review

**1. Spec coverage:**
- §3 data model → Task 1 (`Criticality`, `Exposure`, `derive_criticality`, both CRITICAL paths, all fallbacks). ✓
- §4 parsing/graph → Task 2 (`kind`-tagged nodes, `model → exposure` edges, dangling-ref skip, no-exposures unchanged, `exposures_downstream_of`, `data_downstream_of`). ✓
- §5 impact/severity → Task 3 (`BusinessImpact`, `assess_impact`, `criticality_to_severity`, raise-only materiality-gated `escalate_severity`). ✓
- §6 output → Task 3 (`render_business_impact`) + Task 4 (`Incident.business_impact`, summary clause, `None` when empty) + Task 6 (demo). ✓
- §7 benchmark → Task 5 (all three decoys + three positives, precision/recall + severity, 100% target) + Task 6 (benchmark script section). ✓
- §8 files touched → every listed file appears in a task. ✓
- §9 testing strategy → each bullet maps to a test in Tasks 1–5. ✓

**2. Placeholder scan:** No TBD/TODO; every code step has real code; the doc-prose steps (Task 7) intentionally describe edits to files whose exact current wording must be read first, with explicit run/verify commands. No "similar to Task N" — decoy severity reasoning is spelled out in Task 5 Step 5.

**3. Type consistency:**
- `Criticality` is an `IntEnum`; `-int(e.criticality)` (Task 2) and `max(..., key=_SEVERITY_ORDER.__getitem__)` (Task 3) are consistent.
- `Exposure.depends_on: frozenset[str]` produced in Task 2, consumed in Task 6 demo (`frozenset({...})`). ✓
- `BusinessImpact.exposures: tuple[Exposure, ...]` — Task 3 builds a tuple, Task 4 checks `impact.exposures` truthiness, Task 5 iterates `impact.exposures`. ✓
- `assess_impact(affected_assets, lineage)` and `escalate_severity(base, impact, max_magnitude)` signatures identical across Tasks 3, 4, 5. ✓
- `synthesize_incident([candidate], lineage, [])` call shape matches the existing signature `(ranked, lineage, observations)`. ✓
- `MAGNITUDE_MATERIAL = 0.1` defined in both `incident.py` (existing) and `impact.py` (Task 3) with the same value; `escalate_severity` uses `impact.py`'s copy — consistent, no drift risk since both are the same literal and the spec fixes it.

No issues found.
