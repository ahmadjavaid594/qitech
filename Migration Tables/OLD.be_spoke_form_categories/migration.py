#!/usr/bin/env python3
"""Migrate MySQL `be_spoke_form_categories` to Postgres `public.categories`.

The source reference_id identifies the legacy head office/company. Categories are
inserted with category type `form`.
"""
import os
import sys
import logging
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
PG_DB = os.getenv("PG_DB", "qitech_migration")

# Batch size for fetching/inserting
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "1000"))


def parse_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def fetch_mysql_rows(connection, offset: int, limit: int) -> List[Dict[str, Any]]:
    with connection.cursor() as cur:
        cur.execute(
            """
            SELECT id, name, reference_type, reference_id
            FROM be_spoke_form_categories
            ORDER BY id
            LIMIT %s OFFSET %s
            """,
            (limit, offset),
        )
        return cur.fetchall()


def build_company_map(pg_conn) -> Dict[int, str]:
    company_map: Dict[int, str] = {}
    with pg_conn.cursor() as cur:
        cur.execute("SELECT id::text, external_id FROM public.companies WHERE external_id IS NOT NULL")
        for company_id, external_id in cur.fetchall():
            old_company_id = parse_int(external_id)
            if old_company_id is not None:
                company_map[old_company_id] = company_id
    return company_map


def transform_row(row: Dict[str, Any], company_map: Dict[int, str]) -> Dict[str, Any]:
    name = str(row.get("name") or "").strip()
    if not name:
        raise ValueError("category name is missing")

    reference_type = str(row.get("reference_type") or "").strip().lower()
    if reference_type not in {"head_office", "company"}:
        raise ValueError(f"unsupported reference_type {row.get('reference_type')!r}")

    old_company_id = parse_int(row.get("reference_id"))
    company_id = company_map.get(old_company_id) if old_company_id is not None else None
    if company_id is None:
        raise ValueError(f"no company found for reference_id {row.get('reference_id')!r}")

    source_id = parse_int(row.get("id"))
    return {
        "company_id": company_id,
        "name": name,
        "type": "form",
        "position": source_id or 0,
    }


def insert_batch(pg_conn, rows: List[Dict[str, Any]]):
    if not rows:
        return 0

    # Prevent duplicate conflict keys within one execute_values statement.
    unique_rows = {
        (r["company_id"], r["type"], r["name"]): r
        for r in rows
    }
    rows = list(unique_rows.values())

    cols = ["company_id", '"name"', '"type"', '"position"']
    template = "(%s)" % ",".join(["%s"] * len(cols))
    values = [
        (
            r["company_id"],
            r["name"],
            r["type"],
            r["position"],
        )
        for r in rows
    ]

    sql = (
        "INSERT INTO public.categories (" +
        ",".join(cols) + ") VALUES %s "
        'ON CONFLICT (company_id, type, name) DO UPDATE SET "position" = EXCLUDED."position"'
    )

    with pg_conn.cursor() as cur:
        psycopg2.extras.execute_values(cur, sql, values, template=template)
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
        company_map = build_company_map(pg_conn)
        logging.info("Loaded %d company mappings from Postgres", len(company_map))

        offset = 0
        total_inserted = 0
        while True:
            rows = fetch_mysql_rows(mysql_conn, offset, BATCH_SIZE)
            if not rows:
                break

            transformed = []
            for r in rows:
                try:
                    transformed.append(transform_row(r, company_map))
                except ValueError as exc:
                    logging.warning("Skipping source category id=%r: %s", r.get("id"), exc)
                    continue

            if dry_run:
                logging.info("Dry-run: would upsert %d rows for offset %d", len(transformed), offset)
            else:
                inserted = insert_batch(pg_conn, transformed)
                total_inserted += inserted
                logging.info("Upserted %d rows (offset %d)", inserted, offset)

            offset += BATCH_SIZE

        logging.info("Done. Total upserted: %d", total_inserted)

    finally:
        mysql_conn.close()
        pg_conn.close()


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    main(dry_run=dry)
