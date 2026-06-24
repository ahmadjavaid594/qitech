#!/usr/bin/env python3
"""Migrate data from MySQL `qitech.location_regulatory_bodies` to Postgres `public.regulatory_bodies`.

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


def parse_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def normalize_name(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized if normalized else None


def normalize_lookup_key(value: Any) -> str | None:
    normalized = normalize_name(value)
    return normalized.lower() if normalized else None


def fetch_mysql_rows(connection, offset: int, limit: int) -> List[Dict[str, Any]]:
    with connection.cursor() as cur:
        cur.execute(
            "SELECT id, name, country, regulatory, created_at, updated_at FROM location_regulatory_bodies ORDER BY id LIMIT %s OFFSET %s",
            (limit, offset),
        )
        return cur.fetchall()


def get_existing_names(pg_conn) -> set:
    with pg_conn.cursor() as cur:
        cur.execute("SELECT name FROM public.regulatory_bodies")
        return {row[0].lower() for row in cur.fetchall() if row[0] is not None}


def build_country_map(pg_conn) -> Dict[str, str]:
    with pg_conn.cursor() as cur:
        cur.execute("SELECT id, name FROM public.countries WHERE name IS NOT NULL")
        return {str(row[1]).strip().lower(): str(row[0]) for row in cur.fetchall() if row[1] is not None}


def transform_row(row: Dict[str, Any], country_map: Dict[str, str]) -> Dict[str, Any]:
    name = normalize_name(row.get("name"))
    if not name:
        raise ValueError("Source location_regulatory_bodies row is missing name")

    country = normalize_lookup_key(row.get("country"))
    country_id = country_map.get(country) if country else None
    if country and country_id is None:
        logging.warning("Country not found in public.countries: %s", row.get("country"))

    external_id = parse_int(row.get("id"))
    created_at = row.get("created_at") or datetime.now(timezone.utc)
    updated_at = row.get("updated_at") or datetime.now(timezone.utc)

    return {
        "external_id": external_id,
        "name": name,
        "country_id": country_id,
        "registration_number_regex": normalize_name(row.get("regulatory")),
        "created_at": created_at,
        "updated_at": updated_at,
    }


def insert_batch(pg_conn, rows: List[Dict[str, Any]]):
    if not rows:
        return

    cols = [
        "external_id",
        '"name"',
        "country_id",
        "registration_number_regex",
        "created_at",
        "updated_at",
    ]
    template = "(%s)" % ",".join(["%s"] * len(cols))
    values = [
        (
            r["external_id"],
            r["name"],
            r["country_id"],
            r["registration_number_regex"],
            r["created_at"],
            r["updated_at"],
        )
        for r in rows
    ]

    sql = (
        "INSERT INTO public.regulatory_bodies (" + 
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
        existing_names = get_existing_names(pg_conn)
        country_map = build_country_map(pg_conn)
        logging.info("Found %d existing regulatory_bodies names in Postgres", len(existing_names))
        logging.info("Loaded %d countries from Postgres", len(country_map))

        offset = 0
        total_inserted = 0
        while True:
            rows = fetch_mysql_rows(mysql_conn, offset, BATCH_SIZE)
            if not rows:
                break

            transformed = []
            for r in rows:
                t = transform_row(r, country_map)
                if t["name"].lower() in existing_names:
                    continue
                transformed.append(t)
                existing_names.add(t["name"].lower())

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
