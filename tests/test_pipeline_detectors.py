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
