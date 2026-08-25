"""Domain objects for root-cause analysis."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from dvi.detection import Symptom


@dataclass
class ChangeEvent:
    """A deployment or commit that touched one or more data assets."""

    id: str
    timestamp: datetime
    targets: list[str]
    label: str = ""


@dataclass
class Observation:
    """A symptom observed on a specific asset at a specific time."""

    asset: str
    observed_at: datetime
    symptom: Symptom


@dataclass
class RootCauseCandidate:
    """A change event scored as a possible cause, with its evidence."""

    change: ChangeEvent
    score: float
    explained: list[Observation] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
