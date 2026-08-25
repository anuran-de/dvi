# DVI Architecture

This document describes the intended architecture and records the key design
decisions. It evolves alongside the code; sections marked _(planned)_ are on the
roadmap and not yet implemented.

## 1. Scope and philosophy

DVI is an **intelligence layer**, not a platform. It reuses commodity
infrastructure and builds only the parts that are genuinely novel:

| Concern | Approach |
|---------|----------|
| Metadata / temporal store | Reuse Postgres _(planned)_; SQLite/in-memory for tests |
| Profiling execution | Reuse DuckDB / Polars locally; Snowflake pushdown _(planned, M5)_ |
| Lineage | Reuse dbt `manifest.json` |
| SQL parsing | Reuse `sqlglot` _(as needed)_ |
| Dependency graph | Reuse `networkx` (in-process, no graph DB) |
| **Change detection** | **Built from scratch** |
| **Root-cause ranking** | **Built from scratch** |
| **Blast-radius** | **Built from scratch** _(M4)_ |
| **Incident synthesis** | **Built from scratch** |
| **Benchmark + failure injection** | **Built from scratch** |

## 2. The pipeline (M1 walking skeleton)

```text
Table snapshot (T1)          Table snapshot (T2)
        │                            │
        ▼                            ▼
   Profiler ─────────────────────► Profiler
        │                            │
        └──────────► ColumnProfile ◄─┘
                          │
                          ▼
                 Change detectors            dbt manifest ──► Lineage graph
                 (value substitution, …)                          │
                          │                                        │
                          ▼                                        ▼
                       Symptom ───────────► Corroboration ◄───── Change events
                                              (time × deploy ×
                                               downstream propagation)
                                                    │
                                                    ▼
                                              Root-cause ranking
                                                    │
                                                    ▼
                                              Incident + evidence
```

## 3. Core concepts

- **ColumnProfile** — a point-in-time statistical summary of one column:
  row count, null rate, distinct count, and the top-K value frequencies. This is
  the unit that makes semantic detection possible (value distributions, not just
  structural stats).

- **Change signature** — a deterministic test over two profiles (T1 → T2) that
  recognises a characteristic fingerprint and emits a **Symptom** with a
  magnitude. Signatures never claim to understand meaning; they recognise
  statistical shapes (e.g. mass-conserving value substitution).

- **Symptom vs. Incident** — a fired signature is a *symptom*. It only escalates
  to an *incident* (the thing worth a human's attention) when corroborated by
  temporal clustering, correlation with a change/deploy event, and/or downstream
  propagation. This is the primary false-positive control.

- **Evidence** — every incident carries the observable facts behind it. No
  fabricated confidence numbers; calibrated confidence arrives in M3.

## 4. Module layout

```text
src/dvi/
  profiling/    ColumnProfile + profiler over a Polars/DuckDB relation
  detection/    change signatures (M1: value substitution)
  lineage/      dbt manifest parsing → networkx graph  (M2+)
  rca/          corroboration + root-cause ranking      (M1 thin, M3 calibrated)
  incidents/    incident + evidence synthesis
  benchmark/    synthetic data + failure injection      (M2+)
```

## 5. Decisions log

- **Wedge, not platform.** Ship semantic/behavioral change detection deep; treat
  lineage/profiling/orchestration integration as reused commodity.
- **Deterministic detection; LLM only narrates.** Preserves explainability.
- **A-now / sketch-later data access.** M1 stores real top-K values (synthetic
  data, no privacy issue) to *name* changes in reports; a sketch-only mode is a
  planned drop-in for real deployments.
- **Confidence is measured, not asserted.** Rank + evidence now; calibrated
  logistic confidence with a reliability diagram in M3.
