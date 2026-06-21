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

PG_HOST = os.getenv("PG_HOST", "localhost")
PG_PORT = int(os.getenv("PG_PORT", "5432"))
PG_USER = os.getenv("PG_USER", "postgres")
PG_PASSWORD = os.getenv("PG_PASSWORD", "postgres")
PG_DB = os.getenv("PG_DB", "postgres")

BATCH_SIZE = int(os.getenv("BATCH_SIZE", "1000"))


def fetch_mysql_rows(connection, offset: int, limit: int) -> List[Dict[str, Any]]:
    with connection.cursor() as cur:
        cur.execute(
            "SELECT ht.id, ht.monday_start_time, ht.monday_end_time, ht.tuesday_start_time, ht.tuesday_end_time, ht.wednesday_start_time, ht.wednesday_end_time, ht.thursday_start_time, ht.thursday_end_time, ht.friday_start_time, ht.friday_end_time, ht.saturday_start_time, ht.saturday_end_time, ht.sunday_start_time, ht.sunday_end_time, ht.is_open_monday, ht.is_open_tuesday, ht.is_open_wednesday, ht.is_open_thursday, ht.is_open_friday, ht.is_open_saturday, ht.is_open_sunday, ht.created_at, ht.updated_at, hu.user_id, hu.head_office_id " +
            "FROM head_office_user_timings ht " +
            "JOIN head_office_users hu ON hu.id = ht.id " +
            "ORDER BY ht.id LIMIT %s OFFSET %s",
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


def parse_time(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "strftime"):
        return value.strftime("%H:%M:%S")
    return str(value)


def parse_bool(value: Any) -> bool:
    return value in (1, "1", True, "t", "true", "True")


def build_schedule_arrays(row: Dict[str, Any]) -> tuple[list[str | None], list[str | None], bool]:
    starts = [
        parse_time(row.get("monday_start_time")),
        parse_time(row.get("tuesday_start_time")),
        parse_time(row.get("wednesday_start_time")),
        parse_time(row.get("thursday_start_time")),
        parse_time(row.get("friday_start_time")),
        parse_time(row.get("saturday_start_time")),
        parse_time(row.get("sunday_start_time")),
    ]
    ends = [
        parse_time(row.get("monday_end_time")),
        parse_time(row.get("tuesday_end_time")),
        parse_time(row.get("wednesday_end_time")),
        parse_time(row.get("thursday_end_time")),
        parse_time(row.get("friday_end_time")),
        parse_time(row.get("saturday_end_time")),
        parse_time(row.get("sunday_end_time")),
    ]
    open_flags = [
        parse_bool(row.get("is_open_monday")),
        parse_bool(row.get("is_open_tuesday")),
        parse_bool(row.get("is_open_wednesday")),
        parse_bool(row.get("is_open_thursday")),
        parse_bool(row.get("is_open_friday")),
        parse_bool(row.get("is_open_saturday")),
        parse_bool(row.get("is_open_sunday")),
    ]

    same_hours = False
    if all(open_flags) and all(starts) and all(ends):
        same_hours = len(set(starts)) == 1 and len(set(ends)) == 1

    return starts, ends, same_hours


def transform_row(row: Dict[str, Any], user_map: Dict[int, str], company_map: Dict[int, str], company_user_external_map: Dict[int, str], company_user_pair_map: Dict[tuple[str, str], str]) -> Dict[str, Any]:
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

    # Prefer direct mapping via company_users.external_id (which holds source head_office_users.id)
    company_user_src_id = parse_int(row.get("id"))
    company_user_id = None
    if company_user_src_id is not None:
        company_user_id = company_user_external_map.get(company_user_src_id)
    # Fallback to mapping by (user_id, company_id)
    if company_user_id is None:
        company_user_id = company_user_pair_map.get((user_id, company_id))
    if company_user_id is None:
        raise ValueError(f"No target company_user row found for source id {company_user_src_id} or pair ({user_id},{company_id})")

    starts, ends, same_hours = build_schedule_arrays(row)
    created_at = row.get("created_at") or datetime.now(timezone.utc)
    updated_at = row.get("updated_at") or datetime.now(timezone.utc)

    return {
        'external_id': parse_int(row.get("id")),
        'company_user_id': company_user_id,
        'from': starts,
        'to': ends,
        'same_hours': same_hours,
        'created_at': created_at,
        'updated_at': updated_at,
    }


def insert_batch(pg_conn, rows: List[Dict[str, Any]]):
    if not rows:
        return

    cols = ['external_id', 'company_user_id', '"from"', '"to"', 'same_hours', 'created_at', 'updated_at']
    template = "(%s)" % ",".join(["%s"] * len(cols))
    values = [
        (
            r['external_id'],
            r['company_user_id'],
            r['from'],
            r['to'],
            r['same_hours'],
            r['created_at'],
            r['updated_at'],
        )
        for r in rows
    ]

    sql = (
        "INSERT INTO public.company_user_work_schedules (" +
        ",".join(cols) + ") VALUES %s ON CONFLICT (company_user_id) DO UPDATE SET external_id = COALESCE(public.company_user_work_schedules.external_id, EXCLUDED.external_id)"
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
