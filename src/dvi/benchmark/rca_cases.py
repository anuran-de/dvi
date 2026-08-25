"""Labelled root-cause cases for measuring ranking under concurrency.

Detection tells you *something* changed; RCA has to pick the *right* cause when
several changes land near the same time. These cases stress that:

  * irrelevant deploys (no lineage path) must be excluded, not merely outranked;
  * a change that lands *after* the symptom must be excluded;
  * among genuine upstream candidates, the closer-in-time / higher-coverage one
    must rank first.

Each case is labelled with the ``true_change_id`` the ranker should return at
rank 0. The distractors are always *strictly weaker* than the true cause, so the
label never contradicts the deterministic scoring.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from dvi.detection import Symptom
from dvi.lineage import LineageGraph
from dvi.rca import ChangeEvent, Observation


@dataclass(frozen=True)
class RcaCase:
    name: str
    lineage: LineageGraph
    observations: list[Observation]
    changes: list[ChangeEvent]
    true_change_id: str
    note: str = ""


def _symptom(asset: str) -> Symptom:
    return Symptom(
        signature="value_substitution",
        column="country",
        magnitude=0.2,
        from_value="UK",
        to_value="United Kingdom",
        description="Value 'UK' appears replaced by 'United Kingdom'.",
    )


def _obs(asset: str, when: datetime) -> Observation:
    return Observation(asset, when, _symptom(asset))


def _chain(*edges: tuple[str, str]) -> LineageGraph:
    g = LineageGraph()
    for upstream, downstream in edges:
        g.add_edge(upstream, downstream)
    return g


def build_rca_cases() -> list[RcaCase]:
    """Return the labelled RCA suite."""
    cases: list[RcaCase] = []

    # 1. Direct hit with an irrelevant distractor and a too-late distractor.
    g = _chain(("U", "X"), ("X", "Y"), ("V", "W"))
    cases.append(
        RcaCase(
            "direct_with_irrelevant_and_late",
            g,
            [_obs("X", datetime(2026, 8, 25, 10, 0))],
            [
                ChangeEvent("true", datetime(2026, 8, 25, 9, 55), ["X"], "deploy to X"),
                ChangeEvent("irrelevant", datetime(2026, 8, 25, 9, 56), ["W"], "deploy to W"),
                ChangeEvent("too_late", datetime(2026, 8, 25, 10, 5), ["X"], "later deploy"),
            ],
            "true",
            note="unrelated + post-symptom changes must be excluded",
        )
    )

    # 2. Two genuine upstream candidates; the closer-in-time one wins.
    g = _chain(("U", "X"), ("X", "Y"))
    cases.append(
        RcaCase(
            "closest_upstream_wins",
            g,
            [_obs("Y", datetime(2026, 8, 25, 10, 0))],
            [
                ChangeEvent("true", datetime(2026, 8, 25, 9, 50), ["X"], "deploy to X"),
                ChangeEvent("far", datetime(2026, 8, 25, 2, 0), ["U"], "early deploy to U"),
            ],
            "true",
            note="closer upstream change outranks the distant one",
        )
    )

    # 3. Coverage wins: the common ancestor explains both symptoms.
    g = _chain(("A", "X"), ("A", "Z"))
    cases.append(
        RcaCase(
            "coverage_wins",
            g,
            [
                _obs("X", datetime(2026, 8, 25, 10, 0)),
                _obs("Z", datetime(2026, 8, 25, 10, 0)),
            ],
            [
                ChangeEvent("true", datetime(2026, 8, 25, 9, 50), ["A"], "deploy to A"),
                ChangeEvent("partial", datetime(2026, 8, 25, 9, 55), ["X"], "deploy to X"),
            ],
            "true",
            note="ancestor explaining both symptoms beats the partial explainer",
        )
    )

    # 4. Dense concurrency: one real cause among several unrelated same-minute deploys.
    g = _chain(("U", "X"), ("X", "Y"), ("V", "W"), ("P", "Q"))
    cases.append(
        RcaCase(
            "dense_concurrency",
            g,
            [_obs("Y", datetime(2026, 8, 25, 10, 0))],
            [
                ChangeEvent("true", datetime(2026, 8, 25, 9, 58), ["X"], "deploy to X"),
                ChangeEvent("noise_w", datetime(2026, 8, 25, 9, 58), ["W"], "deploy to W"),
                ChangeEvent("noise_q", datetime(2026, 8, 25, 9, 59), ["Q"], "deploy to Q"),
                ChangeEvent("noise_v", datetime(2026, 8, 25, 9, 57), ["V"], "deploy to V"),
            ],
            "true",
            note="only the upstream deploy explains the symptom",
        )
    )

    return cases
