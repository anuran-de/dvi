import math

from dvi.detection.significance import SIGNIFICANCE_Z, noise_threshold


def test_noise_threshold_matches_z_times_standard_error():
    # Two-proportion standard error for a pooled share.
    p, na, nb = 0.2, 1000, 1000
    se = math.sqrt(p * (1 - p) * (1 / na + 1 / nb))
    assert math.isclose(noise_threshold(p, na, nb), SIGNIFICANCE_Z * se, rel_tol=1e-9)


def test_threshold_shrinks_as_samples_grow():
    small = noise_threshold(0.2, 200, 200)
    large = noise_threshold(0.2, 20000, 20000)
    assert small > large
    # 100x the rows -> ~10x tighter (sqrt law).
    assert math.isclose(small / large, 10.0, rel_tol=1e-6)


def test_threshold_is_zero_without_samples():
    # No sample-size information: fall back to no noise floor.
    assert noise_threshold(0.2, 0, 100) == 0.0
    assert noise_threshold(0.2, 100, 0) == 0.0
