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

## Design principles

- **Integrate, don't replace.** Reuse dbt's lineage, your warehouse, DuckDB, `sqlglot`. Build only the intelligence layer from scratch.
- **Deterministic first.** Detection and ranking are deterministic and explainable. An LLM, if used at all, only *narrates* evidence — it never decides whether something changed.
- **Evidence before explanation.** Every root-cause claim carries the observable facts that support it.
- **Honest confidence.** No hand-tuned "92%". Confidence is either omitted (rank + evidence) or *calibrated and measured on held-out incidents* (roadmap M3).
- **Symptom ≠ incident.** Corroboration (time × deployment × downstream propagation) is required before anything pages a human — this is how false positives stay low.

## Status

> **M2 — the signature taxonomy + benchmark: complete.** All five flagship signatures are implemented, wired with precedence rules, and measured against a labelled benchmark. On a suite of one clean positive per signature plus normal-variation negatives and benign decoys, DVI hits **100% recall at a 0% false-positive rate** at the shipped operating point, and ranks the true root cause **#1 under concurrent distractor deploys** on every RCA case.
>
> **Validated on real data.** The synthetic suite is not enough on its own — so DVI is now validated against a real public dataset (53,940 rows). Running two disjoint halves of the *same* distribution through the detectors produces **0 false positives at n≥1000**, while a planted semantic change is recovered at **100% recall**. This exposed and fixed a real robustness gap (see [Validated on real data](#validated-on-real-data)). 72 tests, all green.
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

Note what DVI does **not** do: it prints no fabricated "92% confidence". It shows the ranked cause and the observable evidence. Calibrated, *measured* confidence arrives in M3.

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

## Roadmap

DVI is built as a **walking skeleton** — the riskiest, most novel part (does semantic detection + causal ranking actually work?) is proven first; UI and connectors come last.

| Milestone | Adds | Proves |
|-----------|------|--------|
| **M1** ✅ | Value-substitution signature end-to-end on synthetic data | The core hypothesis is alive |
| **M2** ✅ | Signatures 2–5 + negatives/decoys benchmark + real-data validation | Full recall on the suite; **0 false positives on real same-distribution data** |
| **M3** | Calibrated logistic confidence + reliability diagram | Honest, *measured* confidence |
| **M4** | Blast-radius + external-asset lineage (dashboards/ML/APIs) | Business-level impact |
| **M5** | Snowflake pushdown profiling + CLI / GitHub Action PR reports | Real-user adoption path |
| **M6** | Production-grade web UI + incident timeline | Operator experience |

Commodity signatures (null-explosion, cardinality, volume, duplicate-rate, schema/type) are slotted in where cheap.

### Explicitly not built yet
- Automatic BI/ML lineage discovery (Tableau/Looker/feature stores) — downstream assets register via dbt exposures / a generic API until then.
- Warehouses other than Snowflake (DuckDB/Postgres work via the local profiling path).
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
