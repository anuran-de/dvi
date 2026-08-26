# M4 — Blast-radius + external-asset lineage (design)

**Date:** 2026-08-27
**Milestone:** M4
**Headline claim:** *Business-level impact* — DVI names the dashboards, ML
features, and applications a silent data change actually reaches, and escalates
severity when a business-critical consumer is in the blast radius.

## 1. Problem

Lineage today models only **dbt data assets** (`manifest.json` `nodes`).
`synthesize_incident` computes a downstream blast-radius over those data assets,
but the people who feel a broken number are downstream of the data warehouse:
**BI dashboards, ML features/models, reverse-ETL applications/APIs.** DVI cannot
currently say "this rename hits the exec dashboard and the pricing API," so it
cannot express business-level impact or prioritize accordingly.

## 2. Decisions (locked during brainstorming)

1. **Source of external lineage:** dbt **exposures** (parsed from
   `manifest.json`). Reuse-dbt / integrate-don't-replace; zero new config for
   dbt shops.
2. **Output:** affected consumers grouped by type with owners, plus
   **criticality-aware severity** with a new top tier `critical`.
3. **Criticality derivation:** explicit `meta.criticality` override, with a smart
   guess fallback from `type` + `maturity`. `critical` is reached by **either**
   an explicit `meta.criticality: critical` **or** a customer-facing
   `application` at `maturity: high`.
4. **Proof:** a labeled blast-radius benchmark (precision/recall of the affected
   exposure set + per-case severity correctness) plus an updated demo.
5. **Graph shape (Approach A):** exposures are **typed nodes in the existing
   `networkx` lineage graph** (edges `model → exposure`), reusing the existing
   downstream traversal. Rejected: a separate exposure registry (B) and a
   dedicated exposure-graph wrapper (C) — both add a second reachability
   structure for a separation problem we don't have at this scale.

## 3. Data model

New module `src/dvi/lineage/exposure.py`:

```python
class Criticality(IntEnum):        # ordered -> max() gives "worst in blast radius"
    LOW = 1; MEDIUM = 2; HIGH = 3; CRITICAL = 4

@dataclass(frozen=True)
class Exposure:
    unique_id: str          # "exposure.shop.exec_dashboard"
    name: str               # "exec_dashboard"
    type: str               # dashboard | ml | application | notebook | analysis
    criticality: Criticality
    owner: str              # owner name/email, "" if absent
    url: str                # "" if absent
    depends_on: frozenset[str]   # data-asset ids it consumes
```

`derive_criticality(type, maturity, meta) -> Criticality`:

1. If `meta.criticality` set (`critical|high|medium|low`) → use it (override).
2. Else `type == "application"` and `maturity == "high"` → **CRITICAL**.
3. Else `type == "application"` → HIGH; `type == "ml"` → HIGH;
   `type == "dashboard"` → maturity mapped (`high/medium/low` →
   HIGH/MEDIUM/LOW, default MEDIUM); `type in {"notebook","analysis"}` → LOW;
   otherwise MEDIUM.

`Exposure` is frozen and criticality is an `IntEnum` so grouping and
worst-criticality are trivial and deterministic.

## 4. Parsing + graph wiring

`load_dbt_manifest` gains a second pass over `manifest["exposures"]`:

- Build an `Exposure` per entry (deriving criticality), then
  `add_node(exposure.unique_id, kind="exposure", exposure=<obj>)`.
- Add edge `model → exposure` for each id in the exposure's
  `depends_on.nodes`, **only** when the model is a known data node (skip
  dangling refs).
- Tag existing data nodes `kind="data"` for symmetry.

`LineageGraph` additions (traversal helpers; `downstream()` itself unchanged):

```python
def exposures_downstream_of(self, assets: set[str]) -> list[Exposure]:
    """Exposure objects reachable downstream from any of `assets`,
    sorted (criticality desc, name)."""

def data_downstream_of(self, assets: set[str]) -> set[str]:
    """Descendants of `assets` excluding exposure nodes."""
```

**Backward compatibility:** a manifest with no `exposures` key produces an
identical graph to today; existing traversals are unchanged.

## 5. Blast-radius + severity escalation

New module `src/dvi/incidents/impact.py`:

```python
@dataclass(frozen=True)
class BusinessImpact:
    exposures: list[Exposure]                # all affected, criticality-sorted
    by_type: dict[str, list[Exposure]]       # {"dashboard": [...], "ml": [...]}
    max_criticality: Criticality | None      # None if nothing external affected

def assess_impact(affected_assets: set[str], lineage: LineageGraph) -> BusinessImpact
```

`affected_assets` is the incident's existing data-asset blast set (change
targets ∪ symptomatic assets). `assess_impact` calls `exposures_downstream_of`,
groups by type, records the worst criticality.

**Severity** — ordered scale `low < medium < high < critical`:

```
base = _severity(max_magnitude, propagates)        # unchanged today's rule
if max_magnitude >= MAGNITUDE_MATERIAL and impact.max_criticality is not None:
    severity = max(base, criticality_to_severity(impact.max_criticality))
else:
    severity = base
```

- Severity can only be **raised**, never lowered.
- Escalation is **gated on materiality**: an immaterial change
  (`magnitude < MAGNITUDE_MATERIAL`) stays `low` even under a critical
  consumer, preserving "symptom ≠ incident, false positives stay low."
- `criticality_to_severity`: LOW→low, MEDIUM→medium, HIGH→high, CRITICAL→critical.

## 6. Incident output

- `Incident` gains `business_impact: BusinessImpact | None`.
- `synthesize_incident` computes impact, applies the (possibly escalated)
  severity, stores the impact.
- Summary gains a clause when exposures are affected:
  *"…3 downstream asset(s) affected, reaching 2 dashboards, 1 ML feature,
  1 application (worst: CRITICAL)."*
- `render_business_impact(impact) -> list[str]` renders the grouped block:

  ```
    Business impact:
      Applications (1): pricing_api [CRITICAL] @platform
      ML features (1): ltv_feature [HIGH] @ml-team
      Dashboards (2): exec_dashboard [HIGH] @jane, revenue_daily [MED] @sam
  ```

  Deterministic ordering: types in fixed order
  (application → ml → dashboard → notebook → analysis); within a type by
  (criticality desc, name). Owner shown when present; `url` kept on the object
  but omitted from the terminal view (for the M6 UI).
- Backward compatible: no affected exposures → `business_impact=None`, severity
  and rendering exactly as today.

## 7. Benchmark (proof)

New `src/dvi/benchmark/blast_radius.py`:

```python
def build_blast_radius_cases() -> list[BlastRadiusCase]
def evaluate_blast_radius(cases) -> BlastRadiusReport
```

Each case: a hand-labeled lineage with a changed data asset, a set of exposures,
the ground-truth affected exposure ids, and the expected severity tier.

**Decoys that must NOT fire:**
- exposure downstream of a *sibling* table (outside the blast radius),
- exposure depending on an *ancestor* but not the changed asset,
- a `notebook` (LOW) downstream — affected but must not escalate severity.

**Positives that must fire:**
- high-`maturity` dashboard downstream → severity ≥ high,
- customer-facing `application` (maturity high) downstream → severity **critical**,
- `meta.criticality: critical` override on an otherwise-medium exposure.

**Metrics:** precision & recall of the affected-exposure set (aggregated) and
per-case severity-escalation correctness. **Target: 100% precision & recall,
all severities correct** — the headline M4 number. `scripts/benchmark.py` prints
a new "Blast-radius / business impact" section.

## 8. Files touched

- `src/dvi/lineage/exposure.py` — new: `Exposure`, `Criticality`, `derive_criticality`
- `src/dvi/lineage/graph.py` — parse exposures, `kind`-tagged nodes, two helpers
- `src/dvi/lineage/__init__.py` — export new names
- `src/dvi/incidents/impact.py` — new: `BusinessImpact`, `assess_impact`,
  `criticality_to_severity`, `render_business_impact`
- `src/dvi/incidents/incident.py` — new field + wiring + escalated severity
- `src/dvi/incidents/__init__.py` — exports
- `src/dvi/benchmark/blast_radius.py` — new: labeled cases + evaluation
- `src/dvi/benchmark/__init__.py` — exports
- `scripts/demo.py` — wire exposures, print the impact block
- `scripts/benchmark.py` — print the blast-radius section
- Docs: `docs/architecture.md` (blast-radius section), `README.md` (M4 status +
  roadmap row), `CHANGELOG.md` (M4 section)

## 9. Testing strategy

Strict TDD (RED-GREEN-REFACTOR), matching the repo's style:

- `derive_criticality`: override wins; the `application`+`maturity:high` →
  CRITICAL auto-case; each type/maturity fallback; unknown type → MEDIUM.
- Manifest parsing: exposures become `kind="exposure"` nodes with edges from
  each valid `depends_on` model; dangling refs skipped; no-exposures manifest is
  unchanged.
- Traversal: `exposures_downstream_of` returns only downstream exposures, sorted;
  `data_downstream_of` excludes exposures.
- `assess_impact`: grouping, worst-criticality, empty when nothing external.
- Severity: raised never lowered; materiality gate holds; critical reached via
  both paths.
- Rendering: deterministic order, owners, empty case.
- Benchmark: precision/recall = 1.0 and all severities correct on the labeled
  suite; determinism under alternate `PYTHONHASHSEED` (CI already runs this).

## 10. Out of scope (YAGNI)

- Non-dbt exposure sources / standalone registry file.
- A weighted numeric business-impact score (deferred; the ordered-criticality
  max is enough to escalate severity).
- Rendering `url` / owner routing / paging integrations (M6 UI, later).
- Column-level exposure lineage (exposures depend on models, not columns).
