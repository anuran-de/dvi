"""Incident synthesis: turn a corroborated cause into an evidence-backed incident."""

from .impact import (
    BusinessImpact,
    assess_impact,
    criticality_to_severity,
    escalate_severity,
    render_business_impact,
)
from .incident import Incident, synthesize_incident

__all__ = [
    "BusinessImpact",
    "Incident",
    "assess_impact",
    "criticality_to_severity",
    "escalate_severity",
    "render_business_impact",
    "synthesize_incident",
]
