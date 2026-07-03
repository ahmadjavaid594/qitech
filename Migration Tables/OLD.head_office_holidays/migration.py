#!/usr/bin/env python3
"""Migrate data from MySQL `qitech.head_office_user_timings` to Postgres `public.company_user_work_schedules`.

This migration requires:
- `public.users` pre-populated
- `public.companies` pre-populated
- `public.company_users` already migrated
- Uses hardcoded mapping of old head_office_id to new company UUID
"""
import os
import sys
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

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

BATCH_SIZE = int(os.getenv("BATCH_SIZE", "1000"))


def fetch_mysql_rows(connection, offset: int, limit: int) -> List[Dict[str, Any]]:
    with connection.cursor() as cur:
        cur.execute(
            "SELECT h.id, h.head_office_user_id, h.away_from, h.return_on, h.total_days, h.type, h.linked_api_holiday_id, h.created_at, h.updated_at, hu.user_id, hu.head_office_id " +
            "FROM head_office_user_holidays h " +
            "JOIN head_office_users hu ON hu.id = h.head_office_user_id " +
            "ORDER BY h.id LIMIT %s OFFSET %s",
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


def build_company_user_map(pg_conn):
    """Return two maps:
    - external_map: source head_office_user id (external_id) -> company_users.id
    - pair_map: (user_id, company_id) -> company_users.id (fallback)
    """
    external_map: Dict[int, str] = {}
    pair_map: Dict[tuple[str, str], str] = {}
    with pg_conn.cursor() as cur:
        cur.execute("SELECT id, external_id, user_id, company_id FROM public.company_users")
        for row in cur.fetchall():
            cid = row[0]
            ext = row[1]
            uid = row[2]
            comp = row[3]
            if ext is not None:
                try:
                    external_map[int(ext)] = str(cid)
                except (TypeError, ValueError):
                    pass
            pair_map[(str(uid), str(comp))] = str(cid)
    return external_map, pair_map


def parse_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_date(value: Any):
    if value is None:
        return None
    return value


# holidays use simple from/to dates; no schedule arrays required


def transform_row(row: Dict[str, Any], user_map: Dict[int, str], company_map: Dict[int, str], company_user_external_map: Dict[int, str], company_user_pair_map: Dict[tuple[str, str], str]) -> Dict[str, Any]:
    # Find company_user by head_office_user_id (source) via external_id, or fallback to (user_id, company_id)
    company_user_src_id = parse_int(row.get("head_office_user_id"))
    company_user_id = None
    if company_user_src_id is not None:
        company_user_id = company_user_external_map.get(company_user_src_id)

    # If we don't have direct mapping, try pair lookup using user and company mappings
    if company_user_id is None:
        user_id_src = parse_int(row.get("user_id"))
        head_office_id_src = parse_int(row.get("head_office_id"))
        if user_id_src is None or head_office_id_src is None:
            raise ValueError(f"Missing user_id or head_office_id for row: {row!r}")
        user_id = user_map.get(user_id_src)
        company_id = company_map.get(head_office_id_src)
        if user_id is None or company_id is None:
            raise ValueError(f"No target user/company for source ids user:{user_id_src} company:{head_office_id_src}")
        company_user_id = company_user_pair_map.get((user_id, company_id))

    if company_user_id is None:
        raise ValueError(f"No target company_user found for source head_office_user_id {company_user_src_id}")

    created_at = row.get("created_at") or datetime.now(timezone.utc)
    updated_at = row.get("updated_at") or datetime.now(timezone.utc)

    return {
        'company_user_id': company_user_id,
        'from': parse_date(row.get("away_from")),
        'to': parse_date(row.get("return_on")),
        'reason': row.get("type"),
        'created_at': created_at,
        'updated_at': updated_at,
    }


def insert_batch(pg_conn, rows: List[Dict[str, Any]]):
    if not rows:
        return

    cols = ['company_user_id', '"to"', '"from"', 'reason', 'created_at', 'updated_at']
    template = "(%s)" % ",".join(["%s"] * len(cols))
    values = [
        (
            r['company_user_id'],
            r['to'],
            r['from'],
            r.get('reason'),
            r['created_at'],
            r['updated_at'],
        )
        for r in rows
    ]

    sql = (
        "INSERT INTO public.company_user_leaves (" +
        ",".join(cols) + ") VALUES %s ON CONFLICT (company_user_id, \"to\", \"from\") DO NOTHING"
    )

    with pg_conn.cursor() as cur:
        psycopg2.extras.execute_values(cur, sql, values, template=template)
    pg_conn.commit()


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
        user_map = build_user_id_map(pg_conn)
        company_map = build_company_id_map(pg_conn)
        company_user_external_map, company_user_pair_map = build_company_user_map(pg_conn)
        logging.info("Loaded %d users, %d companies, %d company_user rows", len(user_map), len(company_map), len(company_user_pair_map))

        offset = 0
        total_inserted = 0
        while True:
            rows = fetch_mysql_rows(mysql_conn, offset, BATCH_SIZE)
            if not rows:
                break

            transformed = []
            for r in rows:
                try:
                    t = transform_row(r, user_map, company_map, company_user_external_map, company_user_pair_map)
                    transformed.append(t)
                except ValueError as e:
                    logging.warning("Skipping row %s: %s", r.get("id"), e)
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
