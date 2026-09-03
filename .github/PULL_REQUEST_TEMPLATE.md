<!-- Thanks for contributing to DVI! Keep PRs focused on one logical change. -->

## What & why

<!-- What does this change, and what problem does it solve? -->

Closes #

## How it was verified

<!-- Commands you ran and their result. -->

- [ ] `pytest` passes (incl. the determinism pass under an alternate `PYTHONHASHSEED`)
- [ ] `ruff check .` clean
- [ ] Web changes only: `npm test` / `npm run e2e` pass in `dvi/`

## Checklist

- [ ] New behavior landed **test-first** (a failing test, then the code to pass it)
- [ ] No new runtime dependency — or the PR explains why one is warranted
- [ ] Detection/ranking stays deterministic (no LLM, wall clock, or unseeded randomness in the decision path)
- [ ] Docs updated in this PR (README / `docs/*.md` as relevant)
- [ ] `CHANGELOG.md` entry added under `## [Unreleased]`
