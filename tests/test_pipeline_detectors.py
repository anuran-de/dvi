"""Detector-registry behaviour: which signatures fire, and precedence between them."""

import polars as pl

from dvi.pipeline.analyze import detect_symptoms


def test_unit_scale_shift_suppresses_distribution_shift_on_same_column():
    # A rigid x100 rescale (dollars -> cents). Both #4 and #5 would match the raw
    # movement, but #5 is more specific, so only it should be reported.
    before = pl.DataFrame({"amount": [float(v) for v in range(1, 201)]})
    after = pl.DataFrame({"amount": [float(v) * 100 for v in range(1, 201)]})

    symptoms = detect_symptoms(before, after, columns=["amount"])

    signatures = {s.signature for s in symptoms}
    assert "unit_scale_shift" in signatures
    assert "numeric_distribution_shift" not in signatures


def test_case_format_suppresses_value_substitution_on_same_column():
    # Lowercasing every category also looks like a mass-conserving substitution to
    # #1, but the re-spelling explanation (#2) is more specific and should win.
    before = pl.DataFrame({"country": ["US"] * 60 + ["UK"] * 25 + ["DE"] * 15})
    after = pl.DataFrame({"country": ["us"] * 60 + ["uk"] * 25 + ["de"] * 15})

    symptoms = detect_symptoms(before, after, columns=["country"])
    signatures = {s.signature for s in symptoms}

    assert "case_format_normalization" in signatures
    assert "value_substitution" not in signatures


def test_split_is_reported_as_split_not_substitution():
    before = pl.DataFrame({"category": ["Electronics"] * 50 + ["Books"] * 30 + ["Toys"] * 20})
    after = pl.DataFrame(
        {"category": ["Consumer Electronics"] * 30 + ["Home Electronics"] * 20
         + ["Books"] * 30 + ["Toys"] * 20}
    )

    symptoms = detect_symptoms(before, after, columns=["category"])
    signatures = {s.signature for s in symptoms}

    assert "category_split_merge" in signatures
    assert "value_substitution" not in signatures


def test_behavioral_shift_still_reports_distribution_shift():
    # A shape change that is NOT a rigid affine map: spread fans out, median stable.
    before = pl.DataFrame({"amount": [50.0] * 90 + [45.0] * 5 + [55.0] * 5})
    after = pl.DataFrame(
        {"amount": [50.0] * 40 + [20.0] * 30 + [80.0] * 30}
    )

    symptoms = detect_symptoms(before, after, columns=["amount"])
    signatures = {s.signature for s in symptoms}

    assert "numeric_distribution_shift" in signatures
    assert "unit_scale_shift" not in signatures
