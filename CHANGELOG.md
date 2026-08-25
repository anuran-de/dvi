# Changelog

All notable changes to DVI are documented here. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Real-data validation + significance guards

Validating the detectors on a real public dataset (the classic **diamonds** set,
53,940 rows) exposed a robustness gap the synthetic suite hid: running two random
halves of the *same* distribution through the share-based detectors false-fired on
nearly every split at small sample sizes. The synthetic "0% false positives" was an
artifact of exact counts and large n. This change closes the gap.

- **detection (significance)** — `significance.noise_threshold`: a share move now
  counts only if it clears the two-proportion sampling noise `Z·√(p(1-p)(1/na+1/nb))`
  (Z=3.0, three-sigma). Wired into `value_substitution` and `category_split_merge`
  as `max(MIN_SHIFT, noise_threshold(...))`. The same share move is noise at small
  n and signal at large n.
- **detection (unit/scale)** — replaced the joint slope+intercept affine fit, which
  turned quantile jitter on a narrow-spread column (a percentage near 61) into a
  bogus "+4 offset", with two independent single-parameter hypotheses: multiplicative
  (spread ratio, through origin) and additive (median shift, slope fixed at 1). A
  no-op scale reads as factor≈1; a no-op shift reads as offset≈0.
- **benchmark (real data)** — `dvi.benchmark.real_data`: `load_diamonds`,
  `two_sample_splits`, `real_vs_real_report`, `injected_recall_report`,
  `evaluate_real_data`. The diamonds parquet is bundled (~0.5 MB) so CI runs offline.
- **result** — at n=1000 across 30 disjoint splits: **0/210 real-vs-real false
  positives** (down from ~100% of splits before the guards) and **100% recall** of a
  planted category rename. Residual false positives appear only at n≤500 (~1% at
  n=250) and vanish by n=1000 — measured, not hidden.

72 tests, all green. CI runs the real-data validation end to end.

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
