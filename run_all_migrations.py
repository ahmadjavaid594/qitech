#!/usr/bin/env python3
"""Run every migration.py script under the Migration Tables folder."""

from __future__ import annotations

import argparse
import subprocess
import sys
from collections import deque
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
DEFAULT_BASE_DIR = ROOT_DIR / "Migration Tables"


def normalize_script_key(script_path: Path, base_dir: Path) -> str:
    return script_path.parent.relative_to(base_dir).as_posix()


def build_dependency_map() -> dict[str, set[str]]:
    return {
        "OLD.head_offices": set(),
        "OLD.user_type_categories": {"OLD.head_offices"},
        "OLD.location_types": set(),
        "OLD.location_regulatory_bodies": set(),
        "OLD.users": set(),
        "OLD.location": {"OLD.head_offices", "OLD.location_types", "OLD.location_regulatory_bodies"},
        "OLD.head_office_users": {"OLD.head_offices", "OLD.users"},
        "OLD.head_office_user_timings": {"OLD.head_office_users"},
        "OLD.head_office_holidays": {"OLD.head_office_users"},
        "OLD.head_office_cases": {"OLD.head_office_users"},
        "OLD.dmd_vtms": set(),
        "OLD.dmd_vmp": {"OLD.dmd_vtms"},
        "OLD.dmd_vmp_drug_forms": {"OLD.dmd_vmp"},
        "OLD.dmd_vmp_routes": {"OLD.dmd_vmp"},
        "OLD.dmd_vmp_control_drug_info": {"OLD.dmd_vmp"},
        "OLD.dmd_ingredients": set(),
        "OLD.dmd_vmp_ingredients": {"OLD.dmd_vmp", "OLD.dmd_ingredients"},
        "OLD.dmd_legal_category": set(),
        "OLD.dmd_control_drug_categories": set(),
        "OLD.dmd_drug_forms": set(),
        "OLD.dmd_routes": set(),
        "OLD.dmd_suppliers": set(),
        "OLD.dmd_unit_of_measures": set(),
        "OLD.dmd_vmpps": {"OLD.dmd_vmp"},
        "OLD.amp": {"OLD.dmd_vmp", "OLD.dmd_vmpps"},
        "OLD.dmd_ampps": {"OLD.amp", "OLD.dmd_vmpps"},
    }


def find_migration_scripts(base_dir: Path) -> list[Path]:
    discovered_paths = sorted(base_dir.rglob("migration.py"))
    if not discovered_paths:
        return []

    script_keys = {
        normalize_script_key(script_path, base_dir): script_path for script_path in discovered_paths
    }
    dependency_map = build_dependency_map()

    dependencies = {key: set() for key in script_keys}
    for key, deps in dependency_map.items():
        if key in dependencies:
            dependencies[key].update(dep for dep in deps if dep in script_keys)

    reverse_dependencies = {key: set() for key in script_keys}
    for key, deps in dependencies.items():
        for dep in deps:
            reverse_dependencies[dep].add(key)

    indegree = {key: len(dependencies[key]) for key in script_keys}
    ready = deque(sorted([key for key, degree in indegree.items() if degree == 0]))
    ordered_keys: list[str] = []

    while ready:
        current = ready.popleft()
        ordered_keys.append(current)

        for dependent in sorted(reverse_dependencies[current]):
            indegree[dependent] -= 1
            if indegree[dependent] == 0:
                ready.append(dependent)

        if len(ready) > 1:
            ready = deque(sorted(ready))

    if len(ordered_keys) != len(script_keys):
        return discovered_paths

    return [script_keys[key] for key in ordered_keys]


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
