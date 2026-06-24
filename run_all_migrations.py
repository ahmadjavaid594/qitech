#!/usr/bin/env python3
"""Run every migration.py script under the Migration Tables folder."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
DEFAULT_BASE_DIR = ROOT_DIR / "Migration Tables"


def find_migration_scripts(base_dir: Path) -> list[Path]:
    return sorted(base_dir.rglob("migration.py"))


def run_migration(script_path: Path, extra_args: list[str]) -> int:
    heading = f"Running migration: {script_path.relative_to(ROOT_DIR)}"
    separator = "=" * len(heading)
    print(separator)
    print(heading)
    print(separator)

    completed = subprocess.run(
        [sys.executable, str(script_path), *extra_args],
        cwd=str(script_path.parent),
    )
    return completed.returncode


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run all migration.py files under Migration Tables in sequence.",
    )
    parser.add_argument(
        "--base-dir",
        default=str(DEFAULT_BASE_DIR),
        help="Base directory to search for migration.py files.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Pass --dry-run to each migration script when supported.",
    )
    parser.add_argument(
        "--stop-on-failure",
        action="store_true",
        help="Stop execution if any migration script exits with a non-zero status.",
    )
    args = parser.parse_args()

    base_dir = Path(args.base_dir).expanduser().resolve()
    if not base_dir.exists():
        print(f"Base directory does not exist: {base_dir}", file=sys.stderr)
        return 2

    scripts = find_migration_scripts(base_dir)
    if not scripts:
        print(f"No migration.py files found under: {base_dir}", file=sys.stderr)
        return 1

    extra_args = ["--dry-run"] if args.dry_run else []
    failures: list[tuple[Path, int]] = []

    for script_path in scripts:
        exit_code = run_migration(script_path, extra_args)
        if exit_code != 0:
            failures.append((script_path, exit_code))
            print(f"Migration failed: {script_path} (exit code {exit_code})", file=sys.stderr)
            if args.stop_on_failure:
                break

    print("\nSummary")
    print("-------")
    print(f"Found {len(scripts)} migration script(s).")
    print(f"Completed {len(scripts) - len(failures)} successfully.")
    if failures:
        print(f"Failed {len(failures)} script(s).", file=sys.stderr)
        for script_path, exit_code in failures:
            print(f" - {script_path.relative_to(ROOT_DIR)}: exit code {exit_code}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
