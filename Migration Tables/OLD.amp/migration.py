#!/usr/bin/env python3
"""Migrate data from MySQL `amp` table to Postgres `dmd_actual_medicinal_products`.

Set connection details via environment variables or edit the defaults below.
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

PG_HOST = os.getenv("PG_HOST", "qitech-pg-test-17943.postgres.database.azure.com")
PG_PORT = int(os.getenv("PG_PORT", "5432"))
PG_USER = os.getenv("PG_USER", "zuhair")
PG_PASSWORD = os.getenv("PG_PASSWORD", "a47faf48e403c78d8729cbd2bf7181cf")
PG_DB = os.getenv("PG_DB", "qi-tech")

# Batch size for fetching/inserting
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "1000"))


def fetch_mysql_rows(connection, offset: int, limit: int) -> List[Dict[str, Any]]:
    with connection.cursor() as cur:
        cur.execute(
            "SELECT id, VPID, APID, NM, created_at, updated_at, `DESC` FROM amp ORDER BY id LIMIT %s OFFSET %s",
            (limit, offset),
        )
        return cur.fetchall()


def get_existing_external_ids(pg_conn) -> set:
    with pg_conn.cursor() as cur:
        cur.execute("SELECT external_id FROM public.dmd_actual_medicinal_products WHERE external_id IS NOT NULL")
        return {row[0] for row in cur.fetchall()}


def transform_row(row: Dict[str, Any]) -> Dict[str, Any]:
    # Mapping decisions:
    # - old `APID` -> `external_id`
    # - old `VPID` -> `virtual_medicinal_product_id`
    # - old `id` -> `supplier_code`
    # - old `NM` -> `name`
    # - try to parse `DESC` as smallint for `lic_auth_code`, otherwise NULL
    lic_auth_code = None
    desc = row.get("DESC")
    try:
        if desc is not None:
            lic_auth_code = int(desc)
            # clamp to smallint
            if lic_auth_code < -32768 or lic_auth_code > 32767:
                lic_auth_code = None
    except Exception:
        lic_auth_code = None

    return {
        "external_id": int(row["APID"]) if row.get("APID") is not None else None,
        "release_version": "migrated",
        "invalid": False,
        "virtual_medicinal_product_id": int(row["VPID"]) if row.get("VPID") is not None else None,
        "name": row.get("NM"),
        "supplier_code": None,
        "lic_auth_code": lic_auth_code,
        "created_at": row.get("created_at"),
    }


def insert_batch(pg_conn, rows: List[Dict[str, Any]]):
    if not rows:
        return
    cols = [
        "external_id",
        "release_version",
        "invalid",
        "virtual_medicinal_product_id",
        '"name"',
        "supplier_code",
        "lic_auth_code",
        "created_at",
    ]
    template = "(%s)" % ",".join(["%s"] * len(cols))
    values = [
        (
            r["external_id"],
            r["release_version"],
            r["invalid"],
            r["virtual_medicinal_product_id"],
            r["name"],
            r["supplier_code"],
            r["lic_auth_code"],
            r["created_at"],
        )
        for r in rows
    ]

    sql = (
        "INSERT INTO public.dmd_actual_medicinal_products (" + 
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
