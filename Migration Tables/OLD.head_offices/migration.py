#!/usr/bin/env python3
"""Migrate data from MySQL `qitech.head_offices` to Postgres `public.companies`.

Set connection details via environment variables or edit the defaults below.
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
    logging.error("Or create a virtualenv and run: pip install -r requirements.txt")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# Configuration (prefer environment variables)
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

# Batch size for fetching/inserting
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "1000"))


def fetch_mysql_rows(connection, offset: int, limit: int) -> List[Dict[str, Any]]:
    with connection.cursor() as cur:
        cur.execute(
            "SELECT id, company_name, address, telephone_no, email, sites_count, created_at, updated_at FROM head_offices ORDER BY id LIMIT %s OFFSET %s",
            (limit, offset),
        )
        return cur.fetchall()


def get_existing_emails(pg_conn) -> set:
    with pg_conn.cursor() as cur:
        cur.execute("SELECT email FROM public.companies WHERE email IS NOT NULL")
        return {row[0] for row in cur.fetchall()}


def parse_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def transform_row(row: Dict[str, Any]) -> Dict[str, Any]:
    # Use company_name -> name, telephone_no -> phone_number, email required in target
    name = row.get("company_name")
    if not name:
        raise ValueError(f"Missing company_name for row: {row!r}")

    email = row.get("email")
    if not email:
        # generate placeholder unique email using source id
        email = f"migrated+{row.get('id')}@example.invalid"

    phone = row.get("telephone_no")
    address = row.get("address")
    estimated_site_count = parse_int(row.get("sites_count"))

    external_id = parse_int(row.get("id"))
    created_at = row.get("created_at") or datetime.now(timezone.utc)
    updated_at = row.get("updated_at") or datetime.now(timezone.utc)

    return {
        'external_id': external_id,
        '"name"': name,
        'address': address,
        'email': email,
        'phone_number': phone,
        'estimated_site_count': estimated_site_count,
        'created_at': created_at,
        'updated_at': updated_at,
    }


def insert_batch(pg_conn, rows: List[Dict[str, Any]]):
    if not rows:
        return
    cols = ['external_id', '"name"', 'address', 'email', 'phone_number', 'estimated_site_count', 'created_at', 'updated_at']
    template = "(%s)" % ",".join(["%s"] * len(cols))
    values = [
        (
            r['external_id'],
            r['"name"'],
            r['address'],
            r['email'],
            r['phone_number'],
            r['estimated_site_count'],
            r['created_at'],
            r['updated_at'],
        )
        for r in rows
    ]

    sql = (
        "INSERT INTO public.companies (" +
        ",".join(cols) + ") VALUES %s ON CONFLICT (email) DO UPDATE SET external_id = COALESCE(public.companies.external_id, EXCLUDED.external_id)"
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
        existing = get_existing_emails(pg_conn)
        logging.info("Found %d existing emails in Postgres", len(existing))

        offset = 0
        total_inserted = 0
        while True:
            rows = fetch_mysql_rows(mysql_conn, offset, BATCH_SIZE)
            if not rows:
                break

            transformed = []
            for r in rows:
                t = transform_row(r)
                if t["email"] in existing:
                    continue
                transformed.append(t)
                existing.add(t["email"])

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
