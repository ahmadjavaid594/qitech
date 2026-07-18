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

# Temporarily skip only the forms migration.
SKIPPED_MIGRATIONS = {
    "OLD.forms",
}

# These scripts either ignore --dry-run or do not accept it. Never invoke them
# from a dry run, because doing so would write to the destination database.
DRY_RUN_UNSUPPORTED = {
    "OLD.forms",
    "OLD.head_office_cases",
}


MIGRATION_ORDER = [
    # Core identities / tenants
    "OLD.roles",
    "OLD.head_offices",
    "OLD.head_office_orginisation_levels",
    "OLD.head_office_orginisation_groups",
    "OLD.users",
    "OLD.location_regulatory_bodies",
    "OLD.location_types",
    "OLD.location",
    "OLD.location_tags",
    "OLD.head_office_users",
    "OLD.user_jobs",
    "OLD.user_type_categories",
    "OLD.be_spoke_form_categories",
    "OLD.permissions",
    "OLD.user_job_assigns",
    # Forms and cases depend on companies/users/company_users being present.
    "OLD.forms",
    "OLD.head_office_cases",
    "OLD.case_handler_users",
    "OLD.head_office_user_timings",
    "OLD.head_office_holidays",
    # DMD reference/import tables
    "OLD.dmd_control_drug_categories",
    "OLD.dmd_drug_forms",
    "OLD.dmd_ingredients",
    "OLD.dmd_legal_category",
    "OLD.dmd_routes",
    "OLD.dmd_suppliers",
    "OLD.dmd_unit_of_measures",
    "OLD.dmd_vtms",
    "OLD.dmd_vmp",
    "OLD.dmd_vmpps",
    "OLD.dmd_vmp_drug_forms",
    "OLD.dmd_vmp_routes",
    "OLD.dmd_vmp_control_drug_info",
    "OLD.dmd_vmp_ingredients",
    "OLD.amp",
    "OLD.dmd_amps",
    "OLD.dmd_ampps",
]

ORDER_PRIORITY = {key: index for index, key in enumerate(MIGRATION_ORDER)}


def normalize_script_key(script_path: Path, base_dir: Path) -> str:
    return script_path.parent.relative_to(base_dir).as_posix()


def build_dependency_map() -> dict[str, set[str]]:
    return {
        # Core identities / tenants
        "OLD.roles": set(),
        "OLD.head_offices": set(),
        "OLD.head_office_orginisation_levels": {"OLD.head_offices"},
        "OLD.head_office_orginisation_groups": {"OLD.head_offices"},
        "OLD.users": {"OLD.roles"},
        "OLD.location_regulatory_bodies": set(),
        "OLD.location_types": set(),
        "OLD.location": {"OLD.head_offices", "OLD.location_types", "OLD.location_regulatory_bodies"},
        "OLD.location_tags": {"OLD.head_offices", "OLD.location"},
        "OLD.head_office_users": {"OLD.head_offices", "OLD.users"},
        "OLD.user_jobs": {"OLD.head_offices"},
        "OLD.user_type_categories": {"OLD.head_offices"},
        "OLD.be_spoke_form_categories": {"OLD.head_offices"},
        "OLD.permissions": {"OLD.roles", "OLD.head_offices", "OLD.users", "OLD.head_office_users"},
        "OLD.user_job_assigns": {
            "OLD.users",
            "OLD.head_offices",
            "OLD.location",
            "OLD.head_office_users",
            "OLD.user_jobs",
            "OLD.location_regulatory_bodies",
        },

        # Forms and cases
        "OLD.forms": {
            "OLD.head_offices",
            "OLD.users",
            "OLD.location",
            "OLD.head_office_users",
            "OLD.be_spoke_form_categories",
            "OLD.head_office_orginisation_groups",
        },
        # This migration builds case templates directly from the legacy forms
        # tables; it does not consume the output of OLD.forms.
        "OLD.head_office_cases": {"OLD.head_offices", "OLD.head_office_users"},
        "OLD.case_handler_users": {"OLD.head_office_cases", "OLD.head_office_users"},
        "OLD.head_office_user_timings": {"OLD.head_office_users"},
        "OLD.head_office_holidays": {"OLD.head_offices", "OLD.users", "OLD.head_office_users"},

        # DMD lookup/import tables
        "OLD.dmd_control_drug_categories": set(),
        "OLD.dmd_drug_forms": set(),
        "OLD.dmd_ingredients": set(),
        "OLD.dmd_legal_category": set(),
        "OLD.dmd_routes": set(),
        "OLD.dmd_suppliers": set(),
        "OLD.dmd_unit_of_measures": set(),
        "OLD.dmd_vtms": set(),
        "OLD.dmd_vmp": {"OLD.dmd_vtms"},
        "OLD.dmd_vmpps": {"OLD.dmd_vmp", "OLD.dmd_unit_of_measures"},
        "OLD.dmd_vmp_drug_forms": {"OLD.dmd_vmp", "OLD.dmd_drug_forms"},
        "OLD.dmd_vmp_routes": {"OLD.dmd_vmp", "OLD.dmd_routes"},
        "OLD.dmd_vmp_control_drug_info": {"OLD.dmd_vmp", "OLD.dmd_control_drug_categories"},
        "OLD.dmd_vmp_ingredients": {"OLD.dmd_vmp", "OLD.dmd_ingredients"},
        "OLD.amp": {"OLD.dmd_vmp"},
        "OLD.dmd_amps": {"OLD.dmd_vmp", "OLD.dmd_suppliers"},
        "OLD.dmd_ampps": {"OLD.dmd_amps", "OLD.dmd_vmpps", "OLD.dmd_legal_category"},
    }


def sort_migration_keys(keys) -> list[str]:
    return sorted(keys, key=lambda key: (ORDER_PRIORITY.get(key, len(ORDER_PRIORITY)), key))


def find_migration_scripts(base_dir: Path, include_skipped: set[str] | None = None) -> list[Path]:
    include_skipped = include_skipped or set()
    all_discovered_paths = sorted(base_dir.rglob("migration.py"))
    discovered_paths = [
        script_path
        for script_path in all_discovered_paths
        if normalize_script_key(script_path, base_dir) not in SKIPPED_MIGRATIONS
        or normalize_script_key(script_path, base_dir) in include_skipped
    ]
    if not discovered_paths:
        return []

    script_keys = {
        normalize_script_key(script_path, base_dir): script_path for script_path in discovered_paths
    }
    dependency_map = build_dependency_map()

    undeclared = sorted(set(script_keys) - set(dependency_map))
    if undeclared:
        raise ValueError(
            "Migration dependencies are not declared for: " + ", ".join(undeclared)
        )

    all_discovered_keys = {
        normalize_script_key(script_path, base_dir) for script_path in all_discovered_paths
    }
    skipped_prerequisites = {
        key: sorted(dep for dep in dependency_map[key] if dep in all_discovered_keys - set(script_keys))
        for key in script_keys
    }
    skipped_prerequisites = {
        key: deps for key, deps in skipped_prerequisites.items() if deps
    }
    if skipped_prerequisites:
        details = "; ".join(
            f"{key} requires {', '.join(deps)}"
            for key, deps in sorted(skipped_prerequisites.items())
        )
        raise ValueError(f"Required migrations are skipped: {details}")

    dependencies = {key: set() for key in script_keys}
    for key, deps in dependency_map.items():
        if key in dependencies:
            dependencies[key].update(dep for dep in deps if dep in script_keys)

    reverse_dependencies = {key: set() for key in script_keys}
    for key, deps in dependencies.items():
        for dep in deps:
            reverse_dependencies[dep].add(key)

    indegree = {key: len(dependencies[key]) for key in script_keys}
    ready = deque(sort_migration_keys([key for key, degree in indegree.items() if degree == 0]))
    ordered_keys: list[str] = []

    while ready:
        current = ready.popleft()
        ordered_keys.append(current)

        for dependent in sort_migration_keys(reverse_dependencies[current]):
            indegree[dependent] -= 1
            if indegree[dependent] == 0:
                ready.append(dependent)

        if len(ready) > 1:
            ready = deque(sort_migration_keys(ready))

    if len(ordered_keys) != len(script_keys):
        cyclic_keys = sort_migration_keys(
            key for key, degree in indegree.items() if degree > 0
        )
        raise ValueError(
            "Migration dependency cycle detected involving: " + ", ".join(cyclic_keys)
        )

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


def filter_scripts(
    scripts: list[Path],
    base_dir: Path,
    start_at: str | None = None,
    only: str | None = None,
) -> list[Path]:
    if only:
        filtered = [script for script in scripts if normalize_script_key(script, base_dir) == only]
        if not filtered:
            raise ValueError(f"Migration key not found for --only: {only}")
        return filtered

    if not start_at:
        return scripts

    for index, script in enumerate(scripts):
        if normalize_script_key(script, base_dir) == start_at:
            return scripts[index:]

    raise ValueError(f"Migration key not found for --start-at: {start_at}")


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
    failure_group = parser.add_mutually_exclusive_group()
    failure_group.add_argument(
        "--stop-on-failure",
        dest="stop_on_failure",
        action="store_true",
        help="Stop after the first failure (default).",
    )
    failure_group.add_argument(
        "--continue-on-failure",
        dest="stop_on_failure",
        action="store_false",
        help="Continue with independent migrations after a failure.",
    )
    parser.set_defaults(stop_on_failure=True)
    parser.add_argument(
        "--list",
        action="store_true",
        help="Print the resolved migration order without running any scripts.",
    )
    parser.add_argument(
        "--start-at",
        help="Start from a migration key such as OLD.forms and continue through the remaining sequence.",
    )
    parser.add_argument(
        "--only",
        help="Run only one migration key such as OLD.forms.",
    )
    args = parser.parse_args()

    base_dir = Path(args.base_dir).expanduser().resolve()
    if not base_dir.exists():
        print(f"Base directory does not exist: {base_dir}", file=sys.stderr)
        return 2

    include_skipped = {args.only} if args.only else set()
    try:
        scripts = find_migration_scripts(base_dir, include_skipped=include_skipped)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if not scripts:
        print(f"No migration.py files found under: {base_dir}", file=sys.stderr)
        return 1
    try:
        scripts = filter_scripts(scripts, base_dir, args.start_at, args.only)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if args.list:
        for index, script_path in enumerate(scripts, start=1):
            print(f"{index:02d}. {normalize_script_key(script_path, base_dir)}")
        if SKIPPED_MIGRATIONS - include_skipped:
            print("\nSkipped by configuration:")
            for key in sort_migration_keys(SKIPPED_MIGRATIONS - include_skipped):
                print(f" - {key}")
        return 0

    if args.dry_run:
        unsupported = [
            normalize_script_key(script, base_dir)
            for script in scripts
            if normalize_script_key(script, base_dir) in DRY_RUN_UNSUPPORTED
        ]
        if unsupported:
            print(
                "Dry run aborted because these migrations do not safely support --dry-run: "
                + ", ".join(unsupported),
                file=sys.stderr,
            )
            return 2

    extra_args = ["--dry-run"] if args.dry_run else []
    failures: list[tuple[Path, int]] = []
    attempted = 0
    succeeded = 0

    for script_path in scripts:
        attempted += 1
        exit_code = run_migration(script_path, extra_args)
        if exit_code != 0:
            failures.append((script_path, exit_code))
            print(f"Migration failed: {script_path} (exit code {exit_code})", file=sys.stderr)
            if args.stop_on_failure:
                break
        else:
            succeeded += 1

    print("\nSummary")
    print("-------")
    print(f"Selected {len(scripts)} migration script(s).")
    print(f"Attempted {attempted}; completed {succeeded} successfully.")
    if attempted < len(scripts):
        print(f"Not attempted after failure: {len(scripts) - attempted}.")
    if failures:
        print(f"Failed {len(failures)} script(s).", file=sys.stderr)
        for script_path, exit_code in failures:
            print(f" - {script_path.relative_to(ROOT_DIR)}: exit code {exit_code}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
