"""A pure-Python logistic-regression model.

numpy/scipy/sklearn are not available in this environment, so the model is
implemented from scratch: batch gradient descent on the mean logistic loss with
L2 regularization, over a small feature vector. Everything is deterministic
(zero initialisation, fixed iteration count, no shuffling) so a fit is
reproducible run to run and can be frozen into JSON.

Features are standardized internally (mean/std learned at fit time and stored),
which keeps gradient descent well-conditioned across features on different scales
(e.g. a 0–1 magnitude next to a log-count).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

MODEL_VERSION = 1


def _sigmoid(z: float) -> float:
    # Numerically stable logistic function.
    if z >= 0:
        ez = math.exp(-z)
        return 1.0 / (1.0 + ez)
    ez = math.exp(z)
    return ez / (1.0 + ez)


@dataclass
class LogisticModel:
    """Logistic regression over standardized features.

    ``weights``/``intercept`` live in *standardized* feature space; the stored
    ``feature_mean``/``feature_std`` recover the standardization at predict time.
    """

    weights: list[float]
    intercept: float
    feature_mean: list[float]
    feature_std: list[float]
    version: int = MODEL_VERSION
    metadata: dict[str, object] = field(default_factory=dict)

    # -- fitting -----------------------------------------------------------

    @classmethod
    def fit(
        cls,
        X: list[list[float]],
        y: list[int],
        *,
        l2: float = 0.0,
        lr: float = 0.1,
        iters: int = 1000,
    ) -> LogisticModel:
        """Fit by deterministic batch gradient descent on the mean logistic loss."""
        if not X:
            raise ValueError("cannot fit on an empty dataset")
        if len(X) != len(y):
            raise ValueError("X and y must have the same length")

        n = len(X)
        d = len(X[0])
        mean, std = _standardization(X, d)
        Z = [_standardize_row(row, mean, std) for row in X]

        weights = [0.0] * d
        intercept = 0.0
        for _ in range(iters):
            grad_w = [0.0] * d
            grad_b = 0.0
            for zi, yi in zip(Z, y, strict=True):
                pred = _sigmoid(intercept + sum(w * z for w, z in zip(weights, zi, strict=True)))
                err = pred - yi
                grad_b += err
                for j in range(d):
                    grad_w[j] += err * zi[j]
            # Mean gradient; L2 shrinks weights (not the intercept).
            intercept -= lr * (grad_b / n)
            for j in range(d):
                weights[j] -= lr * (grad_w[j] / n + l2 * weights[j])

        return cls(
            weights=weights,
            intercept=intercept,
            feature_mean=mean,
            feature_std=std,
        )

    # -- inference ---------------------------------------------------------

    def predict_proba(self, X: list[list[float]]) -> list[float]:
        """Predicted P(y=1) for each row."""
        out: list[float] = []
        for row in X:
            z = _standardize_row(row, self.feature_mean, self.feature_std)
            score = self.intercept + sum(w * zi for w, zi in zip(self.weights, z, strict=True))
            out.append(_sigmoid(score))
        return out

    # -- persistence -------------------------------------------------------

    def to_dict(self) -> dict[str, object]:
        return {
            "version": self.version,
            "weights": list(self.weights),
            "intercept": self.intercept,
            "feature_mean": list(self.feature_mean),
            "feature_std": list(self.feature_std),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> LogisticModel:
        return cls(
            weights=list(data["weights"]),  # type: ignore[arg-type]
            intercept=float(data["intercept"]),  # type: ignore[arg-type]
            feature_mean=list(data["feature_mean"]),  # type: ignore[arg-type]
            feature_std=list(data["feature_std"]),  # type: ignore[arg-type]
            version=int(data.get("version", MODEL_VERSION)),  # type: ignore[arg-type]
            metadata=dict(data.get("metadata", {})),  # type: ignore[arg-type]
        )


def _standardization(X: list[list[float]], d: int) -> tuple[list[float], list[float]]:
    """Per-feature mean and std; a zero-variance feature gets std 1 (no scaling)."""
    n = len(X)
    mean = [sum(row[j] for row in X) / n for j in range(d)]
    std: list[float] = []
    for j in range(d):
        var = sum((row[j] - mean[j]) ** 2 for row in X) / n
        s = math.sqrt(var)
        std.append(s if s > 1e-12 else 1.0)
    return mean, std


def _standardize_row(row: list[float], mean: list[float], std: list[float]) -> list[float]:
    return [(v - m) / s for v, m, s in zip(row, mean, std, strict=True)]
