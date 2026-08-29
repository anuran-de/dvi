"""The pipeline (and anything that imports it, like the CLI) must import
cleanly as a *first* import.

Regression guard for the reverse direction of the cycle guarded by
``test_calibration_import.py``: ``dvi.benchmark.evaluate`` used to import
``dvi.pipeline.analyze`` at module level, so importing ``dvi.pipeline`` (or
``dvi.cli.sources``, which imports it) as the very first ``dvi`` import in a
fresh process walked straight into
    pipeline.analyze -> calibration -> calibration.dataset -> benchmark
    -> benchmark.evaluate -> pipeline.analyze (partially initialized)
and raised ImportError. This matters because the shipped ``dvi`` console
script imports ``dvi.cli.main`` -> ``dvi.cli.sources`` -> ``dvi.pipeline`` as
its first ``dvi`` import, so this would have crashed on every CLI invocation.
Each import below runs in its own interpreter so nothing is pre-warmed.
"""

import subprocess
import sys


def _import_in_fresh_process(statement: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-c", statement],
        capture_output=True,
        text=True,
    )


def test_pipeline_package_imports_first():
    result = _import_in_fresh_process("import dvi.pipeline")
    assert result.returncode == 0, result.stderr


def test_cli_sources_imports_first():
    result = _import_in_fresh_process("from dvi.cli.sources import incident_from_config")
    assert result.returncode == 0, result.stderr


def test_cli_main_imports_first():
    result = _import_in_fresh_process("import dvi.cli.main")
    assert result.returncode == 0, result.stderr
