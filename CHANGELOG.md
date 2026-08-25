# Changelog

All notable changes to DVI are documented here. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### M1 — Walking skeleton (complete)

The thinnest end-to-end path that proves the core hypothesis: a silent semantic
change is detected, attributed to a deploy, and scoped downstream.

- **profiling** — `ColumnProfile` + `profile_column`: distribution-aware column
  profiles (top-K value frequencies, null rate, cardinality).
- **detection** — `detect_value_substitution`: signature #1, a deterministic,
  mass-conserving test for a category being renamed/replaced.
- **lineage** — `load_dbt_manifest` → `LineageGraph` with upstream/downstream
  traversal (backed by networkx, no graph DB).
- **rca** — `rank_root_causes`: corroborates symptoms against change events and
  lineage; only prior, graph-relevant changes become candidates.
- **incidents** — `synthesize_incident`: evidence-backed incident with severity
  and downstream blast radius; returns `None` when uncorroborated (symptom ≠
  incident). No fabricated confidence numbers.
- **pipeline** — `analyze_change`: two snapshots in, an incident out.
- **benchmark** — synthetic orders generator + value-substitution injector.
- **demo** — `scripts/demo.py`: the "silent rename" scenario, end to end.

24 tests, all green.
