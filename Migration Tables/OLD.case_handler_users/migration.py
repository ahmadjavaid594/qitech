#!/usr/bin/env python3
"""Migrate old case_handler_users rows into public.case_handlers.

The migration resolves:
- head_office_user_id -> public.company_users.id by matching company_users.external_id
- case_id -> public.cases.id by matching cases.external_id
"""
import os
import sys
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

try:
    import pymysql.cursors
    import psycopg2
    import psycopg2.extras
except Exception as e:
    logging.error("Missing Python dependency: %s", e)
    logging.error("Install dependencies: pip install pymysql psycopg2-binary")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# Config
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

BATCH_SIZE = int(os.getenv("BATCH_SIZE", "1000"))


def fetch_mysql_rows(connection, offset: int, limit: int) -> List[Dict[str, Any]]:
    with connection.cursor() as cur:
        cur.execute(
            """
            SELECT id, head_office_user_id, case_id, created_at, updated_at,
                   master_stage_handler, deleted_at, is_hidden
            FROM case_handler_users
            ORDER BY id
            LIMIT %s OFFSET %s
            """,
            (limit, offset),
        )
        return cur.fetchall()


def build_target_maps(pg_conn) -> Tuple[Dict[str, str], Dict[str, str]]:
    company_user_map: Dict[str, str] = {}
    case_map: Dict[str, str] = {}

    with pg_conn.cursor() as cur:
        cur.execute("SELECT id, external_id FROM public.company_users WHERE external_id IS NOT NULL")
        for row in cur.fetchall():
            company_user_map[str(row[1])] = str(row[0])

        cur.execute("SELECT id, external_id FROM public.cases WHERE external_id IS NOT NULL")
        for row in cur.fetchall():
            case_map[str(row[1])] = str(row[0])

    return company_user_map, case_map


def transform_row(row: Dict[str, Any], company_user_map: Dict[str, str], case_map: Dict[str, str]) -> Dict[str, Any]:
    head_office_user_id = str(row.get("head_office_user_id"))
    case_id = str(row.get("case_id"))

    company_user_id = company_user_map.get(head_office_user_id)
    if not company_user_id:
        raise ValueError(f"No company_user found for head_office_user_id {head_office_user_id}")

    case_uuid = case_map.get(case_id)
    if not case_uuid:
        raise ValueError(f"No case found for case_id {case_id}")

    created_at = row.get("created_at") or row.get("updated_at") or datetime.now(timezone.utc)

    return {
        "case_id": case_uuid,
        "company_user_id": company_user_id,
        "created_at": created_at,
    }


def insert_batch(pg_conn, rows: List[Dict[str, Any]]) -> int:
    if not rows:
        return 0

    values = [
        (r["case_id"], r["company_user_id"], r["created_at"])
        for r in rows
    ]

    sql = """
        INSERT INTO public.case_handlers (case_id, company_user_id, created_at)
        VALUES %s
        ON CONFLICT (case_id, company_user_id) DO NOTHING
    """

    with pg_conn.cursor() as cur:
        psycopg2.extras.execute_values(cur, sql, values)
    pg_conn.commit()
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
    pg_conn = psycopg2.connect(host=PG_HOST, port=PG_PORT, user=PG_USER, password=PG_PASSWORD, dbname=PG_DB)

    try:
        company_user_map, case_map = build_target_maps(pg_conn)
        logging.info(
            "Loaded %d company_user mappings and %d case mappings from Postgres",
            len(company_user_map),
            len(case_map),
        )

        offset = 0
        total_inserted = 0
        while True:
            rows = fetch_mysql_rows(mysql_conn, offset, BATCH_SIZE)
            if not rows:
                break

            transformed = []
            for row in rows:
                try:
                    transformed.append(transform_row(row, company_user_map, case_map))
                except ValueError as exc:
                    logging.warning("Skipping row due to error: %s", exc)
                    continue

            if dry_run:
                logging.info("Dry-run: would insert %d rows for offset %d", len(transformed), offset)
            else:
                inserted = insert_batch(pg_conn, transformed)
                total_inserted += inserted
                logging.info("Inserted %d rows (offset %d)", inserted, offset)

            offset += BATCH_SIZE

        logging.info("Done. Total inserted: %d", total_inserted)

    finally:
        mysql_conn.close()
        pg_conn.close()


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    main(dry_run=dry)
