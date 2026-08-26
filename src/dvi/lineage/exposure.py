"""External consumers of the warehouse — dbt *exposures* — and their business
criticality.

An exposure is a dashboard, ML feature/model, application, or notebook that
reads one or more dbt models. Criticality is an ordered scale so the *worst*
consumer in a blast radius is just a ``max()``. It is either declared explicitly
in the exposure's ``meta.criticality`` or inferred from its ``type`` and dbt
``maturity``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum


class Criticality(IntEnum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


@dataclass(frozen=True)
class Exposure:
    unique_id: str
    name: str
    type: str
    criticality: Criticality
    owner: str
    url: str
    depends_on: frozenset[str]


_OVERRIDE = {
    "low": Criticality.LOW,
    "medium": Criticality.MEDIUM,
    "high": Criticality.HIGH,
    "critical": Criticality.CRITICAL,
}

_MATURITY = {"high": Criticality.HIGH, "medium": Criticality.MEDIUM, "low": Criticality.LOW}


def derive_criticality(type: str, maturity: str, meta: dict) -> Criticality:
    """Business criticality of an exposure.

    Precedence: an explicit ``meta.criticality`` override wins; otherwise a
    customer-facing ``application`` at ``maturity == "high"`` is CRITICAL; then
    per-type defaults (application/ml -> HIGH, dashboard -> its maturity,
    notebook/analysis -> LOW, anything else -> MEDIUM).
    """
    override = str((meta or {}).get("criticality", "")).lower()
    if override in _OVERRIDE:
        return _OVERRIDE[override]

    if type == "application":
        if maturity == "high":
            return Criticality.CRITICAL
        return Criticality.HIGH
    if type == "ml":
        return Criticality.HIGH
    if type == "dashboard":
        return _MATURITY.get(maturity, Criticality.MEDIUM)
    if type in {"notebook", "analysis"}:
        return Criticality.LOW
    return Criticality.MEDIUM
