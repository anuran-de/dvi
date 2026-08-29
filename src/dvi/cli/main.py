"""The `dvi` command-line entrypoint.

`dvi analyze --config dvi.toml --output-dir <dir>`:
load + validate config, analyze the before/after snapshot, render the Markdown
and JSON reports, and return an exit code the CI gate reads (0 clean/below
threshold, 1 gate tripped, 2 could-not-run).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from .config import DviConfig, DviError, load_config
from .gate import gate_failed
from .render import render_json, render_markdown
from .sources import incident_from_config


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dvi", description="Data Versioning Intelligence")
    sub = parser.add_subparsers(dest="command", required=True)
    analyze = sub.add_parser("analyze", help="Analyze a before/after snapshot and report.")
    analyze.add_argument("--config", default="dvi.toml", help="Path to the dvi.toml config.")
    analyze.add_argument("--output-dir", default=".", help="Directory for report artifacts.")
    analyze.add_argument("--source-before", help="Override the file source 'before' path.")
    analyze.add_argument("--source-after", help="Override the file source 'after' path.")
    return parser


def _apply_overrides(config: DviConfig, args: argparse.Namespace) -> DviConfig:
    if args.source_before is None and args.source_after is None:
        return config
    if config.source.kind != "file":
        raise DviError("--source-before/--source-after apply only to a file source")
    if args.source_before is not None:
        config.source.before = args.source_before
    if args.source_after is not None:
        config.source.after = args.source_after
    return config


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        config = load_config(args.config)
        config = _apply_overrides(config, args)
        incident = incident_from_config(config)

        failed = gate_failed(incident.severity if incident else None, config.gate.fail_on)
        markdown = render_markdown(
            incident, asset=config.asset, fail_on=config.gate.fail_on, gate_failed=failed
        )
        payload = render_json(
            incident,
            asset=config.asset,
            fail_on=config.gate.fail_on,
            gate_failed=failed,
            generated_at=datetime.now(UTC),
        )

        out_dir = Path(args.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "dvi-report.md").write_text(markdown, encoding="utf-8")
        (out_dir / "dvi-report.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except DviError as e:
        print(f"dvi: error: {e}", file=sys.stderr)
        return 2
    except OSError as e:
        print(f"dvi: error: could not write report to {args.output_dir}: {e}", file=sys.stderr)
        return 2

    print(markdown)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
