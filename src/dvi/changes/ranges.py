"""Resolve the commit range to derive change events over.

Precedence: explicit config value -> GitHub Actions env -> a sane default.
Pure over an injected env mapping so it is testable without the real environment.
"""

from __future__ import annotations

from collections.abc import Mapping


def resolve_range(
    env: Mapping[str, str],
    base: str | None = None,
    head: str | None = None,
) -> tuple[str | None, str]:
    resolved_base = base or env.get("GITHUB_BASE_REF") or "HEAD~1"
    resolved_head = head or env.get("GITHUB_SHA") or "HEAD"
    return resolved_base, resolved_head
