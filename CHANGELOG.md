# Changelog

All notable changes to DVI are documented here. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### M2 — Signature taxonomy + benchmark (complete)

The full flagship signature set, plus a labelled benchmark that measures recall
against a false-positive budget.

- **detection** — four new deterministic signatures:
  - `detect_case_format_normalization` (#2): categories re-spelled (casefold +
    whitespace) with the normalized set and masses preserved.
  - `detect_category_split_merge` (#3): one-to-many / many-to-one mass
    redistribution with conserved total mass.
  - `detect_numeric_distribution_shift` (#4): behavioral change in a numeric
    column, measured as normalized quantile movement (tunable threshold).
  - `detect_unit_scale_shift` (#5): rigid affine re-encoding (dollars → cents,
    timezone offset), fitted from robust quantile anchors.
- **pipeline** — detector registry with **precedence**: a more specific
  signature suppresses a more general one on the same column (#5 over #4,
  #2 over #1). Distribution-shift threshold is tunable through `detect_symptoms`.
- **benchmark** — `build_scenarios`: a labelled suite of 5 positives (one per
  signature), 3 normal-variation negatives, and 4 benign decoys (2× volume, a
  new small category, sub-threshold numeric drift). `evaluate` /
  `recall_at_fixed_fp` / `sweep` score recall and false-positive rate and trace
  the operating curve.
- **benchmark (RCA)** — `build_rca_cases` + `evaluate_rca`: labelled root-cause
  cases with concurrent distractor deploys (irrelevant, post-symptom, and weaker
  upstream competitors). Measures top-1 ranking accuracy.
- **demo** — `scripts/benchmark.py`: prints the detection report, operating
  curve, and RCA top-1 accuracy.
- **result** — 100% recall at 0% false positives at the shipped operating point
  (FPs appear below t=0.08, distribution-shift positive missed at t≥0.43); 100%
  top-1 root-cause accuracy under distractors.

60 tests, all green. CI now also runs the benchmark end to end.

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

### Hardening

- **detection** — deterministic lexicographic tie-break for drop/gain matching
  (results no longer depend on set/hash iteration order); high-cardinality guard
  that skips columns whose top_k covers <90% of non-null rows.
- **CI** — GitHub Actions across Python 3.11/3.12: ruff lint, pytest, a
  second test pass under an alternate `PYTHONHASHSEED` (determinism guard), and
  a job that runs the demo end to end. 26 tests.
