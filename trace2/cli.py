from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .analyzer import Analyzer
from .config import ConfigError, load_config_bundle


def analyze_command(args: argparse.Namespace) -> int:
    try:
        config = load_config_bundle(Path(args.config))
    except ConfigError as exc:
        print(f"Config error: {exc}")
        return 2

    try:
        analyzer = Analyzer(config, Path(args.cache_dir))
        analyzer.analyze(Path(args.out))
    except Exception as exc:
        print(f"Analysis error: {exc}")
        return 1
    print(f"Run completed: {args.out}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="trace2")
    subparsers = parser.add_subparsers(dest="command", required=True)

    analyze = subparsers.add_parser("analyze", help="Run Trace2 analysis")
    analyze.add_argument("--config", required=True, help="Config directory")
    analyze.add_argument("--out", required=True, help="Output run folder")
    analyze.add_argument("--cache-dir", required=True, help="Cache directory")
    analyze.set_defaults(func=analyze_command)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
