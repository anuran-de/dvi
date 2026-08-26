"""The pure-Python logistic model (no numpy/sklearn available)."""

import math

from dvi.calibration.model import LogisticModel


def _separable_dataset() -> tuple[list[list[float]], list[int]]:
    """A cleanly separable 1-D problem: x < 0 -> 0, x > 0 -> 1."""
    xs = [-4.0, -3.0, -2.5, -2.0, -1.5, 1.5, 2.0, 2.5, 3.0, 4.0]
    X = [[x] for x in xs]
    y = [0 if x < 0 else 1 for x in xs]
    return X, y


def test_fit_recovers_a_separable_boundary():
    X, y = _separable_dataset()
    model = LogisticModel.fit(X, y, l2=0.0, lr=0.5, iters=2000)

    # Confident and correct on either side of the boundary.
    assert model.predict_proba([[4.0]])[0] > 0.9
    assert model.predict_proba([[-4.0]])[0] < 0.1
    # The decision boundary sits near x = 0.
    at_zero = model.predict_proba([[0.0]])[0]
    assert abs(at_zero - 0.5) < 0.15


def test_predicted_probability_is_monotone_in_the_score():
    X, y = _separable_dataset()
    model = LogisticModel.fit(X, y, l2=0.0, lr=0.5, iters=1000)

    probs = [model.predict_proba([[x]])[0] for x in (-3.0, -1.0, 0.0, 1.0, 3.0)]
    assert probs == sorted(probs)


def test_probabilities_are_bounded():
    X, y = _separable_dataset()
    model = LogisticModel.fit(X, y, l2=0.01, lr=0.5, iters=500)
    for p in model.predict_proba([[100.0], [-100.0], [0.0]]):
        assert 0.0 <= p <= 1.0
        assert not math.isnan(p)


def test_l2_regularization_shrinks_weights():
    X, y = _separable_dataset()
    loose = LogisticModel.fit(X, y, l2=0.0, lr=0.1, iters=2000)
    tight = LogisticModel.fit(X, y, l2=5.0, lr=0.1, iters=2000)
    assert abs(tight.weights[0]) < abs(loose.weights[0])


def test_json_round_trip_is_exact():
    X, y = _separable_dataset()
    model = LogisticModel.fit(X, y, l2=0.1, lr=0.5, iters=500)

    restored = LogisticModel.from_dict(model.to_dict())

    assert restored.weights == model.weights
    assert restored.intercept == model.intercept
    assert restored.feature_mean == model.feature_mean
    assert restored.feature_std == model.feature_std
    probe = [[1.0], [-2.0], [3.5]]
    assert restored.predict_proba(probe) == model.predict_proba(probe)


def test_fit_is_deterministic():
    X, y = _separable_dataset()
    a = LogisticModel.fit(X, y, l2=0.1, lr=0.3, iters=300)
    b = LogisticModel.fit(X, y, l2=0.1, lr=0.3, iters=300)
    assert a.weights == b.weights
    assert a.intercept == b.intercept
