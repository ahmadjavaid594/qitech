#!/usr/bin/env python3
"""Migrate data from MySQL `qitech.dmd_vmp_drug_forms` to Postgres `public.dmd_virtual_medicinal_product_forms`.

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
            "SELECT vpid, `form_cd`, created_at FROM dmd_vmp_drug_forms ORDER BY id LIMIT %s OFFSET %s",
            (limit, offset),
        )
        return cur.fetchall()


def get_virtual_product_map(pg_conn) -> Dict[int, str]:
    with pg_conn.cursor() as cur:
        cur.execute(
            "SELECT external_id, id FROM public.dmd_virtual_medicinal_products WHERE external_id IS NOT NULL"
        )
        return {int(row[0]): row[1] for row in cur.fetchall()}


def get_existing_form_pairs(pg_conn) -> set:
    with pg_conn.cursor() as cur:
        cur.execute(
            "SELECT virtual_medicinal_product_id, form_code FROM public.dmd_virtual_medicinal_product_forms"
        )
        return {(row[0], int(row[1])) for row in cur.fetchall()}


def parse_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def transform_row(row: Dict[str, Any], virtual_product_map: Dict[int, str]) -> Dict[str, Any]:
    source_vpid = row.get("vpid")
    vpid_int = parse_int(source_vpid)
    if vpid_int is None:
        raise ValueError(f"Missing or invalid vpid value: {source_vpid!r}")

    virtual_medicinal_product_id = virtual_product_map.get(vpid_int)
    if virtual_medicinal_product_id is None:
        raise ValueError(
            f"No target virtual_medicinal_product_id found for vpid external_id {vpid_int!r}"
        )

    form_code = parse_int(row.get("form_cd"))
    if form_code is None:
        raise ValueError(f"Missing or invalid form_cd value: {row.get('form_cd')!r}")

    created_at = row.get("created_at") or datetime.now(timezone.utc)

    return {
        "virtual_medicinal_product_id": virtual_medicinal_product_id,
        "form_code": form_code,
        "created_at": created_at,
    }


def insert_batch(pg_conn, rows: List[Dict[str, Any]]):
    if not rows:
        return
    cols = ["virtual_medicinal_product_id", "form_code", "created_at"]
    template = "(%s)" % ",".join(["%s"] * len(cols))
    values = [
        (
            r["virtual_medicinal_product_id"],
            r["form_code"],
            r["created_at"],
        )
        for r in rows
    ]

    sql = (
        "INSERT INTO public.dmd_virtual_medicinal_product_forms (" +
        ",".join(cols) + ") VALUES %s ON CONFLICT (virtual_medicinal_product_id, form_code) DO NOTHING"
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
        virtual_product_map = get_virtual_product_map(pg_conn)
        logging.info("Loaded %d virtual product mappings from Postgres", len(virtual_product_map))
        existing_pairs = get_existing_form_pairs(pg_conn)
        logging.info("Found %d existing form pairs in Postgres", len(existing_pairs))

        offset = 0
        total_inserted = 0
        while True:
            rows = fetch_mysql_rows(mysql_conn, offset, BATCH_SIZE)
            if not rows:
                break

            transformed = []
            for r in rows:
                t = transform_row(r, virtual_product_map)
                pair = (t["virtual_medicinal_product_id"], t["form_code"])
                if pair in existing_pairs:
                    continue
                transformed.append(t)
                existing_pairs.add(pair)

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
