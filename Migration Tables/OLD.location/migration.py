#!/usr/bin/env python3
"""Migrate data from MySQL `qitech.locations` and `qitech.head_office_locations` to Postgres `public.sites`.

Uses `public.companies.external_id` to resolve source head_office_id -> target company UUID.
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


def normalize_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def build_company_map(pg_conn) -> Dict[int, str]:
    with pg_conn.cursor() as cur:
        cur.execute("SELECT id, external_id FROM public.companies WHERE external_id IS NOT NULL")
        mapping: Dict[int, str] = {}
        for row in cur.fetchall():
            try:
                source_id = int(row[1])
            except (TypeError, ValueError):
                continue
            mapping[source_id] = str(row[0])
        return mapping


def build_site_type_map(pg_conn) -> tuple[Dict[int, str], Dict[str, str]]:
    external_map: Dict[int, str] = {}
    name_map: Dict[str, str] = {}
    with pg_conn.cursor() as cur:
        cur.execute("SELECT id, external_id, name FROM public.site_types")
        for row in cur.fetchall():
            target_id = str(row[0])
            external_id = row[1]
            name = row[2]
            if external_id is not None:
                try:
                    external_map[int(external_id)] = target_id
                except (TypeError, ValueError):
                    pass
            if name is not None:
                normalized = str(name).strip().lower()
                if normalized:
                    name_map[normalized] = target_id
    return external_map, name_map


def build_regulatory_body_map(pg_conn) -> tuple[Dict[int, str], Dict[str, str]]:
    external_map: Dict[int, str] = {}
    name_map: Dict[str, str] = {}
    with pg_conn.cursor() as cur:
        cur.execute("SELECT id, external_id, name FROM public.regulatory_bodies")
        for row in cur.fetchall():
            target_id = str(row[0])
            external_id = row[1]
            name = row[2]
            if external_id is not None:
                try:
                    external_map[int(external_id)] = target_id
                except (TypeError, ValueError):
                    pass
            if name is not None:
                normalized = str(name).strip().lower()
                if normalized:
                    name_map[normalized] = target_id
    return external_map, name_map


def get_existing_emails(pg_conn) -> set:
    with pg_conn.cursor() as cur:
        cur.execute("SELECT email FROM public.sites WHERE email IS NOT NULL")
        return {str(row[0]).strip().lower() for row in cur.fetchall() if row[0] is not None}


def fetch_mysql_rows(connection, offset: int, limit: int) -> List[Dict[str, Any]]:
    with connection.cursor() as cur:
        cur.execute(
            "SELECT l.id AS location_id, l.location_type_id, lt.id AS location_type_external_id, lt.name AS location_type_name, l.location_regulatory_body_id, lrb.id AS regulatory_body_external_id, lrb.name AS regulatory_body_name, l.registered_company_name, l.trading_name, l.username, l.registration_no, l.address_line1, l.address_line2, l.town, l.county, l.country, l.postcode, l.telephone_no, l.email, l.password, l.email_verified_at, l.is_active, l.created_at, l.updated_at, l.deleted_at, l.org_code, hol.head_office_id FROM locations l LEFT JOIN location_types lt ON lt.id = l.location_type_id LEFT JOIN location_regulatory_bodies lrb ON lrb.id = l.location_regulatory_body_id LEFT JOIN head_office_locations hol ON hol.location_id = l.id ORDER BY l.id LIMIT %s OFFSET %s",
            (limit, offset),
        )
        return cur.fetchall()


def fetch_mysql_lookup_map(connection, table_name: str) -> Dict[int, str]:
    with connection.cursor() as cur:
        cur.execute(f"SELECT id, name FROM {table_name} WHERE name IS NOT NULL")
        return {int(row[0]): str(row[1]).strip() for row in cur.fetchall() if row[0] is not None and row[1] is not None}


def transform_row(
    row: Dict[str, Any],
    company_map: Dict[int, str],
    site_type_external_map: Dict[int, str],
    site_type_name_map: Dict[str, str],
    regulatory_body_external_map: Dict[int, str],
    regulatory_body_name_map: Dict[str, str],
) -> Dict[str, Any]:
    head_office_id = row.get("head_office_id")
    if head_office_id is None:
        raise ValueError(f"Missing head_office_id for location {row.get('location_id')}")

    try:
        company_id = company_map[int(head_office_id)]
    except (TypeError, ValueError, KeyError):
        raise ValueError(f"Unable to resolve company for head_office_id {head_office_id}")

    type_id = None
    location_type_external_id = row.get("location_type_external_id")
    if location_type_external_id is not None:
        try:
            type_id = site_type_external_map.get(int(location_type_external_id))
        except (TypeError, ValueError):
            type_id = None
    if type_id is None:
        source_type_name = normalize_text(row.get("location_type_name"))
        if source_type_name:
            type_id = site_type_name_map.get(source_type_name.lower())
        if type_id is None and row.get("location_type_id") is not None:
            logging.warning(
                "Missing target site_types row for location_type_id %s / external_id %s / name %s",
                row.get("location_type_id"),
                location_type_external_id,
                row.get("location_type_name"),
            )

    regulatory_body_id = None
    regulatory_body_external_id = row.get("regulatory_body_external_id")
    if regulatory_body_external_id is not None:
        try:
            regulatory_body_id = regulatory_body_external_map.get(int(regulatory_body_external_id))
        except (TypeError, ValueError):
            regulatory_body_id = None
    if regulatory_body_id is None:
        source_reg_name = normalize_text(row.get("regulatory_body_name"))
        if source_reg_name:
            regulatory_body_id = regulatory_body_name_map.get(source_reg_name.lower())
        if regulatory_body_id is None and row.get("location_regulatory_body_id") is not None:
            logging.warning(
                "Missing target regulatory_bodies row for location_regulatory_body_id %s / external_id %s / name %s",
                row.get("location_regulatory_body_id"),
                regulatory_body_external_id,
                row.get("regulatory_body_name"),
            )

    email = normalize_text(row.get("email"))
    if not email:
        raise ValueError(f"Missing email for location {row.get('location_id')}")

    registered_name = normalize_text(row.get("registered_company_name")) or ""
    trading_name = normalize_text(row.get("trading_name")) or ""
    username = normalize_text(row.get("username")) or ""
    postal_code = normalize_text(row.get("postcode"))
    address_line_1 = normalize_text(row.get("address_line1"))
    address_line_2 = normalize_text(row.get("address_line2"))
    country_id = normalize_text(row.get("country"))
    city = normalize_text(row.get("town"))
    state = normalize_text(row.get("county"))
    phone_number = normalize_text(row.get("telephone_no"))
    password_hash = normalize_text(row.get("password"))
    password_updated_at = row.get("updated_at") if password_hash else None
    created_at = row.get("created_at") or datetime.now(timezone.utc)
    updated_at = row.get("updated_at") or datetime.now(timezone.utc)
    external_id = parse_int(row.get("location_id"))
    
    is_active = row.get("is_active")
    status = "active" if is_active == 1 else "inactive"
    
    # Use provided values or set placeholders for required fields
    organization_code = normalize_text(row.get("org_code")) or "N/A"
    registration_number = normalize_text(row.get("registration_no")) or "N/A"
    address_line_1 = normalize_text(row.get("address_line1")) or "N/A"
    address_line_2 = normalize_text(row.get("address_line2")) or "N/A"
    postal_code = normalize_text(row.get("postcode")) or "N/A"
    country_id = normalize_text(row.get("country")) or "N/A"
    
    # Mark as system-generated if type_id is missing
    is_system_generated = type_id is None

    return {
        "external_id": external_id,
        "company_id": company_id,
        "type_id": type_id,
        "regulatory_body_id": regulatory_body_id,
        "postal_code": postal_code,
        "registered_name": registered_name,
        "trading_name": trading_name,
        "organization_code": organization_code,
        "registration_number": registration_number,
        "username": username,
        "address_line_1": address_line_1,
        "address_line_2": address_line_2,
        "country_id": country_id,
        "city": city,
        "state": state,
        "phone_number": phone_number,
        "email": email,
        "email_verified_at": row.get("email_verified_at"),
        "password_updated_at": password_updated_at,
        "password_hash": password_hash,
        "registration_number_regex": None,
        "status": status,
        "register_policy": None,
        "allow_unlicensed_registers": False,
        "current_theme_id": None,
        "deleted_at": row.get("deleted_at"),
        "created_at": created_at,
        "updated_at": updated_at,
        "is_system_generated": is_system_generated,
        "nickname": None,
    }


def insert_batch(pg_conn, rows: List[Dict[str, Any]]):
    if not rows:
        return

    cols = [
        "external_id",
        "company_id",
        "type_id",
        "regulatory_body_id",
        "postal_code",
        "registered_name",
        "trading_name",
        "organization_code",
        "registration_number",
        "username",
        "address_line_1",
        "address_line_2",
        "country_id",
        "city",
        "state",
        "phone_number",
        "email",
        "email_verified_at",
        "password_updated_at",
        "password_hash",
        "status",
        "register_policy",
        "allow_unlicensed_registers",
        "current_theme_id",
        "created_at",
        "updated_at",
        "deleted_at",
        "is_system_generated",
        "nickname",
    ]
    template = "(%s)" % ",".join(["%s"] * len(cols))
    values = [
        tuple(r[col] for col in cols)
        for r in rows
    ]

    sql = (
        "INSERT INTO public.sites (" + 
        ",".join(cols) + ") VALUES %s ON CONFLICT (email) DO UPDATE SET external_id = COALESCE(public.sites.external_id, EXCLUDED.external_id)"
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
        company_map = build_company_map(pg_conn)
        site_type_external_map, site_type_name_map = build_site_type_map(pg_conn)
        regulatory_body_external_map, regulatory_body_name_map = build_regulatory_body_map(pg_conn)
        existing_emails = get_existing_emails(pg_conn)

        logging.info("Loaded %d companies, %d site_types, %d regulatory bodies, %d existing site emails",
                     len(company_map), len(site_type_external_map), len(regulatory_body_external_map), len(existing_emails))

        offset = 0
        total_inserted = 0
        while True:
            rows = fetch_mysql_rows(mysql_conn, offset, BATCH_SIZE)
            if not rows:
                break

            transformed = []
            for r in rows:
                try:
                    t = transform_row(
                        r,
                        company_map,
                        site_type_external_map,
                        site_type_name_map,
                        regulatory_body_external_map,
                        regulatory_body_name_map,
                    )
                except ValueError as exc:
                    logging.warning("Skipping location %s: %s", r.get("location_id"), exc)
                    continue

                email_key = t["email"].lower()
                if email_key in existing_emails:
                    continue
                transformed.append(t)
                existing_emails.add(email_key)

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
