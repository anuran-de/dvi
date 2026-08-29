"""Turn a validated DviConfig into an Incident (or None).

Two adapters converge on the same pipeline call:
- file:      polars reads the two columnar files -> analyze_change (frames)
- warehouse: DuckDB drives the M5a pushdown path -> analyze_change_from_profiles

Everything except *how profiles are produced* (lineage, change list, model) is
shared, so the two producers cannot decide differently — the M5a seam.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import polars as pl

from dvi.calibration.model import LogisticModel
from dvi.incidents import Incident
from dvi.lineage import LineageGraph, load_dbt_manifest
from dvi.pipeline import analyze_change, analyze_change_from_profiles
from dvi.rca import ChangeEvent
from dvi.warehouse import DuckDBDialect, SqlProfileSource

from .config import DviConfig, DviError

_READERS = {
    ".parquet": pl.read_parquet,
    ".csv": pl.read_csv,
    ".ndjson": pl.read_ndjson,
}


def _read_frame(path: str) -> pl.DataFrame:
    p = Path(path)
    if not p.exists():
        raise DviError(f"source file not found: {p}")
    reader = _READERS.get(p.suffix.lower())
    if reader is None:
        raise DviError(
            f"unsupported source file extension {p.suffix!r} for {p} "
            f"(use one of {', '.join(sorted(_READERS))})"
        )
    try:
        return reader(p)
    except Exception as e:  # noqa: BLE001 - surface any read failure as a clear error
        raise DviError(f"could not read source file {p}: {e}") from e


def _lineage_and_changes(config: DviConfig) -> tuple[LineageGraph, list[ChangeEvent]]:
    manifest_path = Path(config.lineage.manifest)
    if not manifest_path.exists():
        raise DviError(f"lineage manifest not found: {manifest_path}")
    try:
        lineage = load_dbt_manifest(manifest_path)
    except Exception as e:  # noqa: BLE001
        raise DviError(f"could not read lineage manifest {manifest_path}: {e}") from e

    changes: list[ChangeEvent] = []
    for change in config.changes:
        for target in change.targets:
            if target not in lineage.nodes:
                raise DviError(
                    f"change {change.id!r} target {target!r} is not a node in "
                    f"lineage manifest {config.lineage.manifest!r}"
                )
        changes.append(
            ChangeEvent(
                id=change.id,
                timestamp=change.timestamp,
                targets=list(change.targets),
                label=change.label,
            )
        )
    return lineage, changes


def _load_model(config: DviConfig) -> LogisticModel | None:
    if not config.gate.model:
        return None
    # Imported here (not at module top) to avoid any import-order cycle between
    # the pipeline and calibration packages when dvi.cli is first imported.
    from dvi.calibration.loader import load_model

    return load_model()


def incident_from_config(config: DviConfig) -> Incident | None:
    """Analyze the configured before/after snapshot and return an incident."""
    lineage, changes = _lineage_and_changes(config)
    model = _load_model(config)
    observed_at = datetime.now(UTC)

    source = config.source
    if source.kind == "file":
        before = _read_frame(source.before)
        after = _read_frame(source.after)
        return analyze_change(
            asset=config.asset,
            before=before,
            after=after,
            observed_at=observed_at,
            lineage=lineage,
            changes=changes,
            columns=config.columns,
            model=model,
        )

    # warehouse
    import duckdb

    db = Path(source.database)
    if not db.exists():
        raise DviError(f"warehouse database not found: {db}")
    try:
        con = duckdb.connect(str(db), read_only=True)
    except Exception as e:  # noqa: BLE001
        raise DviError(f"could not open warehouse database {db}: {e}") from e
    try:
        def execute(sql: str):
            return con.execute(sql).fetchall()

        dialect = DuckDBDialect()
        try:
            before = SqlProfileSource(
                execute, source.before_table, dialect=dialect
            ).profile(config.columns)
            after = SqlProfileSource(
                execute, source.after_table, dialect=dialect
            ).profile(config.columns)
        except Exception as e:  # noqa: BLE001 - clear error, not a raw DB traceback
            raise DviError(f"warehouse profiling failed: {e}") from e
    finally:
        con.close()

    return analyze_change_from_profiles(
        asset=config.asset,
        before=before,
        after=after,
        observed_at=observed_at,
        lineage=lineage,
        changes=changes,
        columns=config.columns,
        model=model,
    )
