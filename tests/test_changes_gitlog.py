import subprocess
from datetime import datetime
from pathlib import Path

from dvi.changes import collect_commits


def _git(cwd: Path, *args: str, env=None) -> None:
    subprocess.run(["git", *args], cwd=str(cwd), check=True,
                   capture_output=True, text=True, env=env)


def _init_repo(cwd: Path) -> None:
    _git(cwd, "init", "-q")
    _git(cwd, "config", "user.email", "t@example.com")
    _git(cwd, "config", "user.name", "T")


def _commit(cwd: Path, filename: str, message: str, iso_date: str) -> None:
    (cwd / filename).write_text("x", encoding="utf-8")
    _git(cwd, "add", filename)
    import os
    env = {**os.environ, "GIT_AUTHOR_DATE": iso_date, "GIT_COMMITTER_DATE": iso_date}
    _git(cwd, "commit", "-q", "-m", message, env=env)


def test_collects_commit_metadata_and_changed_files(tmp_path):
    _init_repo(tmp_path)
    _commit(tmp_path, "a.sql", "first", "2026-08-25T09:50:00+00:00")
    _commit(tmp_path, "b.sql", "second", "2026-08-25T10:00:00+00:00")

    records = collect_commits(base=None, head="HEAD", cwd=tmp_path)

    assert [r.subject for r in records] == ["first", "second"] or \
           [r.subject for r in records] == ["second", "first"]
    by_subject = {r.subject: r for r in records}
    assert by_subject["second"].changed_files == ("b.sql",)
    # naive UTC
    ts = by_subject["first"].timestamp
    assert ts.tzinfo is None
    assert ts == datetime(2026, 8, 25, 9, 50, 0)


def test_range_excludes_the_base_commit(tmp_path):
    _init_repo(tmp_path)
    _commit(tmp_path, "a.sql", "first", "2026-08-25T09:50:00+00:00")
    _commit(tmp_path, "b.sql", "second", "2026-08-25T10:00:00+00:00")

    records = collect_commits(base="HEAD~1", head="HEAD", cwd=tmp_path)
    assert [r.subject for r in records] == ["second"]


def test_offset_timestamps_normalized_to_utc(tmp_path):
    _init_repo(tmp_path)
    _commit(tmp_path, "a.sql", "first", "2026-08-25T11:50:00+02:00")
    records = collect_commits(base=None, head="HEAD", cwd=tmp_path)
    assert records[0].timestamp == datetime(2026, 8, 25, 9, 50, 0)  # 11:50 +02:00 -> 09:50Z


def test_missing_repo_returns_empty_best_effort(tmp_path):
    # tmp_path is not a git repo -> git fails -> []
    assert collect_commits(base=None, head="HEAD", cwd=tmp_path) == []


def test_unknown_ref_returns_empty_best_effort(tmp_path):
    _init_repo(tmp_path)
    _commit(tmp_path, "a.sql", "first", "2026-08-25T09:50:00+00:00")
    assert collect_commits(base="does-not-exist", head="HEAD", cwd=tmp_path) == []
