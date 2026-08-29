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
| Profiling execution | Reuse DuckDB / Polars locally; DuckDB / Snowflake pushdown via SQL (M5a) |
| Lineage | Reuse dbt `manifest.json` |
| SQL parsing | Reuse `sqlglot` _(as needed)_ |
| Dependency graph | Reuse `networkx` (in-process, no graph DB) |
| **Change detection** | **Built from scratch** |
| **Root-cause ranking** | **Built from scratch** |
| **Blast-radius** | **Built from scratch** |
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
  calibration/  per-symptom confidence: features, logistic model, reliability, frozen JSON
  lineage/      dbt manifest parsing → networkx graph
  rca/          corroboration + root-cause ranking
  incidents/    incident + evidence synthesis (surfaces calibrated confidence)
  pipeline/     detector registry + precedence; analyze_change orchestration
  benchmark/    synthetic scenarios, evaluation runner, real-data validation
  warehouse/    SqlDialect (DuckDB/Snowflake) + SqlProfileSource: in-warehouse profiling
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

## 7. Calibrated confidence (M3)

The detectors are deterministic and decide *whether* a symptom fires. The
`calibration/` layer adds *how confident* we are it is real — a probability that
means what it says. It is deliberately kept separate: detection semantics never
depend on the model, and passing no model reproduces exact M1/M2 behavior.

**Feature vector** (`features.extract_features`) — three uniform features per
fired symptom: `magnitude` (the detector's effect size), `significance_margin`
(that effect in multiples of its noise/threshold floor; the only feature that
branches by signature — share noise for categorical, the shift threshold for
numeric, the fit tolerance for unit/scale), and `log10(min(na, nb))`. Features are
standardized inside the model. (A `coverage` feature was removed in M3.1: every
fired categorical symptom already clears the detectors' `MIN_TOP_K_COVERAGE`
guard, so it was a constant 1.0 with zero variance and a trained weight of exactly
0 — a dead input. Dropping it left every prediction unchanged.)

**Model** (`model.LogisticModel`) — a from-scratch logistic regression, because
numpy/scipy/sklearn are not in the stack. Deterministic batch gradient descent
(zero init, fixed iterations, no shuffling) with L2 that shrinks weights but not
the intercept, so a fit is reproducible and freezable.

**Dataset** (`dataset.build_calibration_dataset`) — the calibration data has to
cover the *hard* regime, or the reliability curve only sees easy extremes. So it
mixes real category renames injected across a size×fraction grid (borderline
positives), **small-`n` real-vs-real splits** where noise leaks past the guards
(hard negatives), and the synthetic scenarios (numeric/unit positives the
categorical grid can't provide). Everything is seeded and derived from profiles.

**Honesty** (`reliability`) — calibration quality is measured on **out-of-fold**
predictions via k-fold CV (`index % k`): each row is scored by a model that never
trained on it. From those pooled `(prob, label)` pairs we build an equal-width
reliability table (per-bin count, mean predicted, empirical frequency), the
Expected Calibration Error, the **Maximum Calibration Error**, and the Brier
score. No plotting library is available, so the "diagram" is a markdown table with
visible per-bin counts.

Because confidence is *conditional on firing*, this is a near-separable problem:
almost all predictions land in the extreme bins (obvious real change vs obvious
noise), and the intermediate `[0.2, 0.8]` band is sparsely populated. The
count-weighted **ECE (≈0.047)** is therefore dominated by those well-separated
extremes — it certifies the model *ranks* real above noise, not that a "0.5" means
50%. We report **MCE (≈0.21)**, the worst single populated-bin gap, precisely so
the low ECE is not mistaken for calibrated mid-range confidence, and the frozen
test asserts the middle stays under-populated rather than claiming it is
calibrated. **Brier 0.005.** Honest framing: *strong separation of real vs noise;
intermediate probabilities are not calibration-tested.*

**Freezing** (`loader`) — the shipped model is refit on all the data and frozen to
`coefficients.json` (weights, intercept, feature scaling, feature order, and the
measured k-fold ECE/Brier as metadata), loaded via `importlib.resources`.
Inference needs no training data. A regression test re-fits from the seeded
generators and asserts the coefficients match and held-out ECE/Brier stay within
bounds — a de-calibrating change fails CI.

**Wiring** — `Symptom.confidence` defaults to `None`; `detect_symptoms` and
`analyze_change` take an optional `model=`; when supplied, each surviving symptom
is scored (`score.attach_confidence`) and `Incident.confidence` surfaces the
primary symptom's probability. Confidence is *conditional on firing*, so scores
skew to the extremes and production `n` pushes real confidences high.

## 8. Business-level impact (M4)

A data incident matters in proportion to who it reaches. dbt **exposures**
(dashboards, ML features/models, applications, notebooks, analyses) are parsed
from `manifest.json` as typed lineage nodes alongside models — a `kind`-tagged
graph with `model → exposure` edges — so blast radius is computed the same way
as any other downstream traversal (`exposures_downstream_of`), no separate
integration required.

Each exposure carries a `Criticality` (`derive_criticality`: an explicit
`meta.criticality` override, else customer-facing/high-maturity applications
are CRITICAL, then per-type defaults). `assess_impact` (`incidents/impact.py`)
projects an incident's affected assets onto reachable exposures and groups them
by type; `render_business_impact` prints them in a fixed order (applications,
ML features, dashboards, notebooks, analyses) so the operator sees who is hit
without hunting through a raw list.

The worst reachable criticality can **raise** incident severity — never lower
it — via `escalate_severity`, and only when the change is **material**
(`max_magnitude >= MAGNITUDE_MATERIAL`): an immaterial flicker under a
business-critical dashboard stays low severity, and a large change under a
critical consumer can escalate all the way to a new `critical` tier above
`high`. `Incident.business_impact` surfaces the assessment (`None` when no
exposures are reached) and the summary clause names the affected consumers.

## 9. Warehouse pushdown (M5a)

Every detector consumes a `ColumnProfile`, never raw rows — so profiling does
not have to happen in-process. `dvi.warehouse` computes the *same*
`ColumnProfile` by pushing the aggregation down into the warehouse as SQL and
pulling back only the compact result.

**Dialect** (`warehouse/dialect.py`) — `SqlDialect` is the abstract seam: four
methods that render base counts (row count, null count, distinct count),
numeric aggregates (quantiles, stddev, a finite-only exclusion predicate), and
top-K categorical frequencies as SQL for one column against one table.
`DuckDBDialect` and `SnowflakeDialect` are its two implementations — same
shape, warehouse-flavored SQL (e.g. Snowflake's `PERCENTILE_CONT ... WITHIN
GROUP` vs DuckDB's quantile functions).

**Executor contract** (`warehouse/sql_source.py`) — `SqlProfileSource(execute,
table, *, dialect, top_k)` never opens a connection itself. `execute` is a thin
`Callable[[str], Iterable[Sequence]]` — the DBAPI `fetchall()` shape — so the
caller owns the connection, auth, and lifecycle; DVI only builds SQL (via the
dialect) and adapts the returned rows into `ColumnProfile`. This keeps
`dvi.warehouse` free of any driver dependency: DuckDB is exercised directly in
tests/CI, while Snowflake's SQL is verified by string assertion only (its
driver pulls `pyarrow`, which DVI avoids everywhere else).

**Shared detection seam** (`pipeline`) — `analyze_change_from_profiles` is a
twin of `analyze_change` that takes profile dicts directly instead of raw
column data, built over a `detect_symptoms_from_profiles` core shared with the
local Polars path. Same profiles in, same detector registry, same precedence
rules — the two producers (`profiling.profiler`, `warehouse.SqlProfileSource`)
are interchangeable from the pipeline's point of view.

**Detection-equivalence, not bit-identity** — the bar for the pushdown path is
that it reaches the **same decisions** as the local path on the same data, not
that every float matches to the last digit (SQL and Polars aggregate in
different orders). `tests/test_pushdown_equivalence.py` runs categorical and
numeric change scenarios through both DuckDB and Polars and asserts the fired
incidents are decision-identical.

## 10. CLI + GitHub Action (M5b)

`dvi.cli` is a **thin orchestration layer**, not a new detection path: it wires
config → source adapter → pipeline → render → exit code, and delegates every
decision about *whether* something changed to the existing pipeline. No
detection, corroboration, or ranking logic lives in the CLI.

**Config** (`cli/config.py`) — `DviConfig` (pydantic, loaded from `dvi.toml`
via `tomllib`) models one asset, an optional column subset, a `[source]`
(`FileSourceConfig` or `WarehouseSourceConfig`, discriminated by `kind`), a
`[lineage]` manifest path, one or more `[[changes]]` (explicit `ChangeConfig`
entries — DVI does not infer changes from commit/deploy history), and a
`[gate]` (`fail_on` severity, `model` on by default). A malformed or
incomplete config raises `DviError`.

**Sources** (`cli/sources.py`) — `incident_from_config(config)` dispatches on
`config.source.kind` to one of two adapters — a file adapter (polars over
`.parquet`/`.csv`/`.ndjson`) or a warehouse adapter (a read-only DuckDB
connection feeding `SqlProfileSource`, the M5a pushdown seam) — and both
**converge on the same `Incident | None`** result. The CLI, the renderer, and
the gate never know which adapter ran; adding a new source means adding a new
adapter behind this same seam, not touching orchestration.

**Gate + exit codes** (`cli/gate.py`, `cli/main.py`) — `gate_failed(severity,
fail_on)` compares the incident's severity against the configured threshold;
`dvi analyze` translates the outcome into the process exit code: `0` (no
incident, or below `fail_on`), `1` (gate tripped), `2` (a `DviError` —
could not run at all). Render (`cli/render.py`) writes `dvi-report.md` /
`dvi-report.json` and echoes the Markdown before the process exits.

**GitHub Action** (`action.yml`) — a composite action that is itself a **thin
wrapper**: it installs DVI, runs `dvi analyze`, and gates the check on the
CLI's exit code. Its own contribution is posting the rendered Markdown as a
**sticky** pull-request comment — found and updated in place via a hidden
`<!-- dvi-report -->` marker, through the runner's `gh` CLI — so no incident
detection, severity logic, or state lives in the Action; all of it is the
CLI's exit code and report.

## 5. Decisions log

- **Wedge, not platform.** Ship semantic/behavioral change detection deep; treat
  lineage/profiling/orchestration integration as reused commodity.
- **Deterministic detection; LLM only narrates.** Preserves explainability.
- **A-now / sketch-later data access.** M1 stores real top-K values (synthetic
  data, no privacy issue) to *name* changes in reports; a sketch-only mode is a
  planned drop-in for real deployments.
- **Confidence is measured, not asserted.** A per-symptom logistic model whose
  out-of-fold reliability (ECE/Brier) is reported, not a hand-tuned percentage.
  Calibration lives in a separate layer so detection stays deterministic and
  passing no model reproduces exact M1/M2 behavior.
- **Calibrate on the hard regime.** The labelled dataset over-samples borderline
  cases (small-`n` renames, noise that leaks past the guards) on purpose — a
  reliability curve built only from easy extremes proves nothing.
