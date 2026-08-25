# Bundled data

## `diamonds.parquet`

The classic **diamonds** dataset — 53,940 rows describing diamond attributes
(carat, cut, color, clarity, depth, table, price, x, y, z). It originates from
the [ggplot2](https://ggplot2.tidyverse.org/reference/diamonds.html) R package
and is one of the most widely redistributed public sample datasets.

It is checked in (≈0.5 MB) so DVI's **real-data validation** benchmark runs fully
offline and deterministically in CI — no network fetch, no flaky download.

### How it is used

`dvi.benchmark.real_data` runs two experiments against it:

1. **real-vs-real false positives** — two disjoint samples of the *same*
   distribution must produce no symptoms (the honest robustness test).
2. **injected recall** — a known category rename planted into a real sample must
   be recovered under real sampling noise.

Everything is seeded, so results are reproducible run to run.
