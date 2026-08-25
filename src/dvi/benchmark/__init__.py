"""Benchmark: synthetic data and controlled failure injection with ground truth."""

from .evaluate import (
    BenchmarkReport,
    OperatingPoint,
    ScenarioResult,
    evaluate,
    recall_at_fixed_fp,
    sweep,
)
from .scenarios import Scenario, build_scenarios
from .synthetic import (
    categorical,
    inject_value_substitution,
    make_orders,
    numeric,
    ramp,
)

__all__ = [
    "BenchmarkReport",
    "OperatingPoint",
    "Scenario",
    "ScenarioResult",
    "build_scenarios",
    "categorical",
    "evaluate",
    "inject_value_substitution",
    "make_orders",
    "numeric",
    "ramp",
    "recall_at_fixed_fp",
    "sweep",
]
