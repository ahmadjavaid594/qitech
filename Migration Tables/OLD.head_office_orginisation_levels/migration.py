#!/usr/bin/env python3
"""Migrate MySQL head-office organisation levels to Postgres org_levels.

The hierarchy is represented by level_number in MySQL and level in Postgres.
Rows are therefore migrated company-by-company in ascending level order.
"""

import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List

try:
    import pymysql.cursors
    import psycopg2
    import psycopg2.extras
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

PG_HOST = os.getenv("PG_HOST", "qitech-pg-test-17943.postgres.database.azure.com")
PG_PORT = int(os.getenv("PG_PORT", "5432"))
PG_USER = os.getenv("PG_USER", "pgadmin")
PG_PASSWORD = os.getenv("PG_PASSWORD", "2fac05f6ac12e581bc2aeb8bc188deac")
PG_DB = os.getenv("PG_DB", "qi-tech")

BATCH_SIZE = int(os.getenv("BATCH_SIZE", "1000"))


def parse_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def fetch_mysql_rows(mysql_conn) -> List[Dict[str, Any]]:
    with mysql_conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, head_office_id, level_number, level_name, created_at, updated_at
            FROM head_office_orginisation_levels
            ORDER BY head_office_id, level_number, id
            """
        )
        return cur.fetchall()


def build_company_map(pg_conn) -> Dict[int, str]:
    company_map: Dict[int, str] = {}
    with pg_conn.cursor() as cur:
        cur.execute(
            """
            SELECT id::text, external_id
            FROM public.companies
            WHERE external_id IS NOT NULL
            """
        )
        for company_id, external_id in cur.fetchall():
            old_company_id = parse_int(external_id)
            if old_company_id is not None:
                company_map[old_company_id] = company_id
    return company_map


def transform_rows(
    source_rows: List[Dict[str, Any]],
    company_map: Dict[int, str],
) -> List[Dict[str, Any]]:
    transformed: List[Dict[str, Any]] = []
    seen_levels: set[tuple[str, int]] = set()
    seen_names: set[tuple[str, str]] = set()
    previous_level_by_company: Dict[str, int] = {}

    for row in source_rows:
        source_id = parse_int(row.get("id"))
        old_company_id = parse_int(row.get("head_office_id"))
        company_id = company_map.get(old_company_id) if old_company_id is not None else None
        if company_id is None:
            logging.warning(
                "Skipping source org level id=%r: no company has external_id=%r",
                source_id,
                old_company_id,
            )
            continue

        level = parse_int(row.get("level_number"))
        if level is None:
            logging.warning("Skipping source org level id=%r: invalid level_number", source_id)
            continue

        name = str(row.get("level_name") or "").strip()
        if not name:
            logging.warning("Skipping source org level id=%r: level_name is empty", source_id)
            continue

        key = (company_id, level)
        if key in seen_levels:
            logging.warning(
                "Skipping duplicate level %s for company external_id=%s (source id=%s)",
                level,
                old_company_id,
                source_id,
            )
            continue

        name_key = (company_id, name.casefold())
        if name_key in seen_names:
            logging.warning(
                "Skipping duplicate level name %r for company external_id=%s (source id=%s)",
                name,
                old_company_id,
                source_id,
            )
            continue

        previous_level = previous_level_by_company.get(company_id)
        if previous_level is not None and level > previous_level + 1:
            logging.warning(
                "Organisation hierarchy gap for company external_id=%s: level %s follows level %s",
                old_company_id,
                level,
                previous_level,
            )

        now = datetime.now(timezone.utc)
        transformed.append(
            {
                "name": name,
                "level": level,
                "company_id": company_id,
                "text_color": None,
                "background_color": None,
                "created_at": row.get("created_at") or now,
                "updated_at": row.get("updated_at") or now,
            }
        )
        seen_levels.add(key)
        seen_names.add(name_key)
        previous_level_by_company[company_id] = level

    return transformed


def upsert_batch(pg_conn, rows: List[Dict[str, Any]]) -> int:
    if not rows:
        return 0

    values = [
        (
            row["name"],
            row["level"],
            row["company_id"],
            row["text_color"],
            row["background_color"],
            row["created_at"],
            row["updated_at"],
        )
        for row in rows
    ]
    sql = """
        INSERT INTO public.org_levels
            (name, level, company_id, text_color, background_color, created_at, updated_at)
        VALUES %s
        ON CONFLICT (level, company_id) DO UPDATE
        SET name = EXCLUDED.name,
            text_color = EXCLUDED.text_color,
            background_color = EXCLUDED.background_color,
            updated_at = EXCLUDED.updated_at
    """

    with pg_conn.cursor() as cur:
        psycopg2.extras.execute_values(
            cur,
            sql,
            values,
            template="(%s, %s, %s, %s, %s, %s, %s)",
        )
    return len(rows)


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
        source_rows = fetch_mysql_rows(mysql_conn)
        rows = transform_rows(source_rows, company_map)
        logging.info(
            "Prepared %d of %d organisation levels across %d mapped companies",
            len(rows),
            len(source_rows),
            len(company_map),
        )

        if dry_run:
            logging.info("Dry-run: would upsert %d organisation levels", len(rows))
            return

        total = 0
        for start in range(0, len(rows), BATCH_SIZE):
            total += upsert_batch(pg_conn, rows[start : start + BATCH_SIZE])
        pg_conn.commit()
        logging.info("Done. Total organisation levels upserted: %d", total)
    except Exception:
        pg_conn.rollback()
        raise
    finally:
        mysql_conn.close()
        pg_conn.close()


if __name__ == "__main__":
    main(dry_run="--dry-run" in sys.argv)
