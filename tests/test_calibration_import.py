"""The calibration package must import cleanly as a *first* import.

Regression guard for a circular import: ``dvi.pipeline.analyze`` used to import
the ``dvi.calibration`` package while that package's ``__init__`` was still
executing (calibration -> loader -> dataset -> benchmark -> pipeline.analyze ->
calibration), so ``from dvi.calibration import load_model`` raised ImportError in
any fresh process. The full test suite hid it only because an alphabetically
earlier test warmed ``sys.modules`` first. Each import below runs in its own
interpreter so nothing is pre-warmed.
"""

import subprocess
import sys


def _import_in_fresh_process(statement: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-c", statement],
        capture_output=True,
        text=True,
    )


def test_calibration_public_api_imports_first():
    result = _import_in_fresh_process("from dvi.calibration import load_model")
    assert result.returncode == 0, result.stderr


def test_calibration_package_imports_first():
    result = _import_in_fresh_process("import dvi.calibration")
    assert result.returncode == 0, result.stderr


def test_score_submodule_imports_first():
    result = _import_in_fresh_process("from dvi.calibration.score import attach_confidence")
    assert result.returncode == 0, result.stderr
