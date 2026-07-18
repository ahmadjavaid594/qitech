#!/usr/bin/env python3
"""Migrate data from MySQL `qitech.dmd_ampps` to Postgres `public.dmd_actual_medicinal_product_packs`.

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
PG_DB = os.getenv("PG_DB", "qitech_migration")
# Batch size for fetching/inserting
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "1000"))


def fetch_mysql_rows(connection, offset: int, limit: int) -> List[Dict[str, Any]]:
    with connection.cursor() as cur:
        cur.execute(
            "SELECT appid, apid, vppid, name, legal_catcd, disccd, discdt, created_at, updated_at "
            "FROM dmd_ampps ORDER BY appid LIMIT %s OFFSET %s",
            (limit, offset),
        )
        return cur.fetchall()


def get_existing_external_ids(pg_conn) -> set:
    with pg_conn.cursor() as cur:
        cur.execute("SELECT external_id FROM public.dmd_actual_medicinal_product_packs WHERE external_id IS NOT NULL")
        return {row[0] for row in cur.fetchall()}


def parse_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_smallint(value: Any) -> int | None:
    parsed = parse_int(value)
    if parsed is None:
        return None
    if -32768 <= parsed <= 32767:
        return parsed
    return None


def transform_row(row: Dict[str, Any]) -> Dict[str, Any]:
    external_id = parse_int(row.get("appid"))
    actual_medicinal_product_id = parse_int(row.get("apid"))
    virtual_medicinal_product_pack_id = parse_int(row.get("vppid"))
    legal_cat_code = parse_smallint(row.get("legal_catcd"))
    disc_code = parse_smallint(row.get("disccd"))

    if external_id is None:
        raise ValueError(f"Missing or invalid APPID value for external_id: {row.get('appid')!r}")
    if actual_medicinal_product_id is None:
        raise ValueError(f"Missing or invalid APID value for actual_medicinal_product_id: {row.get('apid')!r}")

    created_at = row.get("created_at") or datetime.now(timezone.utc)

    return {
        "external_id": external_id,
        "release_version": "migrated",
        "invalid": False,
        "actual_medicinal_product_id": actual_medicinal_product_id,
        "virtual_medicinal_product_pack_id": virtual_medicinal_product_pack_id,
        "name": row.get("name"),
        "legal_cat_code": legal_cat_code,
        "disc_code": disc_code,
        "disc_date": row.get("discdt"),
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
        "actual_medicinal_product_id",
        "virtual_medicinal_product_pack_id",
        '"name"',
        "legal_cat_code",
        "disc_code",
        "disc_date",
        "created_at",
    ]
    template = "(%s)" % ",".join(["%s"] * len(cols))
    values = [
        (
            r["external_id"],
            None,
            r["release_version"],
            r["invalid"],
            r["actual_medicinal_product_id"],
            r["virtual_medicinal_product_pack_id"],
            r["name"],
            r["legal_cat_code"],
            r["disc_code"],
            r["disc_date"],
            r["created_at"],
        )
        for r in rows
    ]

    sql = (
        "INSERT INTO public.dmd_actual_medicinal_product_packs (" +
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
