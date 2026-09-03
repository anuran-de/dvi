# Contributing to DVI

Thanks for your interest in DVI. It's early and there's a lot to build — the
[open issues](https://github.com/anuran-de/dvi/issues) are the best place to
start, and small PRs are very welcome.

By participating you agree to keep the project a respectful, harassment-free
space for everyone. Be kind; assume good faith.

## Ways to contribute

- **Report a bug** or **request a feature** via the issue templates.
- **Improve docs** — the `docs/` folder, the README, or inline docstrings.
- **Pick up an issue** — comment first so we don't duplicate work, then open a PR.
- **Add a warehouse dialect, signature, or connector** — please open an issue to
  discuss the design before building anything large.

## Development setup

DVI is a Python engine (`src/dvi/`) plus a static web UI (`dvi/`). You only need
the part you're touching.

### Python engine

Requires **Python 3.11+**.

```bash
git clone https://github.com/anuran-de/dvi.git
cd dvi
python -m venv .venv
source .venv/bin/activate        # Windows (Git Bash): source .venv/Scripts/activate
pip install -e ".[dev]"

pytest              # full suite (also runs the demo + benchmark end to end)
ruff check .        # lint
```

### Web UI

Requires **Node 20+**.

```bash
cd dvi
npm install
npm run dev         # http://localhost:3000
npm test            # vitest unit tests
npm run e2e         # playwright smoke tests
```

See [docs/architecture.md](docs/architecture.md) for the module map and
[docs/frontend.md](docs/frontend.md) for the web app.

## The conventions this project holds to

These are the things a reviewer will look for. They're also *why* DVI's results
are trustworthy, so please don't work around them.

- **Test-driven.** New behavior lands as a **failing test first**, then the
  minimal code to pass it. A bug fix starts with a test that reproduces the bug.
  If a change has no test, expect to be asked for one.
- **Deterministic and explainable.** Detection and ranking must not depend on an
  LLM, on the wall clock, or on unseeded randomness. CI runs the suite a second
  time under a different `PYTHONHASHSEED`, so **never depend on set/dict
  iteration order** — sort explicitly where order matters.
- **Honest confidence.** Confidence numbers are either omitted (rank + evidence)
  or *measured on held-out data* — never hand-tuned. If you touch calibration,
  the out-of-fold reliability must still be reported, not asserted.
- **Few dependencies on purpose.** The engine uses only `polars`, `duckdb`,
  `networkx`, and `pydantic`. A new runtime dependency needs a strong reason in
  the PR description (this is why, e.g., Snowflake's `pyarrow`-pulling driver is
  not exercised in CI).
- **Evidence before explanation.** Every root-cause claim carries the observable
  facts that support it — keep that contract when you extend detection or RCA.

## Pull requests

1. **Branch** off `main` (`feat/…`, `fix/…`, `docs/…`, `chore/…`).
2. **Keep it focused** — one logical change per PR is much easier to review.
3. **Green CI** — `pytest`, the determinism pass, `ruff`, and (for UI changes)
   the web job must pass. Run them locally first.
4. **Update docs** in the same PR — the README, the relevant `docs/*.md`, and a
   `CHANGELOG.md` entry under `## [Unreleased]`.
5. **Commit messages** follow a light [Conventional
   Commits](https://www.conventionalcommits.org/) style — `feat:`, `fix:`,
   `docs:`, `test:`, `chore:`, `ci:` — with an optional scope, e.g.
   `feat(warehouse): add BigQuery dialect`.
6. **Link the issue** the PR addresses (`Closes #NN`).

## Releases

Releases are cut by the maintainer: bump the version in `pyproject.toml`, move
the `CHANGELOG.md` entries from `## [Unreleased]` into a versioned section, and
push a `vX.Y.Z` tag. The `Release` workflow builds, publishes to PyPI via trusted
publishing, and creates the GitHub Release. You don't need to do any of this for
a normal contribution.

## Questions

Open an issue with the question — that keeps answers discoverable for the next
person.
