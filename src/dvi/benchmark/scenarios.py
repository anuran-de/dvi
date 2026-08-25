"""The labelled benchmark suite.

A benchmark is only as honest as its negatives. Anyone can build positives that
their own detector catches; the credibility comes from the *decoys* — legitimate
changes that superficially resemble an incident (a doubling in volume, a brand-new
category, a sub-threshold numeric wiggle) and must NOT fire — and the *negatives*
(normal sampling noise). This module ships a labelled suite spanning:

  * positives   — one clean injection per signature (#1..#5)
  * negatives   — normal variation that must stay silent
  * decoys      — real but benign changes that must stay silent

The evaluation runner (``dvi.benchmark.evaluate``) scores detectors against these
labels to produce recall, false-positive rate, and a recall-at-fixed-FP operating
point. Magnitudes are chosen to sit clearly on the intended side of the default
operating point, so a regression that widens or narrows a guard shows up as a
metric change rather than a silent drift.
"""

from __future__ import annotations

from dataclasses import dataclass

import polars as pl

from .synthetic import categorical, numeric, ramp

_COUNTRY = {"US": 400, "UK": 200, "DE": 200, "FR": 200}
_STATUS = {"active": 600, "pending": 250, "closed": 150}
_CATEGORY = {"Electronics": 500, "Books": 300, "Toys": 200}


@dataclass(frozen=True)
class Scenario:
    """One labelled before/after pair.

    ``kind`` is ``"positive"``, ``"negative"`` or ``"decoy"``. For positives,
    ``signature`` and ``column`` name the change that *should* be detected; for
    negatives/decoys they are ``None`` and any fired symptom is a false positive.
    """

    name: str
    kind: str
    before: pl.DataFrame
    after: pl.DataFrame
    columns: list[str]
    signature: str | None = None
    column: str | None = None
    note: str = ""

    @property
    def is_positive(self) -> bool:
        return self.kind == "positive"


def _stretch_above(values: list[float], pivot: float, factor: float) -> list[float]:
    """Multiply only the values above ``pivot`` — a non-affine shape change."""
    return [v * factor if v > pivot else v for v in values]


def build_scenarios(seed: int = 0) -> list[Scenario]:
    """Return the full labelled benchmark suite."""
    amounts = ramp(1000)
    scenarios: list[Scenario] = []

    # ---- Positives: one clean injection per signature -----------------------
    scenarios.append(
        Scenario(
            "pos:value_substitution",
            "positive",
            categorical("country", _COUNTRY, seed),
            categorical(
                "country",
                {"US": 400, "United Kingdom": 200, "DE": 200, "FR": 200},
                seed,
            ),
            ["country"],
            signature="value_substitution",
            column="country",
            note="UK silently renamed to United Kingdom",
        )
    )
    scenarios.append(
        Scenario(
            "pos:case_format",
            "positive",
            categorical("status", _STATUS, seed),
            categorical("status", {"ACTIVE": 600, "PENDING": 250, "CLOSED": 150}, seed),
            ["status"],
            signature="case_format_normalization",
            column="status",
            note="status values upper-cased",
        )
    )
    scenarios.append(
        Scenario(
            "pos:split_merge",
            "positive",
            categorical("category", _CATEGORY, seed),
            categorical(
                "category",
                {"Consumer Electronics": 300, "Home Electronics": 200, "Books": 300, "Toys": 200},
                seed,
            ),
            ["category"],
            signature="category_split_merge",
            column="category",
            note="Electronics split into two categories",
        )
    )
    scenarios.append(
        Scenario(
            "pos:distribution_shift",
            "positive",
            numeric("amount", amounts),
            numeric("amount", _stretch_above(amounts, pivot=55, factor=2.0)),
            ["amount"],
            signature="numeric_distribution_shift",
            column="amount",
            note="upper half of amounts inflated (non-affine tail thickening)",
        )
    )
    scenarios.append(
        Scenario(
            "pos:unit_scale",
            "positive",
            numeric("amount", amounts),
            numeric("amount", [v * 100 for v in amounts]),
            ["amount"],
            signature="unit_scale_shift",
            column="amount",
            note="dollars re-encoded as cents (x100)",
        )
    )

    # ---- Negatives: normal variation, must stay silent ----------------------
    scenarios.append(
        Scenario(
            "neg:country_sampling_noise",
            "negative",
            categorical("country", _COUNTRY, seed),
            categorical("country", {"US": 398, "UK": 204, "DE": 199, "FR": 199}, seed + 1),
            ["country"],
            note="sub-threshold share wiggle",
        )
    )
    scenarios.append(
        Scenario(
            "neg:amount_small_drift",
            "negative",
            numeric("amount", amounts),
            numeric("amount", [v + 4 for v in amounts]),
            ["amount"],
            note="~5% uniform drift, below the distribution-shift threshold",
        )
    )
    scenarios.append(
        Scenario(
            "neg:status_stable",
            "negative",
            categorical("status", _STATUS, seed),
            categorical("status", {"active": 604, "pending": 248, "closed": 148}, seed + 1),
            ["status"],
            note="stable status mix",
        )
    )

    # ---- Decoys: real but benign changes, must stay silent ------------------
    scenarios.append(
        Scenario(
            "decoy:volume_doubled",
            "decoy",
            categorical("country", _COUNTRY, seed),
            categorical("country", {k: v * 2 for k, v in _COUNTRY.items()}, seed + 1),
            ["country"],
            note="2x rows, identical shares (naive volume monitors would alarm)",
        )
    )
    scenarios.append(
        Scenario(
            "decoy:new_small_category",
            "decoy",
            categorical("country", _COUNTRY, seed),
            categorical(
                "country",
                {"US": 394, "UK": 197, "DE": 197, "FR": 197, "MX": 15},
                seed + 1,
            ),
            ["country"],
            note="a new market appears at 1.5% share",
        )
    )
    scenarios.append(
        Scenario(
            "decoy:amount_mild_stretch",
            "decoy",
            numeric("amount", amounts),
            numeric("amount", _stretch_above(amounts, pivot=55, factor=1.15)),
            ["amount"],
            note="mild upper-tail growth, below the shift threshold",
        )
    )
    scenarios.append(
        Scenario(
            "decoy:amount_small_inflation",
            "decoy",
            numeric("amount", amounts),
            numeric("amount", [v + 6 for v in amounts]),
            ["amount"],
            note="~7% uniform inflation, below the shift threshold",
        )
    )

    return scenarios
