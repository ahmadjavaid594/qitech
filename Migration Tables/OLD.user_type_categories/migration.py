#!/usr/bin/env python3
"""Migrate data from MySQL `qitech.user_type_categories` to Postgres `public.categories`.

This migration expects `public.companies` to have been populated already. It maps
`head_office_id` -> `company_id` by looking up the company email generated during the
`head_offices` migration (migrated+<id>@example.invalid), and stores rows as category
records of type `user_type`.
"""
import os
import sys
import logging
from datetime import datetime, timezone
from typing import Dict, List, Any, Tuple

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
            "SELECT id, name, head_office_id FROM user_type_categories ORDER BY id LIMIT %s OFFSET %s",
            (limit, offset),
        )
        return cur.fetchall()


def build_company_maps(pg_conn) -> Tuple[Dict[int, str], Dict[str, str]]:
    # Build two maps:
    #  - external_map: source head_office id (int) -> companies.id (uuid) via companies.external_id
    #  - email_map: email -> companies.id (uuid) as a fallback (migrated+<id>@example.invalid)
    external_map: Dict[int, str] = {}
    email_map: Dict[str, str] = {}
    with pg_conn.cursor() as cur:
        cur.execute("SELECT id, external_id, email FROM public.companies")
        for row in cur.fetchall():
            cid = row[0]
            ext = row[1]
            email = row[2]
            try:
                if ext is not None:
                    external_map[int(ext)] = cid
            except (TypeError, ValueError):
                pass
            if email:
                email_map[email] = cid
    return external_map, email_map


def parse_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def transform_row(row: Dict[str, Any], company_external_map: Dict[int, str], company_email_map: Dict[str, str]) -> Dict[str, Any]:
    name = row.get("name")
    if not name:
        raise ValueError(f"Missing name in row: {row!r}")

    head_office_id = parse_int(row.get("head_office_id"))
    if head_office_id is None:
        raise ValueError(f"Missing or invalid head_office_id for row: {row!r}")

    # First, try matching by companies.external_id (preferred)
    company_id = company_external_map.get(head_office_id)
    if company_id is None:
        # Fallback to the migrated placeholder email used during companies import
        expected_email = f"migrated+{head_office_id}@example.invalid"
        company_id = company_email_map.get(expected_email)
    if company_id is None:
        raise ValueError(f"No company found for head_office_id {head_office_id} (tried external_id={head_office_id} and email migrated+{head_office_id}@example.invalid)")

    return {
        "company_id": company_id,
        '"name"': name,
        'type': 'user_type',
        'position': 0,
    }


def insert_batch(pg_conn, rows: List[Dict[str, Any]]):
    if not rows:
        return
    # Deduplicate rows that would conflict on (company_id, name) within the same batch.
    uniq: Dict[tuple, Dict[str, Any]] = {}
    for r in rows:
        key = (r["company_id"], r['"name"'])
        if key not in uniq:
            uniq[key] = r.copy()
            continue
        existing = uniq[key]
        # Prefer existing external_id, otherwise take new
        if existing.get("external_id") is None and r.get("external_id") is not None:
            existing["external_id"] = r.get("external_id")
        # created_at: earliest
        if existing.get("created_at") and r.get("created_at"):
            existing["created_at"] = min(existing["created_at"], r["created_at"])
        elif r.get("created_at"):
            existing["created_at"] = r["created_at"]
        # updated_at: latest
        if existing.get("updated_at") and r.get("updated_at"):
            existing["updated_at"] = max(existing["updated_at"], r["updated_at"])
        elif r.get("updated_at"):
            existing["updated_at"] = r["updated_at"]
        # boolean flags: keep True if any row has True
        for bool_field in ['"isSystemGenerated"', 'enabled', 'allow_multiple_sub_types', 'sub_type_selection_required', 'has_regulatory_body']:
            existing[bool_field] = bool(existing.get(bool_field)) or bool(r.get(bool_field))
        # description: prefer existing, else new
        if not existing.get("description") and r.get("description"):
            existing["description"] = r.get("description")

    deduped_rows = list(uniq.values())

    cols = ["company_id", '"name"', 'type', 'position']
    template = "(%s)" % ",".join(["%s"] * len(cols))
    values = [
        (
            r["company_id"],
            r['"name"'],
            r["type"],
            r["position"],
        )
        for r in deduped_rows
    ]

    sql = (
        "INSERT INTO public.categories (" +
        ",".join(cols) + ") VALUES %s ON CONFLICT (company_id, type, \"name\") DO UPDATE SET position = EXCLUDED.position"
    )

    with pg_conn.cursor() as cur:
        psycopg2.extras.execute_values(cur, sql, values, template=template)
    pg_conn.commit()

    return len(deduped_rows)


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
        company_external_map, company_email_map = build_company_maps(pg_conn)
        logging.info("Loaded %d companies with external_id and %d emails from Postgres", len(company_external_map), len(company_email_map))

        offset = 0
        total_inserted = 0
        while True:
            rows = fetch_mysql_rows(mysql_conn, offset, BATCH_SIZE)
            if not rows:
                break

            transformed = []
            for r in rows:
                try:
                    t = transform_row(r, company_external_map, company_email_map)
                except ValueError as e:
                    logging.warning("Skipping row due to error: %s", e)
                    continue
                transformed.append(t)

            if dry_run:
                logging.info("Dry-run: would insert %d rows for offset %d", len(transformed), offset)
            else:
                inserted = insert_batch(pg_conn, transformed)
                total_inserted += int(inserted or 0)
                logging.info("Inserted %d rows (offset %d)", int(inserted or 0), offset)

            offset += BATCH_SIZE

        logging.info("Done. Total inserted: %d", total_inserted)

    finally:
        mysql_conn.close()
        pg_conn.close()


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    main(dry_run=dry)
