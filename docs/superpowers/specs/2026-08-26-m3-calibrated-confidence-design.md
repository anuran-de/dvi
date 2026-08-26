# M3 — Calibrated confidence (design)

**Date:** 2026-08-26
**Milestone:** M3 — "Honest, *measured* confidence."
**Status:** approved, in implementation.

## Goal

Attach a **calibrated probability** to each fired symptom: *the measured
probability that this symptom is a real change rather than a false positive*.
"Calibrated" is the whole point — when the model says 0.7, ~70% of such symptoms
are real, proven on held-out data with a reliability diagram. No hand-tuned "92%".

## Decisions (from brainstorming)

1. **Prediction unit — per-symptom.** Confidence is conditional on a symptom
   firing. The deterministic detectors are unchanged; they decide *whether* a
   symptom fires. The calibration layer only adds *how confident* we are it is
   real. This is exactly what the operator sees.
2. **Calibration data — real-data grid + synthetic.** Positives from injected
   renames into real diamonds samples across a grid of sample size `n` and
   injected share (so some are borderline); negatives from real-vs-real splits;
   plus the M2 synthetic scenarios for multi-signature coverage. Seeded.
3. **Honesty — k-fold cross-validation.** The reliability diagram, ECE and Brier
   score are computed from pooled **out-of-fold** predictions. The shipped model
   is then refit on all the data (standard CV practice).
4. **Features — minimal uniform 4.** `magnitude`, `significance_margin`,
   `coverage`, `log10(sample_size)`. One global model, one reliability curve.
5. **Persistence — freeze coefficients to JSON.** Fit deterministically, freeze
   intercept + 4 weights + feature scaling into a versioned JSON shipped in the
   package. Inference needs no training data. A test re-fits and asserts the
   frozen coefficients still match and held-out ECE/Brier stay within bounds.

Environment-forced (not choices): **pure-Python logistic regression** (no
numpy/scipy/sklearn) and a **text/markdown reliability table** (no matplotlib).

## Semantics: conditional on firing

The model's domain is *fired symptoms*. Intermediate confidences arise only in
the hard regime where small real injections and small-`n` sampling-noise false
positives look alike. So the calibration grid **deliberately includes a small-`n`
regime** to populate the low/middle probability bins, and the reliability report
**prints per-bin counts** so sparse bins are visible, not hidden. We are explicit
that production `n` is typically larger, so real confidences skew high.

## Features

`extract_features(symptom, baseline, current) -> FeatureVector`. Three features
are uniform; only `significance_margin` branches by signature.

| Feature | Definition |
|---------|------------|
| `magnitude` | `symptom.magnitude` (0–1), the detector's effect size. |
| `significance_margin` | Effect size in multiples of its noise/threshold floor. Categorical (#1,#2,#3): `min(lost,gained) / noise_threshold(p_pooled, na, nb)`. Numeric shift (#4): `stat / threshold`. Unit/scale (#5): `fit_magnitude / tolerance`. Clipped to a sane cap. |
| `coverage` | `min(baseline, current)` top_k coverage for categorical; `1.0` for numeric (coverage not meaningful there). |
| `log10_n` | `log10(min(na, nb))`, non-null counts. |

Features are standardized (mean/std frozen from the training set) before the
logistic link, for stable gradient descent.

## Logistic model (`calibration/model.py`)

Pure-Python `LogisticModel`:
- `fit(X, y, *, l2, lr, iters)` — batch gradient descent on the mean logistic
  loss with L2 regularization; deterministic (fixed init at 0, fixed iteration
  count, no shuffling). Standardizes X internally, stores `mean`/`std`.
- `predict_proba(X) -> list[float]` — sigmoid of the linear score.
- `to_dict()` / `from_dict()` — JSON round-trip (weights, intercept, scaling,
  feature order, a `version`).
- No external deps; operates on lists of lists / lists of floats.

## Calibration dataset (`calibration/dataset.py`)

`build_calibration_dataset(seed, grid) -> list[LabeledSymptom]` where a
`LabeledSymptom` bundles `(features, label, signature)`.

- **Positives:** for each `(column, from_value, n, fraction, seed)` in the grid,
  draw a real diamonds sample, inject a partial/full rename, run the matching
  detector; if it fires, record `features` with `label=1`. Grid spans small→large
  `n` and small→large `fraction` to cover borderline cases.
- **Negatives:** real-vs-real disjoint splits across columns and small `n`; every
  fired symptom is `label=0` (nothing changed). This is the hard-negative source.
- **Synthetic:** the M2 `build_scenarios()` positives/negatives/decoys, run
  through the detectors; fired → labeled by ground truth, for multi-signature
  coverage.

Reuses `benchmark.real_data` and `benchmark.scenarios`. Fully seeded.

## Reliability (`calibration/reliability.py`)

- `k_fold_predictions(dataset, k, seed) -> list[(prob, label)]` — deterministic
  fold assignment (index % k), fit on the other folds, predict the held-out fold,
  pool.
- `reliability_table(pairs, bins) -> ReliabilityReport` — equal-width bins over
  [0,1]; per bin: count, mean predicted prob, empirical frequency.
- `expected_calibration_error(...)`, `brier_score(...)`.
- `render_reliability(report) -> str` — a markdown/ASCII table (bin, n,
  predicted, empirical, gap). No plotting.

## Freezing (`calibration/coefficients.json` + `calibration/loader.py`)

- A script/test fits the final model on the full dataset and writes
  `coefficients.json` (weights, scaling, feature order, version, and the measured
  held-out ECE/Brier as metadata).
- `load_model()` reads the shipped JSON (via `importlib.resources`).
- Regression test: re-fit from seeded generators, assert coefficients match the
  frozen JSON within tolerance and held-out ECE ≤ a bound, Brier ≤ a bound.

## Inference wiring

- Add `confidence: float | None = None` to `Symptom` (default `None` keeps M1/M2
  behavior and tests intact).
- `calibration/score.py`: `score_symptom(symptom, baseline, current, model) ->
  float`; `attach_confidence(...)` returns a copy with `confidence` set.
- Pipeline (`analyze.py` / `detect_symptoms`): optional `model` param; when
  provided, populate `confidence` on each returned symptom. Default off → no
  behavior change.
- `Incident`: surface the primary symptom's confidence as `Incident.confidence`
  when present. The demo keeps printing rank + evidence, now **plus** a measured
  confidence line when a model is loaded.

## Benchmark / CLI / CI

- `scripts/benchmark.py` gains a **Calibration** section: dataset size, positive
  rate, k-fold ECE, Brier, and the rendered reliability table.
- CI already runs pytest + the benchmark; the calibration section runs there too.

## Testing plan (TDD, unit by unit)

1. `LogisticModel` — recovers a known separable boundary; predicts monotone in
   score; JSON round-trip is exact.
2. `extract_features` — correct margins per signature; numeric coverage = 1.0;
   monotonicities (bigger effect → bigger margin).
3. `build_calibration_dataset` — deterministic; contains both labels; positive
   rate in a sane band; only fired symptoms included.
4. `reliability` — ECE/Brier match hand-computed values on a tiny fixture;
   k-fold folds are disjoint and cover all rows; a perfectly-calibrated synthetic
   set yields ECE ≈ 0.
5. Frozen model — coefficients match re-fit; held-out ECE/Brier within bounds.
6. Wiring — `detect_symptoms(..., model=m)` sets `confidence`; default leaves it
   `None`; higher-margin symptom gets higher confidence than a borderline one.

## Out of scope (YAGNI for M3)

Signature one-hot features / per-signature models; incident-level corroboration
confidence; any plotted (non-text) diagram; online/continuous retraining.
