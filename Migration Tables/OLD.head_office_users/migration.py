#!/usr/bin/env python3
"""Migrate data from MySQL `qitech.head_office_users` to Postgres `public.company_users`.

This migration requires:
- `public.users` pre-populated
- `public.companies` pre-populated
- DEFAULT_COMPANY_ROLE_ID environment variable set (UUID of default role)
- Uses hardcoded mapping of old head_office_id to new company UUID
"""
import os
import sys
import logging
from datetime import datetime, timezone
from typing import Dict, List, Any

try:
    import pymysql.cursors
    import psycopg2
    import psycopg2.extras
except Exception as e:
    logging.error("Missing Python dependency: %s", e)
    logging.error("Install dependencies: pip install pymysql psycopg2-binary")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# Configuration
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

DEFAULT_COMPANY_ROLE_ID ='eb89681c-0605-4abe-b7d2-0546f517823d'
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "1000"))


def fetch_mysql_rows(connection, offset: int, limit: int) -> List[Dict[str, Any]]:
    with connection.cursor() as cur:
        cur.execute(
            "SELECT id, user_id, head_office_id, `level`, created_at, updated_at, `position`, work_status, `location`, about_me, is_active, is_blocked, block_comment, do_not_disturb, deleted_at FROM head_office_users ORDER BY id LIMIT %s OFFSET %s",
            (limit, offset),
        )
        return cur.fetchall()


def build_user_id_map(pg_conn) -> Dict[int, str]:
    """Map source user_id (int) → target user.id (uuid) using users.external_id."""
    mapping: Dict[int, str] = {}
    with pg_conn.cursor() as cur:
        cur.execute("SELECT id, external_id FROM public.users WHERE external_id IS NOT NULL")
        for row in cur.fetchall():
            uid = row[0]
            ext = row[1]
            try:
                mapping[int(ext)] = str(uid)
            except (TypeError, ValueError):
                continue
    return mapping


def build_company_id_map(pg_conn) -> Dict[int, str]:
    """Map source head_office_id (int) → target company.id (uuid) using companies.external_id."""
    mapping: Dict[int, str] = {}
    with pg_conn.cursor() as cur:
        cur.execute("SELECT id, external_id FROM public.companies WHERE external_id IS NOT NULL")
        for row in cur.fetchall():
            cid = row[0]
            ext = row[1]
            try:
                mapping[int(ext)] = str(cid)
            except (TypeError, ValueError):
                continue
    return mapping


def get_existing_pairs(pg_conn) -> set:
    """Get existing user_id, company_id pairs to avoid duplicates"""
    with pg_conn.cursor() as cur:
        cur.execute("SELECT user_id, company_id FROM public.company_users")
        return {(str(row[0]), str(row[1])) for row in cur.fetchall()}


def parse_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_bool(value: Any) -> bool:
    if value in (1, "1", True, "t", "true", "True"):
        return True
    return False


def transform_row(row: Dict[str, Any], user_map: Dict[int, str], company_map: Dict[int, str]) -> Dict[str, Any]:
    if DEFAULT_COMPANY_ROLE_ID is None:
        raise RuntimeError("DEFAULT_COMPANY_ROLE_ID environment variable must be set")

    user_id_src = parse_int(row.get("user_id"))
    if user_id_src is None:
        raise ValueError(f"Missing or invalid user_id: {row.get('user_id')!r}")

    head_office_id_src = parse_int(row.get("head_office_id"))
    if head_office_id_src is None:
        raise ValueError(f"Missing or invalid head_office_id: {row.get('head_office_id')!r}")

    user_id = user_map.get(user_id_src)
    if user_id is None:
        raise ValueError(f"No target user found for source user_id {user_id_src}")

    company_id = company_map.get(head_office_id_src)
    if company_id is None:
        raise ValueError(f"No target company found for source head_office_id {head_office_id_src}")

    position = row.get("position") or "Staff"
    created_at = row.get("created_at") or datetime.now(timezone.utc)
    updated_at = row.get("updated_at") or datetime.now(timezone.utc)
    deleted_at = row.get("deleted_at")
    status = 'inactive' if deleted_at or parse_bool(row.get("is_blocked")) else 'active'

    return {
        'external_id': parse_int(row.get("id")),
        'user_id': user_id,
        'company_id': company_id,
        'company_role_id': DEFAULT_COMPANY_ROLE_ID,
        '"position"': position,
        '"location"': row.get("location"),
        'about': row.get("about_me"),
        'photo': None,
        'invited_by_company_id': None,
        'invited_by_user_id': None,
        '"status"': status,
        'status_comment': row.get("block_comment"),
        'display_message': None,
        'work_environment_id': None,
        '"work_status"': 'away',
        'timezone': None,
        'pin_hash': None,
        'created_at': created_at,
        'updated_at': updated_at,
        'start_date': None,
        'end_date': deleted_at.date() if deleted_at else None,
        'is_role_active': not parse_bool(row.get("is_blocked")),
    }


def insert_batch(pg_conn, rows: List[Dict[str, Any]]):
    if not rows:
        return
    cols = [
        'external_id',
        'user_id', 'company_id', 'company_role_id', '"position"', '"location"', 'about', 'photo',
        'invited_by_company_id', 'invited_by_user_id', '"status"', 'status_comment', 'display_message',
        'work_environment_id', '"work_status"', 'timezone', 'pin_hash', 'created_at', 'updated_at',
        'start_date', 'end_date', 'is_role_active',
    ]
    template = "(%s)" % ",".join(["%s"] * len(cols))
    values = [
        (
            r['external_id'],
            r['user_id'], r['company_id'], r['company_role_id'], r['"position"'], r['"location"'], r['about'], r['photo'],
            r['invited_by_company_id'], r['invited_by_user_id'], r['"status"'], r['status_comment'], r['display_message'],
            r['work_environment_id'], r['"work_status"'], r['timezone'], r['pin_hash'], r['created_at'], r['updated_at'],
            r['start_date'], r['end_date'], r['is_role_active'],
        )
        for r in rows
    ]

    sql = (
        "INSERT INTO public.company_users (" +
        ",".join(cols) + ") VALUES %s ON CONFLICT (user_id, company_id) DO UPDATE SET external_id = COALESCE(public.company_users.external_id, EXCLUDED.external_id)"
    )

    with pg_conn.cursor() as cur:
        psycopg2.extras.execute_values(cur, sql, values, template=template)
    pg_conn.commit()


def main(dry_run: bool = False):
    if DEFAULT_COMPANY_ROLE_ID is None:
        raise RuntimeError("DEFAULT_COMPANY_ROLE_ID environment variable must be set")

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
        user_map = build_user_id_map(pg_conn)
        company_map = build_company_id_map(pg_conn)
        existing_pairs = get_existing_pairs(pg_conn)
        logging.info("Loaded %d users, %d companies, %d existing pairs", len(user_map), len(company_map), len(existing_pairs))

        offset = 0
        total_inserted = 0
        while True:
            rows = fetch_mysql_rows(mysql_conn, offset, BATCH_SIZE)
            if not rows:
                break

            transformed = []
            for r in rows:
                try:
                    t = transform_row(r, user_map, company_map)
                    pair = (t['user_id'], t['company_id'])
                    if pair in existing_pairs:
                        continue
                    transformed.append(t)
                    existing_pairs.add(pair)
                except ValueError as e:
                    logging.warning("Skipping row: %s", e)
                    continue

            if dry_run:
                logging.info("Dry-run: would insert %d rows for offset %d", len(transformed), offset)
            else:
                insert_batch(pg_conn, transformed)
                total_inserted += len(transformed)
                logging.info("Inserted %d rows (offset %d)", len(transformed), offset)

            offset += BATCH_SIZE

        logging.info("Done. Total inserted: %d", total_inserted)

    finally:
        mysql_conn.close()
        pg_conn.close()


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    main(dry_run=dry)

