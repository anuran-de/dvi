"""Attaching a measured confidence to fired symptoms."""

import polars as pl

from dvi.benchmark.synthetic import categorical
from dvi.calibration.loader import load_model
from dvi.calibration.score import attach_confidence, score_symptom
from dvi.detection import detect_value_substitution
from dvi.pipeline import detect_symptoms
from dvi.profiling import profile_column


def _rename_frame(n: int, moved_share: float) -> tuple[pl.DataFrame, pl.DataFrame]:
    """A country column where ``moved_share`` of UK is renamed, at sample size n."""
    uk = round(0.3 * n)
    tenth = n // 10
    us = n - uk - 2 * tenth
    before = categorical("country", {"US": us, "UK": uk, "DE": tenth, "FR": tenth})
    moved = round(moved_share * uk)
    after = categorical(
        "country",
        {
            "US": us,
            "UK": uk - moved,
            "United Kingdom": moved,
            "DE": tenth,
            "FR": tenth,
        },
    )
    return before, after


def test_score_symptom_is_a_probability():
    before, after = _rename_frame(2000, 1.0)
    baseline = profile_column(before["country"])
    current = profile_column(after["country"])
    symptom = detect_value_substitution(baseline, current)
    assert symptom is not None

    p = score_symptom(symptom, baseline, current, load_model())
    assert 0.0 <= p <= 1.0


def test_attach_confidence_returns_a_copy_with_confidence_set():
    before, after = _rename_frame(2000, 1.0)
    baseline = profile_column(before["country"])
    current = profile_column(after["country"])
    symptom = detect_value_substitution(baseline, current)

    scored = attach_confidence(symptom, baseline, current, load_model())
    assert symptom.confidence is None  # original untouched
    assert scored.confidence is not None
    assert 0.0 <= scored.confidence <= 1.0


def test_detect_symptoms_populates_confidence_only_when_model_given():
    before, after = _rename_frame(3000, 1.0)

    without = detect_symptoms(before, after, ["country"])
    assert without and all(s.confidence is None for s in without)

    with_model = detect_symptoms(before, after, ["country"], model=load_model())
    assert with_model and all(s.confidence is not None for s in with_model)


def test_strong_change_scores_higher_than_borderline():
    model = load_model()

    strong_b, strong_a = _rename_frame(5000, 1.0)
    weak_b, weak_a = _rename_frame(300, 0.4)

    strong = detect_symptoms(strong_b, strong_a, ["country"], model=model)
    weak = detect_symptoms(weak_b, weak_a, ["country"], model=model)
    assert strong and weak
    assert strong[0].confidence > weak[0].confidence
