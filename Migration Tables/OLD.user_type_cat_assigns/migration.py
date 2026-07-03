#!/usr/bin/env python3
"""Migrate data from MySQL `qitech.user_type_cat_assigns` to Postgres `public.user_type_categories`.

This migration resolves source `user_type_id` via `public.user_types.external_id`
and resolves source `user_type_category_id` to `public.categories.id` using the
category name, head office/company mapping, and type `user_type`.
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

PG_HOST = os.getenv("PG_HOST", "qitech-pg-test-17943.postgres.database.azure.com")
PG_PORT = int(os.getenv("PG_PORT", "5432"))
PG_USER = os.getenv("PG_USER", "zuhair")
PG_PASSWORD = os.getenv("PG_PASSWORD", "a47faf48e403c78d8729cbd2bf7181cf")
PG_DB = os.getenv("PG_DB", "qi-tech")

BATCH_SIZE = int(os.getenv("BATCH_SIZE", "1000"))

HEAD_OFFICE_OVERRIDES = {
    36: "23b59048-99aa-4609-9fd4-2d4e09bd71cb",  # Qitech
}


def fetch_mysql_rows(connection, offset: int, limit: int) -> List[Dict[str, Any]]:
    with connection.cursor() as cur:
        cur.execute(
            "SELECT a.id, a.user_type_id, a.user_type_category_id, c.name AS category_name, c.head_office_id "
            "FROM user_type_cat_assigns a "
            "JOIN user_type_categories c ON c.id = a.user_type_category_id "
            "ORDER BY a.id LIMIT %s OFFSET %s",
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


def build_target_maps(pg_conn) -> Tuple[Dict[int, str], Dict[tuple, str]]:
    user_type_map: Dict[int, str] = {}
    category_map: Dict[tuple, str] = {}
    with pg_conn.cursor() as cur:
        cur.execute("SELECT id, external_id FROM public.user_types WHERE external_id IS NOT NULL")
        for row in cur.fetchall():
            if row[1] is not None:
                user_type_map[int(row[1])] = row[0]

        cur.execute("SELECT id, company_id, \"name\", type FROM public.categories")
        for row in cur.fetchall():
            category_map[(row[1], row[2], row[3])] = row[0]

    return user_type_map, category_map


def parse_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def transform_row(
    row: Dict[str, Any],
    company_external_map: Dict[int, str],
    company_email_map: Dict[str, str],
    user_type_map: Dict[int, str],
    category_map: Dict[tuple, str],
) -> Dict[str, Any]:
    user_type_id = parse_int(row.get("user_type_id"))
    if user_type_id is None:
        raise ValueError(f"Missing or invalid user_type_id for row: {row!r}")

    category_name = row.get("category_name")
    if not category_name:
        raise ValueError(f"Missing category_name for row: {row!r}")

    headoffice_id = parse_int(row.get("head_office_id"))
    if headoffice_id is None:
        raise ValueError(f"Missing or invalid head_office_id for row: {row!r}")

    company_id = HEAD_OFFICE_OVERRIDES.get(headoffice_id)
    if company_id is None:
        company_id = company_external_map.get(headoffice_id)
    if company_id is None:
        expected_email = f"migrated+{headoffice_id}@example.invalid"
        company_id = company_email_map.get(expected_email)
    if company_id is None:
        raise ValueError(
            f"No company found for head_office_id {headoffice_id} "
            f"(tried external_id and email migrated+{headoffice_id}@example.invalid)"
        )

    target_user_type_id = user_type_map.get(user_type_id)
    if target_user_type_id is None:
        raise ValueError(f"No target user_type found for source user_type_id {user_type_id}")

    category_id = category_map.get((company_id, category_name, "user_type"))
    if category_id is None:
        raise ValueError(
            f"No target category found for name {category_name!r} and company_id {company_id}"
        )

    return {
        "user_type_id": target_user_type_id,
        "category_id": category_id,
    }


def insert_batch(pg_conn, rows: List[Dict[str, Any]]):
    if not rows:
        return

    uniq: Dict[tuple, Dict[str, Any]] = {}
    for r in rows:
        key = (r["user_type_id"], r["category_id"])
        if key not in uniq:
            uniq[key] = r.copy()

    deduped_rows = list(uniq.values())

    cols = ["user_type_id", "category_id"]
    template = "(%s)" % ",".join(["%s"] * len(cols))
    values = [
        (
            r["user_type_id"],
            r["category_id"],
        )
        for r in deduped_rows
    ]

    sql = (
        "INSERT INTO public.user_type_categories (" +
        ",".join(cols) + ") VALUES %s ON CONFLICT (user_type_id, category_id) DO NOTHING"
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
        user_type_map, category_map = build_target_maps(pg_conn)
        logging.info(
            "Loaded %d companies with external_id, %d emails, %d user types, and %d categories from Postgres",
            len(company_external_map),
            len(company_email_map),
            len(user_type_map),
            len(category_map),
        )

        offset = 0
        total_inserted = 0
        while True:
            rows = fetch_mysql_rows(mysql_conn, offset, BATCH_SIZE)
            if not rows:
                break

            transformed = []
            for r in rows:
                try:
                    t = transform_row(r, company_external_map, company_email_map, user_type_map, category_map)
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
