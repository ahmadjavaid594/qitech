#!/usr/bin/env python3
"""Migrate MySQL head-office organisation groups to Postgres org_units."""

import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    import pymysql.cursors
    import psycopg2
except Exception as exc:
    logging.error("Missing Python dependency: %s", exc)
    logging.error("Install dependencies: pip install pymysql psycopg2-binary")
    sys.exit(1)


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

MYSQL_HOST = os.getenv("MYSQL_HOST", "127.0.0.1")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "root")
MYSQL_DB = os.getenv("MYSQL_DB", "qitech")

PG_HOST = os.getenv("PG_HOST", "localhost")
PG_PORT = int(os.getenv("PG_PORT", "5432"))
PG_USER = os.getenv("PG_USER", "postgres")
PG_PASSWORD = os.getenv("PG_PASSWORD", "postgres")
PG_DB = os.getenv("PG_DB", "qitech_migration")


def parse_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def fetch_source_rows(mysql_conn) -> List[Dict[str, Any]]:
    with mysql_conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, head_office_id, parent_id, `group`, created_at, updated_at
            FROM head_office_organisation_groups
            ORDER BY head_office_id, id
            """
        )
        return cur.fetchall()


def build_company_map(pg_conn) -> Dict[int, str]:
    result: Dict[int, str] = {}
    with pg_conn.cursor() as cur:
        cur.execute(
            "SELECT id::text, external_id FROM public.companies WHERE external_id IS NOT NULL"
        )
        for company_id, external_id in cur.fetchall():
            old_company_id = parse_int(external_id)
            if old_company_id is not None:
                result[old_company_id] = company_id
    return result


def load_existing_unit_map(pg_conn) -> Dict[int, str]:
    result: Dict[int, str] = {}
    with pg_conn.cursor() as cur:
        cur.execute(
            """
            SELECT external_id, id::text
            FROM public.org_units
            WHERE external_id IS NOT NULL
            """
        )
        for external_id, unit_id in cur.fetchall():
            old_id = parse_int(external_id)
            if old_id is not None:
                result[old_id] = unit_id
    return result


def prepare_rows(
    source_rows: List[Dict[str, Any]],
    company_map: Dict[int, str],
) -> Dict[int, Dict[str, Any]]:
    prepared: Dict[int, Dict[str, Any]] = {}

    for row in source_rows:
        source_id = parse_int(row.get("id"))
        old_company_id = parse_int(row.get("head_office_id"))
        company_id = company_map.get(old_company_id) if old_company_id is not None else None
        name = str(row.get("group") or "").strip()

        if source_id is None:
            logging.warning("Skipping organisation group with invalid source id: %r", row)
            continue
        if company_id is None:
            logging.warning(
                "Skipping source group id=%s: no company has external_id=%r",
                source_id,
                old_company_id,
            )
            continue
        if not name:
            logging.warning("Skipping source group id=%s: group name is empty", source_id)
            continue

        prepared[source_id] = {
            "external_id": source_id,
            "old_company_id": old_company_id,
            "company_id": company_id,
            "old_parent_id": parse_int(row.get("parent_id")),
            "name": name,
            "created_at": row.get("created_at") or datetime.now(timezone.utc),
            "updated_at": row.get("updated_at") or datetime.now(timezone.utc),
        }

    return prepared


def upsert_unit(pg_conn, row: Dict[str, Any], parent_id: Optional[str]) -> str:
    """Upsert by legacy ID, adopting an existing matching path when necessary."""
    with pg_conn.cursor() as cur:
        cur.execute(
            "SELECT id::text FROM public.org_units WHERE external_id = %s",
            (row["external_id"],),
        )
        existing = cur.fetchone()

        if not existing:
            cur.execute(
                """
                SELECT id::text
                FROM public.org_units
                WHERE company_id = %s
                  AND parent_id IS NOT DISTINCT FROM %s::uuid
                  AND name = %s
                LIMIT 1
                """,
                (row["company_id"], parent_id, row["name"]),
            )
            existing = cur.fetchone()

        if existing:
            unit_id = existing[0]
            cur.execute(
                """
                UPDATE public.org_units
                SET external_id = %s,
                    company_id = %s,
                    parent_id = %s,
                    name = %s,
                    updated_at = %s
                WHERE id = %s
                """,
                (
                    row["external_id"],
                    row["company_id"],
                    parent_id,
                    row["name"],
                    row["updated_at"],
                    unit_id,
                ),
            )
            return unit_id

        cur.execute(
            """
            INSERT INTO public.org_units
                (external_id, company_id, parent_id, name, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id::text
            """,
            (
                row["external_id"],
                row["company_id"],
                parent_id,
                row["name"],
                row["created_at"],
                row["updated_at"],
            ),
        )
        return cur.fetchone()[0]


def migrate_hierarchy(
    pg_conn,
    rows_by_id: Dict[int, Dict[str, Any]],
    unit_map: Dict[int, str],
) -> int:
    pending = dict(rows_by_id)
    processed: set[int] = set()
    migrated = 0

    while pending:
        progressed = False

        for source_id, row in list(pending.items()):
            old_parent_id = row["old_parent_id"]
            if old_parent_id is not None:
                if old_parent_id in rows_by_id and old_parent_id not in processed:
                    continue
                if old_parent_id not in unit_map:
                    continue

            parent_id = unit_map.get(old_parent_id) if old_parent_id is not None else None
            if old_parent_id is not None:
                parent_source = rows_by_id.get(old_parent_id)
                if parent_source and parent_source["company_id"] != row["company_id"]:
                    logging.error(
                        "Skipping source group id=%s: parent %s belongs to another company",
                        source_id,
                        old_parent_id,
                    )
                    del pending[source_id]
                    progressed = True
                    continue

            unit_map[source_id] = upsert_unit(pg_conn, row, parent_id)
            processed.add(source_id)
            del pending[source_id]
            migrated += 1
            progressed = True
            if migrated % 50 == 0:
                logging.info(
                    "Migrated %d organisation groups; %d remaining",
                    migrated,
                    len(pending),
                )

        if progressed:
            continue

        for source_id, row in pending.items():
            parent_id = row["old_parent_id"]
            reason = (
                "missing parent"
                if parent_id not in rows_by_id
                else "cyclic parent relationship"
            )
            logging.error(
                "Could not migrate source group id=%s: %s (parent_id=%r)",
                source_id,
                reason,
                parent_id,
            )
        break

    return migrated


def main(dry_run: bool = False):
    logging.info("Connecting to MySQL %s:%s/%s", MYSQL_HOST, MYSQL_PORT, MYSQL_DB)
    mysql_conn = pymysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        db=MYSQL_DB,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )
    logging.info("Connecting to Postgres %s:%s/%s", PG_HOST, PG_PORT, PG_DB)
    pg_conn = psycopg2.connect(
        host=PG_HOST,
        port=PG_PORT,
        user=PG_USER,
        password=PG_PASSWORD,
        dbname=PG_DB,
    )

    try:
        company_map = build_company_map(pg_conn)
        source_rows = fetch_source_rows(mysql_conn)
        prepared = prepare_rows(source_rows, company_map)
        logging.info(
            "Prepared %d of %d organisation groups",
            len(prepared),
            len(source_rows),
        )

        if dry_run:
            logging.info(
                "Dry-run: would migrate %d groups and resolve their parent relationships",
                len(prepared),
            )
            return

        logging.info("Loading existing organisation-group mappings")
        unit_map = load_existing_unit_map(pg_conn)
        logging.info(
            "Migrating hierarchy (%d existing mappings found)",
            len(unit_map),
        )
        migrated = migrate_hierarchy(pg_conn, prepared, unit_map)
        pg_conn.commit()
        logging.info("Done. Total organisation groups upserted: %d", migrated)
    except Exception:
        pg_conn.rollback()
        raise
    finally:
        mysql_conn.close()
        pg_conn.close()


if __name__ == "__main__":
    main(dry_run="--dry-run" in sys.argv)
