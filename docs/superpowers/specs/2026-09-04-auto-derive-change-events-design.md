# Auto-derive change events from git/CI (#11)

**Status:** approved for implementation
**Issue:** [#11](https://github.com/anuran-de/dvi/issues/11)
**Date:** 2026-09-04

## Problem

Root-cause analysis attributes a semantic data change to a declared deploy/PR
event, but those events must be hand-declared in `dvi.toml` under `[[changes]]`
(`src/dvi/cli/config.py`). This is friction and easy to get wrong. In a CI
context the tool already has everything it needs — the commit range, commit
metadata, and the changed files — to derive candidate `ChangeEvent`s
automatically.

## Goal

Auto-derive candidate `ChangeEvent`s from git metadata, map changed files to
lineage nodes so the candidates are narrowed to modeled assets, and feed them
into the existing `rank_root_causes` unchanged. Explicit `[[changes]]` still
work and are unioned in.

Non-goals: GitHub-API/event-payload ingestion, PR-title/author enrichment,
non-git VCS. RCA scoring itself is untouched.

## Chosen approach

- **git as the portable core.** Shell out to `git log` / `git show --name-only`
  over a commit range. Works in the Action *and* locally, deterministic, no
  network, VCS-host-agnostic.
- **GitHub env supplies the range only.** `GITHUB_BASE_REF`/`GITHUB_SHA` (or an
  optional `[git]` block in `dvi.toml`) resolve the range; default
  `HEAD~1..HEAD`.
- **Union with explicit `[[changes]]`.** Derived events are added to any
  explicit changes and de-duplicated. `changes` becomes optional.
- **One event per commit, drop unmapped.** Each commit → one `ChangeEvent`;
  commits touching no modeled file are dropped (this is the narrowing).

Rejected alternative: read the GitHub API / event JSON. GitHub-locked, needs a
token, hard to test deterministically.

## Components

Each unit has one purpose, a well-defined interface, and is testable in
isolation.

### 1. `derive_change_events` — pure core (no git, no I/O)

```
derive_change_events(
    commits: Iterable[CommitRecord],
    resolve_targets: Callable[[str], set[str]],   # changed file path -> lineage nodes
) -> list[ChangeEvent]
```

- `CommitRecord`: `sha: str`, `timestamp: datetime`, `subject: str`,
  `changed_files: list[str]`.
- For each commit: `targets = union(resolve_targets(f) for f in changed_files)`.
  If empty, drop the commit.
- Emit `ChangeEvent(id=short_sha, timestamp=commit.timestamp,
  targets=sorted(targets), label=subject)`.
- Return sorted by `(timestamp, id)` — explicit, so order never depends on
  set/dict iteration (PYTHONHASHSEED-safe).

This is where the "synthetic git contexts" tests live: feed hand-built
`CommitRecord`s and a fake resolver, assert the derived events.

### 2. `collect_commits` — git adapter (side-effecting)

```
collect_commits(base: str | None, head: str, cwd: Path) -> list[CommitRecord]
```

- Runs `git log`/`git show` for the range (`base..head`, or just `head` when no
  base) via `subprocess`, parsing a stable machine format (e.g.
  `--format=%H%x1f%cI%x1f%s` + `--name-only`).
- Commit time uses committer date in ISO-8601 (`%cI`), parsed to an aware
  `datetime`.
- **Best-effort:** any `git` failure (not a repo, unknown ref, git missing)
  returns `[]`. Derivation contributes nothing rather than crashing a run.
- Integration-tested against a throwaway temp git repo.

### 3. File → node index (lineage)

- Extend `load_dbt_manifest` to retain each node's `original_file_path`.
- Add `LineageGraph.nodes_for_file(path) -> set[str]`: suffix-normalized match
  (normalize separators; match on the manifest-relative path or a trailing
  suffix) so a dbt project nested under a repo subdir still resolves.
- Manifests without file paths → empty result → commits drop gracefully.

### 4. Range resolver

```
resolve_range(env: Mapping[str, str], git_config) -> tuple[str | None, str]
```

- Precedence: explicit `[git] base/head` in config → GitHub env
  (`GITHUB_BASE_REF` as base, `GITHUB_SHA` as head) → default
  `(HEAD~1, HEAD)`.
- Pure function over an injected env mapping — unit-testable without touching
  the real environment.

## Wiring & contract changes

- **`config.py`:** drop `min_length=1` on `changes` (default `[]`). Add an
  optional `[git]` config block (`base`, `head`) — both optional.
- **`sources.py` `_lineage_and_changes`:** build explicit changes, derive from
  git (`resolve_range` → `collect_commits` → `derive_change_events` with
  `lineage.nodes_for_file`), then **union + dedup**. Dedup key:
  `(id, tuple(sorted(targets)), timestamp)`. Explicit changes still validate
  their targets against lineage nodes as today; derived targets are lineage
  nodes by construction.
- **`sources.py` `incident_from_config`:** `observed_at = max(c.timestamp for c
  in combined)`. If `combined` is empty → `DviError` ("no change events:
  declare [[changes]] or run in a git repo whose commits touch a modeled
  asset"), surfaced as exit code 2. This is a deliberate behavior change,
  approved: a run with no attributable change is an error, because RCA is core.
- **Action (`action.yml`) + docs:** document that callers must use
  `actions/checkout` with `fetch-depth: 0` so history/range is available; pass
  the GitHub env through. RCA output shape unchanged.

## Determinism & error handling

- No wall clock; every ordering is an explicit sort. Safe under the alternate
  `PYTHONHASHSEED` CI pass.
- git/manifest problems degrade to "derived nothing," never a crash.
- The only new error path is truly-empty combined changes → `DviError`.

## Testing (TDD, RED first)

- Unit: `derive_change_events` — mapping, drop-unmapped, sort, dedup, short-sha,
  label.
- Unit: `LineageGraph.nodes_for_file` on a manifest carrying
  `original_file_path` (including a nested-subdir path).
- Unit: `resolve_range` precedence over an injected env dict.
- Integration: `collect_commits` against a temp git repo (create commits, assert
  records); and the best-effort `[]` on a non-repo dir.
- CLI/sources: union + dedup + `observed_at`; empty-combined → `DviError`/exit 2;
  explicit-only path unchanged.
- Docs (`README`, `docs/`) + `CHANGELOG.md` `## [Unreleased]` updated in the
  same PR.

## Rollout

Single PR: engine core + git adapter + lineage index + CLI/sources wiring +
Action/docs. Merged to `main` via the normal PR flow (maintainer decides merge).
