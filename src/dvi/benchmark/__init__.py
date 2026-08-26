"""Benchmark: synthetic data and controlled failure injection with ground truth."""

from .blast_radius import (
    BlastRadiusCase,
    BlastRadiusCaseResult,
    BlastRadiusReport,
    build_blast_radius_cases,
    evaluate_blast_radius,
)
from .evaluate import (
    BenchmarkReport,
    OperatingPoint,
    RcaCaseResult,
    RcaReport,
    ScenarioResult,
    evaluate,
    evaluate_rca,
    recall_at_fixed_fp,
    sweep,
)
from .rca_cases import RcaCase, build_rca_cases
from .real_data import (
    RealDataReport,
    RealFpReport,
    RealRecallReport,
    evaluate_real_data,
    injected_recall_report,
    load_diamonds,
    real_vs_real_report,
    two_sample_splits,
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
    "BlastRadiusCase",
    "BlastRadiusCaseResult",
    "BlastRadiusReport",
    "OperatingPoint",
    "RcaCase",
    "RcaCaseResult",
    "RcaReport",
    "RealDataReport",
    "RealFpReport",
    "RealRecallReport",
    "Scenario",
    "ScenarioResult",
    "build_blast_radius_cases",
    "build_rca_cases",
    "build_scenarios",
    "categorical",
    "evaluate",
    "evaluate_blast_radius",
    "evaluate_rca",
    "evaluate_real_data",
    "inject_value_substitution",
    "injected_recall_report",
    "load_diamonds",
    "make_orders",
    "numeric",
    "ramp",
    "real_vs_real_report",
    "recall_at_fixed_fp",
    "sweep",
    "two_sample_splits",
]
