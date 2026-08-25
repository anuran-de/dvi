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
  statistical shapes (e.g. mass-conserving value substitution). The five flagship
  signatures (M2):

  | # | Signature | Fingerprint |
  |---|-----------|-------------|
  | 1 | Value substitution | One category's mass collapses; a new value absorbs it (masses conserved) |
  | 2 | Case/format normalization | Categories re-spelled; normalized (casefold + whitespace) set and masses preserved |
  | 3 | Category split/merge | One-to-many / many-to-one redistribution with conserved total mass |
  | 4 | Numeric distribution shift | Normalized quantile movement beyond a tunable threshold |
  | 5 | Unit/scale shift | Every quantile lands on one fitted affine line (rigid re-encoding) |

- **Signature precedence** — a more specific signature suppresses a more general
  one when both fire on the same column, so an incident is described by its most
  precise cause. #5 (unit/scale) suppresses #4 (distribution shift); #2
  (re-spelling) suppresses #1 (substitution). Encoded in the pipeline registry.

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
  detection/    change signatures #1-5 + Symptom + significance guard
  lineage/      dbt manifest parsing → networkx graph
  rca/          corroboration + root-cause ranking      (M1 thin, M3 calibrated)
  incidents/    incident + evidence synthesis
  pipeline/     detector registry + precedence; analyze_change orchestration
  benchmark/    synthetic scenarios, evaluation runner, real-data validation
```

## 6. Benchmark and operating point

The benchmark (`dvi.benchmark`) is the credibility instrument. Its honesty comes
from the **decoys** — legitimate changes engineered to superficially resemble an
incident yet must stay silent (a 2× volume jump with identical shares, a new
category at sub-threshold share, sub-threshold numeric drift) — alongside one
clean positive per signature and normal-variation negatives.

`evaluate` scores **recall** (positives caught with the correct signature) and
**false-positive rate** (negatives/decoys that fired). `sweep` / `recall_at_fixed_fp`
vary the one continuous knob, the distribution-shift threshold, to trace the
operating curve and pick a robust point (the middle of the zero-FP band). At the
shipped default the detectors reach 100% recall at 0% false positives; the curve
makes the trade-off — noise below t≈0.08, missed shifts above t≈0.43 — explicit
and measured rather than asserted. The categorical signatures are effectively
fixed; only the numeric detector is threshold-tunable in v1.

### 6.1 Real-data validation and the significance guard

A synthetic suite can flatter its own detector, so `dvi.benchmark.real_data`
validates against a real public dataset (diamonds, 53,940 rows, bundled for
offline CI). The decisive experiment is the inverse of recall: split the data into
two **disjoint samples of the same distribution** and confirm no detector fires —
every symptom there is a false positive.

The first run failed loudly, and that failure shaped the design. The share-based
signatures used a flat share-shift floor (`MIN_SHIFT`), which cannot tell a real
relocation from sampling noise: a 3-point move is signal at 250k rows and noise at
250. The synthetic "0% false positives" was an artifact of exact counts and large
n. The fix is a **sample-size-aware significance guard** (`detection.significance`):
a share move counts only if it clears `Z·√(p(1-p)(1/n_a+1/n_b))`, the two-proportion
sampling error, with `Z=3` (three-sigma). The per-value floor becomes
`max(MIN_SHIFT, noise_threshold(...))`. A parallel fix replaced the unit/scale
detector's joint slope+intercept fit — unstable on a narrow-spread column far from
zero — with two independent single-parameter hypotheses (multiplicative through the
origin; additive with slope fixed at 1).

Result: at n=1000 across 30 disjoint splits, **0 real-vs-real false positives**
(down from ~100% of splits) and **100% recall** of a planted category rename.
Residual false positives survive only at n≤500 and vanish by n=1000 — measured,
not hidden.

## 5. Decisions log

- **Wedge, not platform.** Ship semantic/behavioral change detection deep; treat
  lineage/profiling/orchestration integration as reused commodity.
- **Deterministic detection; LLM only narrates.** Preserves explainability.
- **A-now / sketch-later data access.** M1 stores real top-K values (synthetic
  data, no privacy issue) to *name* changes in reports; a sketch-only mode is a
  planned drop-in for real deployments.
- **Confidence is measured, not asserted.** Rank + evidence now; calibrated
  logistic confidence with a reliability diagram in M3.
