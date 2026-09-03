"""Declarative config for the DVI CLI: parse dvi.toml, validate with pydantic.

The config is the single source of truth for a run — what asset to analyze,
where its before/after data lives, the lineage manifest, the change list RCA
attributes to, and the gate. Every expected failure surfaces as a DviError so
the CLI can map it to exit code 2 instead of a raw traceback.
"""

from __future__ import annotations

import re
import tomllib
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator


class DviError(Exception):
    """A clear, user-facing error (bad config, missing input, unresolved target)."""


# A dot-separated SQL identifier: each part must be a plain, unquoted identifier
# (letter/underscore start, then letters/digits/underscores/dollar). This rejects
# whitespace, semicolons, quotes, comment markers and empty parts, so a table name
# can never carry a SQL-injection payload into the generated warehouse queries.
_IDENT_PART = re.compile(r"[A-Za-z_][A-Za-z0-9_$]*")


def _validate_table_identifier(value: str) -> str:
    parts = value.split(".")
    if not all(_IDENT_PART.fullmatch(part) for part in parts):
        raise ValueError(
            f"invalid table identifier {value!r}: each dot-separated part must be a "
            "plain SQL identifier (letters, digits, underscore, dollar; not starting "
            "with a digit)"
        )
    return value


class FileSource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["file"]
    before: str
    after: str


class WarehouseSource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["warehouse"]
    database: str
    before_table: str
    after_table: str

    @field_validator("before_table", "after_table")
    @classmethod
    def _check_table_identifier(cls, value: str) -> str:
        return _validate_table_identifier(value)


class LineageConfig(BaseModel):
    manifest: str


class ChangeConfig(BaseModel):
    id: str
    targets: list[str] = Field(min_length=1)
    timestamp: datetime
    label: str = ""

    @field_validator("timestamp", mode="after")
    @classmethod
    def _normalize_naive_utc(cls, value: datetime) -> datetime:
        # Mirror dvi.changes.gitlog._to_naive_utc so declared and derived
        # change timestamps are always naive UTC and comparable/max()-able
        # together (the DVI spec's global "naive UTC" constraint).
        if value.tzinfo is not None:
            value = value.astimezone(UTC).replace(tzinfo=None)
        return value


class GitConfig(BaseModel):
    """Optional commit range for auto-deriving change events."""

    model_config = ConfigDict(extra="forbid")
    base: str | None = None
    head: str | None = None


class GateConfig(BaseModel):
    fail_on: Literal["low", "medium", "high", "critical"] = "high"
    model: bool = True


class StoreConfig(BaseModel):
    """Optional incident persistence. Present ⇒ each run records its incident."""

    model_config = ConfigDict(extra="forbid")
    path: str


class DviConfig(BaseModel):
    asset: str
    source: FileSource | WarehouseSource = Field(discriminator="kind")
    lineage: LineageConfig
    changes: list[ChangeConfig] = Field(default_factory=list)
    git: GitConfig = Field(default_factory=GitConfig)
    gate: GateConfig = Field(default_factory=GateConfig)
    store: StoreConfig | None = None
    columns: list[str] | None = None


def load_config(path: str | Path) -> DviConfig:
    """Load and validate a dvi.toml, wrapping any failure in DviError."""
    p = Path(path)
    try:
        with p.open("rb") as f:
            raw = tomllib.load(f)
    except FileNotFoundError as e:
        raise DviError(f"config file not found: {p}") from e
    except tomllib.TOMLDecodeError as e:
        raise DviError(f"invalid TOML in {p}: {e}") from e
    try:
        return DviConfig.model_validate(raw)
    except ValidationError as e:
        raise DviError(f"invalid config {p}:\n{e}") from e
