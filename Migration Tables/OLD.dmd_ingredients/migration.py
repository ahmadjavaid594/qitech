#!/usr/bin/env python3
"""Migrate data from MySQL `qitech.dmd_ingredients` to Postgres `public.dmd_ingredient_substances`.

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
            "SELECT isid, name, created_at, updated_at FROM dmd_ingredients ORDER BY isid LIMIT %s OFFSET %s",
            (limit, offset),
        )
        return cur.fetchall()


def get_existing_external_ids(pg_conn) -> set:
    with pg_conn.cursor() as cur:
        cur.execute("SELECT external_id FROM public.dmd_ingredient_substances WHERE external_id IS NOT NULL")
        return {row[0] for row in cur.fetchall()}


def parse_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def transform_row(row: Dict[str, Any]) -> Dict[str, Any]:
    external_id = parse_int(row.get("isid"))
    if external_id is None:
        raise ValueError(f"Missing or invalid isid value for external_id: {row.get('isid')!r}")

    created_at = row.get("created_at") or datetime.now(timezone.utc)

    return {
        "external_id": external_id,
        "new_id": None,
        "release_version": "migrated",
        "invalid": False,
        "name": row.get("name"),
        "created_at": created_at,
    }


def insert_batch(pg_conn, rows: List[Dict[str, Any]]):
    if not rows:
        return
    cols = [
        "external_id",
        "new_id",
        "release_version",
        "invalid",
        '"name"',
        "created_at",
    ]
    template = "(%s)" % ",".join(["%s"] * len(cols))
    values = [
        (
            r["external_id"],
            r["new_id"],
            r["release_version"],
            r["invalid"],
            r["name"],
            r["created_at"],
        )
        for r in rows
    ]

    sql = (
        "INSERT INTO public.dmd_ingredient_substances (" +
        ",".join(cols) + ") VALUES %s"
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
        existing = get_existing_external_ids(pg_conn)
        logging.info("Found %d existing external_id values in Postgres", len(existing))

        offset = 0
        total_inserted = 0
        while True:
            rows = fetch_mysql_rows(mysql_conn, offset, BATCH_SIZE)
            if not rows:
                break

            transformed = []
            for r in rows:
                t = transform_row(r)
                if t["external_id"] in existing:
                    continue
                transformed.append(t)
                existing.add(t["external_id"])

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
