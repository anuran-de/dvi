import math

from dvi.detection.significance import SIGNIFICANCE_Z, noise_threshold, pooled_share


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


def test_pooled_share_is_count_weighted_not_a_midpoint():
    # Unequal samples: baseline 50% of 100 rows, current 10% of 900 rows. The
    # correct pooled proportion for a two-proportion test is (x_a + x_b)/(n_a + n_b)
    # = (50 + 90)/1000 = 0.14, NOT the share midpoint (0.5 + 0.1)/2 = 0.30.
    assert math.isclose(pooled_share(0.5, 0.1, 100, 900), 0.14, rel_tol=1e-9)


def test_pooled_share_equals_midpoint_when_samples_are_equal():
    # With equal sample sizes the count-weighted pool reduces to the midpoint.
    assert math.isclose(pooled_share(0.4, 0.2, 500, 500), 0.30, rel_tol=1e-9)


def test_pooled_share_without_samples_falls_back_to_midpoint():
    assert math.isclose(pooled_share(0.4, 0.2, 0, 0), 0.30, rel_tol=1e-9)
