<h1 align="center">DVI — Data Versioning Intelligence</h1>

<p align="center">
  <em>Catch the data incidents that pass every green check.</em>
</p>

<p align="center">
  <a href="https://github.com/anuran-de/dvi/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/anuran-de/dvi/actions/workflows/ci.yml/badge.svg"></a>
  <a href="#status"><img alt="status" src="https://img.shields.io/badge/status-M2%20complete-brightgreen"></a>
  <a href="LICENSE"><img alt="license" src="https://img.shields.io/badge/license-MIT-green"></a>
  <img alt="python" src="https://img.shields.io/badge/python-3.11%2B-blue">
</p>

---

## The problem DVI exists to solve

Data pipelines fail differently from software. A pipeline can **execute successfully, keep its schema, meet its freshness SLA, and pass every null/volume check** — and still make the business number silently wrong.

```sql
-- The whole pipeline stays green. The revenue dashboard is now wrong.
- WHERE status = 'completed'
+ WHERE status = 'COMPLETE'
```

```text
Before                         After
country = "UK"                 country = "United Kingdom"
```

Schema unchanged. Row count unchanged. Freshness normal. Yet downstream logic that expects `"UK"` now under-counts a region, and executive revenue drifts by double digits.

Structural/volumetric observability tools do not catch this class of failure, because **nothing structural changed**. DVI is built specifically for it.

## What DVI does

DVI is a self-hostable intelligence layer that sits **on top of** your existing stack (dbt, your warehouse, Git) — it does not replace them. It:

1. **Profiles** each column over time — including *value distributions*, not just counts.
2. **Detects change signatures** — deterministic tests that recognise the statistical fingerprint of a semantic change (e.g. a dominant category's mass collapsing while a new value absorbs it) without needing to "understand" meaning.
3. **Corroborates** a detected change against deployments/commits and downstream lineage, so an isolated blip stays a *symptom* and only a change that correlates with a deploy and propagates downstream becomes an *incident*.
4. **Ranks likely root causes with evidence** — every claim is backed by observable facts, never a fabricated confidence number.
5. **Names the business-level impact** — dbt exposures downstream of an incident (dashboards, ML features, applications) are named by type, and a business-critical consumer can escalate severity into a new `critical` tier — only for a *material* change, never for an immaterial flicker.

- **Warehouse pushdown profiling** — step 1 can also run **inside the warehouse**: a `SqlDialect` (DuckDB, Snowflake) computes the `ColumnProfile` in SQL and only the compact profile comes back, so profiling a billion-row table moves a handful of aggregates, not the table. See [Warehouse pushdown profiling](docs/warehouse-pushdown.md).
- **Incident history** — detection is stateless by default, but an optional local incident store gives incidents a stable identity so recurrences dedupe and an asset's history is queryable over time. Opt in with a `[store]` section in `dvi.toml`. See [Incident store](docs/incident-store.md).

## Design principles

- **Integrate, don't replace.** Reuse dbt's lineage, your warehouse, DuckDB, `sqlglot`. Build only the intelligence layer from scratch.
- **Deterministic first.** Detection and ranking are deterministic and explainable. An LLM, if used at all, only *narrates* evidence — it never decides whether something changed.
- **Evidence before explanation.** Every root-cause claim carries the observable facts that support it.
- **Honest confidence.** No hand-tuned "92%". Confidence is either omitted (rank + evidence) or *calibrated and measured on held-out data* — a logistic model whose out-of-fold reliability is reported (ECE ≈ 0.05, plus MCE for the worst bin), not asserted.
- **Symptom ≠ incident.** Corroboration (time × deployment × downstream propagation) is required before anything pages a human — this is how false positives stay low.

## Status

**Web UI:** an editorial landing page + operator dashboard, static-exported and
deployed to Vercel ([dvintelligence.vercel.app](https://dvintelligence.vercel.app)).
See [docs/frontend.md](docs/frontend.md) — `cd dvi && npm run dev`.

> **M5b — CLI + GitHub Action: complete.** A `dvi` CLI and a composite GitHub
> Action drive the whole pipeline off a single `dvi.toml`: config → source
> adapter (file or warehouse) → detection/RCA/blast-radius → a severity-gated
> Markdown + JSON report. `dvi analyze` writes `dvi-report.md` / `dvi-report.json`
> and exits `0` (clean/below gate), `1` (gate tripped), or `2` (could not run);
> the Action installs DVI, runs it on a PR, and posts the report as a **sticky**
> comment, failing the check on the CLI's exit code. See [`docs/cli.md`](docs/cli.md).
> **223 tests, all green.**
>
> **M5a — warehouse pushdown profiling: complete.** DVI's semantic detectors now
> consume a `ColumnProfile` computed **in the warehouse via SQL**, not only from
> an in-memory Polars `Series`. A new `dvi.warehouse` package's `SqlDialect`
> (`DuckDBDialect`, `SnowflakeDialect`) emits per-column profiling SQL;
> `SqlProfileSource` runs it through a thin `execute(sql) -> rows` callable — DVI
> never opens a connection itself — and adapts the rows into the same
> `ColumnProfile` the local profiler builds. `analyze_change_from_profiles` is a
> twin of `analyze_change` over a shared `detect_symptoms_from_profiles` core, so
> the pushdown path and the local Polars path run identical detection logic.
> DuckDB is the CI-executed reference; Snowflake's SQL is unit-tested by string
> assertion but not executed in CI (its driver pulls `pyarrow`, which DVI
> deliberately avoids). Parity is **detection-equivalent, proven**:
> `tests/test_pushdown_equivalence.py` runs categorical and numeric cases through
> both engines and asserts decision-identical incidents. **180 tests, all green.**
> See [Warehouse pushdown profiling](docs/warehouse-pushdown.md).
>
> **M4 — blast-radius / business-level impact: complete.** dbt *exposures*
> (dashboards, ML features, applications, notebooks) are now parsed from
> `manifest.json` as typed lineage nodes, so an incident's blast radius extends
> past data assets to the business consumers downstream of them. `assess_impact`
> names the affected consumers by type, and the worst reachable criticality can
> *raise* severity into a new `critical` tier — never lower it, and only for a
> **material** change (an immaterial flicker under a critical dashboard stays
> low). A labeled benchmark of blast-radius cases, with decoys (an immaterial
> critical hit, a material non-critical hit), scores **100% exposure precision,
> 100% exposure recall, and 100% severity accuracy**. **157 tests, all green.**
>
> **M3.1 — hardening pass: complete.** A three-perspective code review (correctness,
> detection robustness, calibration honesty) produced a ranked defect list; every
> finding was fixed in priority order, each with a regression test. Highlights: a
> public-API import cycle closed; non-finite values can no longer fabricate a numeric
> distribution; a sample-size noise floor added to distribution shift; **MCE** now
> reported alongside ECE and the mid-range explicitly declared not calibration-tested;
> and a cluster of determinism/correctness fixes (deterministic `top_k` ties,
> count-weighted pooled proportion, tail-noise-robust case/format). **127 tests, all
> green;** frozen model refit with unchanged quality (ECE ≈ 0.047, MCE ≈ 0.21).
>
> **M3 — calibrated confidence: complete.** Each fired symptom now carries a *measured* probability that it is a real change, from a pure-Python logistic model over three uniform features (magnitude, significance margin, log10 sample size). Calibration is proven, not asserted: on a labelled dataset of real injections, small-`n` hard negatives and synthetic scenarios, the **out-of-fold** (k-fold) reliability gives **ECE ≈ 0.047 / MCE ≈ 0.21 / Brier 0.005**. The coefficients are frozen to JSON and shipped; inference needs no training data.
>
> **M2 — the signature taxonomy + benchmark: complete.** All five flagship signatures are implemented, wired with precedence rules, and measured against a labelled benchmark. On a suite of one clean positive per signature plus normal-variation negatives and benign decoys, DVI hits **100% recall at a 0% false-positive rate** at the shipped operating point, and ranks the true root cause **#1 under concurrent distractor deploys** on every RCA case.
>
> **Validated on real data.** The synthetic suite is not enough on its own — so DVI is now validated against a real public dataset (53,940 rows). Running two disjoint halves of the *same* distribution through the detectors produces **0 false positives at n≥1000**, while a planted semantic change is recovered at **100% recall**. This exposed and fixed a real robustness gap (see [Validated on real data](#validated-on-real-data)). 127 tests, all green.
>
> **M1 — walking skeleton: complete.** The thinnest end-to-end path proving the core hypothesis: profile → temporal snapshots → detector → dbt lineage → corroboration → ranked root cause with evidence, on synthetic data.

See the [roadmap](#roadmap) for what each milestone adds and what is explicitly *not built yet*.

### The signatures (M2)

Each is a deterministic test over two column profiles. More specific signatures suppress more general ones on the same column (e.g. a rigid `x100` re-encoding reports as *unit/scale shift*, not a generic distribution shift).

| # | Signature | Catches |
|---|-----------|---------|
| 1 | Value substitution | A category renamed/replaced (`"UK"` → `"United Kingdom"`) |
| 2 | Case/format normalization | Same categories re-spelled (`"active"` → `"ACTIVE"`, stray whitespace) |
| 3 | Category split/merge | One category fans into many, or many collapse into one |
| 4 | Numeric distribution shift | A behavioral change in shape/location of a numeric column |
| 5 | Unit/scale shift | A rigid re-encoding (dollars → cents, timezone offset) |

## See it work

```bash
python scripts/demo.py
```

A deploy silently renames `"UK"` → `"United Kingdom"`. Every structural check stays green; DVI still catches it, attributes it, and scopes the blast radius:

```text
  Structural checks: schema OK | row_count OK | freshness OK | nulls OK

  DATA INCIDENT
  Severity    : HIGH
  Change at   : 09:14
  Detected at : 09:16
  Confidence  : 95% (calibrated, out-of-fold ECE 0.05)

  Suspected data incident from change 'deploy #482 (country normalization)'.
  Value 'UK' (20.0% of the distribution) appears replaced by 'United Kingdom'
  (20.0%) on model.shop.fact_orders; 3 downstream asset(s) affected.

  Affected downstream assets:
    - model.shop.exec_dashboard
    - model.shop.ml_ltv_feature
    - model.shop.revenue_daily

  Evidence:
    * Change 'deploy #482 ...' was deployed 2 min before the first symptom.
    * 'deploy #482 ...' directly changed model.shop.fact_orders, where DVI
      observed: Value 'UK' (20.0%) appears replaced by 'United Kingdom' (20.0%).
    * No corresponding change was observed upstream of the targeted asset(s).
```

Note what DVI does **not** do: it prints no fabricated "92% confidence". The confidence it *does* show is a calibrated probability from a logistic model, whose out-of-fold reliability (ECE ≈ 0.05) is reported alongside — the number means what it says, and drops on weaker evidence.

### The benchmark

```bash
python scripts/benchmark.py
```

Anyone can build positives their own detector catches — the credibility comes from the **decoys**: legitimate changes that superficially look like incidents and must stay silent (a 2× jump in volume, a new market appearing at 1.5% share, sub-threshold numeric drift). The runner scores recall and false-positive rate, then sweeps the one continuous knob (the distribution-shift threshold) to trace the operating curve:

```text
  At the shipped default threshold (0.10):
    recall              : 100%
    false-positive rate : 0%

  Operating curve (distribution-shift threshold sweep):
     threshold   recall  fp_rate   false positives
          0.01     100%      43%   3 numeric decoys/negatives fire
          0.07     100%      14%   1 numeric decoy fires
          0.08     100%       0%   -
          0.43      80%       0%   distribution-shift positive missed
```

The safe band `[0.08, 0.43)` gives full recall at zero false positives; push the threshold too low and benign numeric drift becomes noise, too high and real shifts slip through. That trade-off is *measured*, not asserted.

The same runner scores **root-cause ranking under concurrency**: given a symptom and several near-simultaneous deploys, it checks the true cause ranks #1. Irrelevant deploys (no lineage path) and post-symptom changes are excluded outright; among genuine upstream candidates the closer-in-time / higher-coverage one wins. Top-1 accuracy is 100% across the RCA cases.

### Validated on real data

A synthetic benchmark can flatter its own detector. The real test of a change detector is the opposite of recall: **when nothing changed, does it stay silent?** So DVI is validated against a real public dataset — the classic [diamonds](data/README.md) set, 53,940 rows, bundled so the check runs offline in CI.

The experiment: split the data into two **disjoint samples of the same distribution** and run every detector. Nothing changed between them, so every symptom is a false positive.

This is where the honest story is. The *first* run of that experiment false-fired on nearly every split — the synthetic "0% false positives" was an artifact of exact counts and huge sample sizes. A share moving 3 points is a real event at 250k rows and pure sampling noise at 250. The fix is a **sample-size-aware significance guard**: a share move counts only if it clears the sampling noise `Z·√(p(1-p)(1/n_a+1/n_b))` (Z=3, three-sigma). A parallel fix stabilised the unit/scale detector, which was turning quantile jitter on a narrow-spread column into a phantom offset.

```text
  Validation on real data (diamonds, 53,940 rows)
  Real-vs-real false positives: 0/210 column-checks fire (0%) across 30 disjoint splits
  Injected-rename recall       : 30/30 (100%) - a planted category rename recovered under real noise
```

Two disjoint samples of the same distribution stay **silent**; a real injected change is still **caught**. Residual false positives exist only at very small samples (~1% at n=250) and vanish by n=1000 — and that trade-off is measured, not hidden.

### Calibrated confidence (M3)

A detector firing is one thing; *how sure* should you be it's real? DVI attaches a **calibrated probability** to every fired symptom — the measured chance it is a genuine change rather than sampling noise. The point of "calibrated" is literal: when the model says 0.7, about 70% of such symptoms are real, and we prove it on held-out data instead of hand-tuning a number.

The model is a small pure-Python logistic regression (no numpy/sklearn in the stack) over three uniform features: the detector's `magnitude`, a `significance_margin` (effect size in multiples of its noise/threshold floor), and `log10` of the sample size. (A fourth `coverage` feature was dropped in M3.1 — it was a dead constant on the calibration set, since every fired categorical symptom already clears the detectors' coverage guard.) It is trained on a labelled dataset that deliberately spans the hard regime — real category renames injected into diamonds samples across a grid of size and rename fraction (the *borderline* positives), plus **small-`n` real-vs-real splits** where noise occasionally slips past the guards (the hard negatives), plus the synthetic scenarios for multi-signature coverage.

Honesty comes from **k-fold cross-validation**: every row is scored by a model that never trained on it, and those out-of-fold predictions produce the reliability table below. The shipped model is then refit on all the data and its coefficients frozen to JSON, so inference needs no training data.

```text
  Calibrated confidence (per-symptom, k-fold cross-validated)
  Dataset: 58 fired symptoms, 34 real (59% positive)
  Out-of-fold ECE: 0.0466   MCE: 0.2165   Brier: 0.0051
  (ECE is count-weighted, dominated by the extremes; MCE is the worst bin.
   1 of 58 predictions land in [0.2, 0.8] — the mid-range is not calibration-tested.)
```

Confidence is conditional on firing, so predictions skew to the extremes — most fired symptoms are clearly real or clearly noise — and the reliability table prints per-bin counts so the sparse middle stays visible rather than hidden by a smooth curve. Run `python scripts/benchmark.py` for the full table.

## Roadmap

DVI is built as a **walking skeleton** — the riskiest, most novel part (does semantic detection + causal ranking actually work?) is proven first; UI and connectors come last.

| Milestone | Adds | Proves |
|-----------|------|--------|
| **M1** ✅ | Value-substitution signature end-to-end on synthetic data | The core hypothesis is alive |
| **M2** ✅ | Signatures 2–5 + negatives/decoys benchmark + real-data validation | Full recall on the suite; **0 false positives on real same-distribution data** |
| **M3** ✅ | Calibrated logistic confidence + out-of-fold reliability table | Honest, *measured* confidence (ECE ≈ 0.05, MCE ≈ 0.21) |
| **M3.1** ✅ | Review-driven hardening: import-cycle, non-finite, noise floors, MCE, determinism | Correctness & honesty under scrutiny; 127 tests |
| **M4** ✅ | Blast-radius + external-asset lineage (dashboards/ML/APIs) | Business-level impact |
| **M5a** ✅ | Warehouse pushdown profiling (DuckDB executed, Snowflake dialect + SQL-gen tests) + `analyze_change_from_profiles`, cross-engine detection-equivalence | Pushdown path is detection-equivalent to local profiling |
| **M5b** ✅ | CLI (`dvi analyze`) + composite GitHub Action posting sticky PR reports, severity-gated | Real-user adoption path |
| **M6** ✅ | Editorial landing page + operator UI (dashboard, incident timeline, blast-radius graph), static-exported | Operator experience |

Commodity signatures (null-explosion, cardinality, volume, duplicate-rate, schema/type) are slotted in where cheap.

### Explicitly not built yet
- Automatic BI/ML lineage discovery (Tableau/Looker/feature stores) — downstream assets register via dbt exposures / a generic API until then.
- Warehouses beyond DuckDB (executed in CI) and Snowflake (dialect + SQL-gen tests, not CI-executed) — another warehouse needs a new `SqlDialect`, not a new profiling path.
- Auto-derived change events — `[[changes]]` is declared explicitly in `dvi.toml`; DVI does not yet infer changes from commit/deploy history.
- Multi-asset runs — one `dvi analyze` run covers one asset; scanning a whole project needs one config per asset.
- Forges beyond GitHub — the composite Action posts via the runner's `gh` CLI; GitLab/Bitbucket equivalents are not built.
- Any autonomous remediation.

## Getting started

Requires Python 3.11+.

```bash
python -m venv .venv
source .venv/Scripts/activate   # Windows (Git Bash);  use source .venv/bin/activate on macOS/Linux
pip install -e ".[dev]"
pytest
```

## License

MIT — see [LICENSE](LICENSE).
