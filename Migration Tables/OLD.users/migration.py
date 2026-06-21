#!/usr/bin/env python3
"""Migrate data from MySQL `qitech.users` to Postgres `public.users`.

This migration requires a target role UUID supplied via `DEFAULT_USER_ROLE_ID`.
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
PG_DB = os.getenv("PG_DB", "postgres")

DEFAULT_USER_ROLE_ID = 'c07a186f-0248-44b9-bca6-cb7f46f903ac';
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "1000"))


def fetch_mysql_rows(connection, offset: int, limit: int) -> List[Dict[str, Any]]:
    with connection.cursor() as cur:
        cur.execute(
            "SELECT id, job_id, position_id, is_registered, registration_no, location_regulatory_body_id, country_of_practice, first_name, surname, mobile_no, email, password, password_updated_at, email_verified_at, remember_token, created_at, updated_at, is_archived, is_active, is_suspended, selected_head_office_id, last_login_at, last_login_location_id, is_email_hidden, is_phone_hidden, block_comment, dob, middlename, registration_number, last_form_id FROM users ORDER BY id LIMIT %s OFFSET %s",
            (limit, offset),
        )
        return cur.fetchall()


def get_existing_emails(pg_conn) -> set:
    with pg_conn.cursor() as cur:
        cur.execute("SELECT email FROM public.users WHERE email IS NOT NULL")
        return {row[0] for row in cur.fetchall()}


def parse_bool(value: Any) -> bool:
    if value in (1, "1", True, "t", "true", "True"):
        return True
    return False


def parse_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def transform_row(row: Dict[str, Any]) -> Dict[str, Any]:
    if DEFAULT_USER_ROLE_ID is None:
        raise RuntimeError("DEFAULT_USER_ROLE_ID environment variable must be set for user migration")

    first_name = row.get("first_name")
    surname = row.get("surname")
    email = row.get("email")
    password_hash = row.get("password")

    if not first_name or not surname or not email:
        raise ValueError(f"Missing required user fields in row: {row!r}")

    created_at = row.get("created_at") or datetime.now(timezone.utc)
    updated_at = row.get("updated_at") or datetime.now(timezone.utc)
    external_id = parse_int(row.get("id"))
    deleted_at = created_at if parse_bool(row.get("is_archived")) else None

    return {
        'external_id': external_id,
        'first_name': first_name,
        'middle_name': row.get("middlename"),
        'surname': surname,
        'date_of_birth': row.get("dob"),
        'email': email,
        'is_email_hidden': parse_bool(row.get("is_email_hidden")),
        'email_verified_at': row.get("email_verified_at"),
        'password_hash': password_hash,
        'password_reset_at': row.get("password_updated_at"),
        'phone_number': row.get("mobile_no"),
        'is_phone_number_hidden': parse_bool(row.get("is_phone_hidden")),
        'photo': None,
        '"status"': 'active',
        'status_comment': None,
        'role_id': DEFAULT_USER_ROLE_ID,
        'created_at': created_at,
        'updated_at': updated_at,
        'deleted_at': deleted_at,
        'pseudonymized_at': None,
    }


def insert_batch(pg_conn, rows: List[Dict[str, Any]]):
    if not rows:
        return
    cols = [
        'external_id',
        'first_name',
        'middle_name',
        'surname',
        'date_of_birth',
        'email',
        'is_email_hidden',
        'email_verified_at',
        'password_hash',
        'password_reset_at',
        'phone_number',
        'is_phone_number_hidden',
        'photo',
        '"status"',
        'status_comment',
        'role_id',
        'created_at',
        'updated_at',
        'deleted_at',
        'pseudonymized_at',
    ]
    template = "(%s)" % ",".join(["%s"] * len(cols))
    values = [
        (
            r['external_id'],
            r['first_name'],
            r['middle_name'],
            r['surname'],
            r['date_of_birth'],
            r['email'],
            r['is_email_hidden'],
            r['email_verified_at'],
            r['password_hash'],
            r['password_reset_at'],
            r['phone_number'],
            r['is_phone_number_hidden'],
            r['photo'],
            r['"status"'],
            r['status_comment'],
            r['role_id'],
            r['created_at'],
            r['updated_at'],
            r['deleted_at'],
            r['pseudonymized_at'],
        )
        for r in rows
    ]

    sql = (
        "INSERT INTO public.users (" +
        ",".join(cols) + ") VALUES %s ON CONFLICT (email) DO UPDATE SET external_id = COALESCE(public.users.external_id, EXCLUDED.external_id)"
    )

    with pg_conn.cursor() as cur:
        psycopg2.extras.execute_values(cur, sql, values, template=template)
    pg_conn.commit()


def main(dry_run: bool = False):
    if DEFAULT_USER_ROLE_ID is None:
        raise RuntimeError("DEFAULT_USER_ROLE_ID environment variable must be set for user migration")

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
