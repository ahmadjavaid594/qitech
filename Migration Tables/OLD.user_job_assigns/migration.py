#!/usr/bin/env python3
"""Migrate MySQL `user_job_assigns` to Postgres `company_user_user_types`.

Expected prerequisite migrations:
- users -> public.users with external_id
- head_offices -> public.companies with external_id/email
- locations -> public.sites with external_id
- head_office_users -> public.company_users
- user_jobs -> public.user_types with external_id
"""
import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

try:
    import pymysql.cursors
    import psycopg2
    import psycopg2.extras
except Exception as e:
    logging.error("Missing Python dependency: %s", e)
    logging.error("Install dependencies: pip install pymysql psycopg2-binary")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

MYSQL_HOST = os.getenv("MYSQL_HOST", "127.0.0.1")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "root")
MYSQL_DB = os.getenv("MYSQL_DB", "qitech")

PG_HOST = os.getenv("PG_HOST", "qitech-pg-test-17943.postgres.database.azure.com")
PG_PORT = int(os.getenv("PG_PORT", "5432"))
PG_USER = os.getenv("PG_USER", "pgadmin")
PG_PASSWORD = os.getenv("PG_PASSWORD", "2fac05f6ac12e581bc2aeb8bc188deac")
PG_DB = os.getenv("PG_DB", "qi-tech")

BATCH_SIZE = int(os.getenv("BATCH_SIZE", "1000"))
LIVE_COMPANY_USER_LOOKUP = os.getenv("LIVE_COMPANY_USER_LOOKUP", "0").lower() in {"1", "true", "yes", "on"}


def parse_int(value: Any) -> Optional[int]:
    if value in (None, "", "NULL"):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def clean_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def parse_also_is_job_ids(value: Any) -> List[int]:
    if value in (None, "", "null"):
        return []
    try:
        decoded = json.loads(value) if isinstance(value, str) else value
    except (TypeError, ValueError):
        return []

    if isinstance(decoded, dict):
        candidates = decoded.values()
    elif isinstance(decoded, list):
        candidates = decoded
    else:
        candidates = [decoded]

    job_ids: List[int] = []
    for item in candidates:
        parsed = parse_int(item)
        if parsed is not None and parsed not in job_ids:
            job_ids.append(parsed)
    return job_ids


def fetch_mysql_rows(connection, offset: int, limit: int) -> List[Dict[str, Any]]:
    with connection.cursor() as cur:
        cur.execute(
            """
            SELECT
                uja.id,
                uja.user_id,
                uja.location_id,
                uja.head_office_id,
                COALESCE(uja.head_office_id, hol.head_office_id) AS resolved_head_office_id,
                ho.email AS head_office_email,
                uja.job_id,
                uj.job AS job_name,
                uj.job_description,
                uja.subtypes,
                uja.regulatory_body_id,
                uja.reg_no,
                uja.created_at,
                uja.updated_at,
                uja.also_is,
                jrb.name AS regulatory_body_name,
                jrb.reg_number_validation AS regulatory_body_regex
            FROM user_job_assigns uja
            LEFT JOIN head_office_locations hol ON hol.location_id = uja.location_id
            LEFT JOIN head_offices ho ON ho.id = COALESCE(uja.head_office_id, hol.head_office_id)
            LEFT JOIN user_jobs uj ON uj.id = uja.job_id
            LEFT JOIN job_regulatory_body jrb ON jrb.id = uja.regulatory_body_id
            ORDER BY uja.id
            LIMIT %s OFFSET %s
            """,
            (limit, offset),
        )
        return cur.fetchall()


def build_company_maps(pg_conn) -> Tuple[Dict[int, str], Dict[str, str]]:
    external_map: Dict[int, str] = {}
    email_map: Dict[str, str] = {}
    with pg_conn.cursor() as cur:
        cur.execute("SELECT id::text, external_id, email FROM public.companies")
        for company_id, external_id, email in cur.fetchall():
            parsed = parse_int(external_id)
            if parsed is not None:
                external_map[parsed] = company_id
            if email:
                email_map[str(email).strip().lower()] = company_id
    return external_map, email_map


def build_site_company_map(pg_conn) -> Dict[int, str]:
    mapping: Dict[int, str] = {}
    with pg_conn.cursor() as cur:
        cur.execute("SELECT external_id, company_id::text FROM public.sites WHERE external_id IS NOT NULL")
        for external_id, company_id in cur.fetchall():
            parsed = parse_int(external_id)
            if parsed is not None:
                mapping[parsed] = company_id
    return mapping


def build_user_map(pg_conn) -> Dict[int, str]:
    mapping: Dict[int, str] = {}
    with pg_conn.cursor() as cur:
        cur.execute("SELECT external_id, id::text FROM public.users WHERE external_id IS NOT NULL")
        for external_id, user_id in cur.fetchall():
            parsed = parse_int(external_id)
            if parsed is not None:
                mapping[parsed] = user_id
    return mapping


def build_company_user_map(pg_conn) -> Dict[Tuple[str, str], str]:
    mapping: Dict[Tuple[str, str], str] = {}
    with pg_conn.cursor() as cur:
        cur.execute("SELECT user_id::text, company_id::text, id::text FROM public.company_users")
        for user_id, company_id, company_user_id in cur.fetchall():
            mapping[(user_id, company_id)] = company_user_id
    return mapping


def build_company_user_external_map(pg_conn) -> Dict[Tuple[int, str], str]:
    """Map (old user_job_assigns.user_id, company_id) to company_users.id.

    The old user id is resolved through public.users.external_id, then joined to
    public.company_users using the resolved users.id plus company_id.
    """
    mapping: Dict[Tuple[int, str], str] = {}
    with pg_conn.cursor() as cur:
        cur.execute(
            """
            SELECT u.external_id, cu.company_id::text, cu.id::text
            FROM public.users u
            JOIN public.company_users cu ON cu.user_id = u.id
            WHERE u.external_id IS NOT NULL
            """
        )
        for external_id, company_id, company_user_id in cur.fetchall():
            parsed = parse_int(external_id)
            if parsed is not None:
                mapping[(parsed, company_id)] = company_user_id
    return mapping


def resolve_company_user_id(
    pg_conn,
    source_user_id: int,
    company_id: str,
    user_map: Dict[int, str],
    company_user_map: Dict[Tuple[str, str], str],
    company_user_external_map: Dict[Tuple[int, str], str],
    missing_company_user_pairs: set[Tuple[int, str]],
) -> Optional[str]:
    external_key = (source_user_id, company_id)
    if external_key in company_user_external_map:
        return company_user_external_map[external_key]
    if external_key in missing_company_user_pairs:
        return None

    user_id = user_map.get(source_user_id)
    if user_id:
        company_user_id = company_user_map.get((user_id, company_id))
        if company_user_id:
            company_user_external_map[external_key] = company_user_id
            return company_user_id

    if not LIVE_COMPANY_USER_LOOKUP:
        missing_company_user_pairs.add(external_key)
        return None

    with pg_conn.cursor() as cur:
        cur.execute(
            """
            SELECT cu.id::text, u.id::text
            FROM public.users u
            JOIN public.company_users cu ON cu.user_id = u.id
            WHERE u.external_id = %s
              AND cu.company_id = %s
            LIMIT 1
            """,
            (source_user_id, company_id),
        )
        row = cur.fetchone()

    if not row:
        missing_company_user_pairs.add(external_key)
        return None

    company_user_id, user_id = row
    user_map[source_user_id] = user_id
    company_user_map[(user_id, company_id)] = company_user_id
    company_user_external_map[external_key] = company_user_id
    return company_user_id


def build_user_type_maps(pg_conn) -> Tuple[Dict[Tuple[int, str], str], Dict[Tuple[str, str], str]]:
    """Map old user_job_assigns.job_id to public.user_types.id via external_id."""
    external_map: Dict[Tuple[int, str], str] = {}
    name_map: Dict[Tuple[str, str], str] = {}
    with pg_conn.cursor() as cur:
        cur.execute("SELECT external_id, company_id::text, lower(name), id::text FROM public.user_types")
        for external_id, company_id, name, user_type_id in cur.fetchall():
            parsed = parse_int(external_id)
            if parsed is not None:
                external_map[(parsed, company_id)] = user_type_id
            if name:
                name_map[(company_id, name)] = user_type_id
    return external_map, name_map


def get_or_create_user_type(
    pg_conn,
    source_job_id: int,
    company_id: str,
    name: Optional[str],
    description: Optional[str],
    user_type_external_map: Dict[Tuple[int, str], str],
    user_type_name_map: Dict[Tuple[str, str], str],
    dry_run: bool,
) -> Optional[str]:
    existing = user_type_external_map.get((source_job_id, company_id))
    if existing:
        return existing

    clean_name = clean_text(name) or f"Migrated User Type {source_job_id}"
    name_key = (company_id, clean_name.lower())
    existing = user_type_name_map.get(name_key)
    if existing:
        user_type_external_map[(source_job_id, company_id)] = existing
        return existing

    if dry_run:
        logging.info("Dry-run: would create user_type %r for company %s from job_id=%s", clean_name, company_id, source_job_id)
        dry_run_id = f"dry-run-user-type:{company_id}:{source_job_id}"
        user_type_external_map[(source_job_id, company_id)] = dry_run_id
        user_type_name_map[name_key] = dry_run_id
        return dry_run_id

    with pg_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO public.user_types
                (external_id, company_id, name, description, "isSystemGenerated", enabled,
                 allow_multiple_sub_types, sub_type_selection_required, has_regulatory_body,
                 assignment_mode, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (company_id, name) DO UPDATE SET
                external_id = COALESCE(public.user_types.external_id, EXCLUDED.external_id),
                description = COALESCE(public.user_types.description, EXCLUDED.description),
                enabled = true,
                updated_at = EXCLUDED.updated_at
            RETURNING id::text
            """,
            (
                source_job_id,
                company_id,
                clean_name,
                clean_text(description),
                False,
                True,
                False,
                False,
                False,
                "open",
                now_utc(),
                now_utc(),
            ),
        )
        user_type_id = cur.fetchone()[0]
    pg_conn.commit()
    user_type_external_map[(source_job_id, company_id)] = user_type_id
    user_type_name_map[name_key] = user_type_id
    return user_type_id


def build_regulatory_body_name_map(pg_conn) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    with pg_conn.cursor() as cur:
        cur.execute("SELECT id::text, name FROM public.regulatory_bodies WHERE name IS NOT NULL")
        for regulatory_body_id, name in cur.fetchall():
            key = clean_text(name)
            if key:
                mapping[key.lower()] = regulatory_body_id
    return mapping


def get_or_create_regulatory_body(
    pg_conn,
    name: Optional[str],
    regex: Optional[str],
    regulatory_body_name_map: Dict[str, str],
    dry_run: bool,
) -> Optional[str]:
    clean_name = clean_text(name)
    if not clean_name:
        return None

    key = clean_name.lower()
    existing = regulatory_body_name_map.get(key)
    if existing:
        return existing

    if dry_run:
        logging.info("Dry-run: would create regulatory_body %r", clean_name)
        return None

    with pg_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO public.regulatory_bodies
                (name, registration_number_regex, created_at, updated_at)
            VALUES (%s, %s, %s, %s)
            RETURNING id::text
            """,
            (clean_name, clean_text(regex), now_utc(), now_utc()),
        )
        regulatory_body_id = cur.fetchone()[0]
    pg_conn.commit()
    regulatory_body_name_map[key] = regulatory_body_id
    return regulatory_body_id


def resolve_company_id(
    row: Dict[str, Any],
    company_external_map: Dict[int, str],
    company_email_map: Dict[str, str],
    site_company_map: Dict[int, str],
) -> Optional[str]:
    head_office_id = parse_int(row.get("resolved_head_office_id"))
    if head_office_id is not None:
        company_id = company_external_map.get(head_office_id)
        if company_id:
            return company_id

        email = clean_text(row.get("head_office_email"))
        if email:
            company_id = company_email_map.get(email.lower())
            if company_id:
                return company_id

        company_id = company_email_map.get(f"migrated+{head_office_id}@example.invalid")
        if company_id:
            return company_id

    location_id = parse_int(row.get("location_id"))
    if location_id is not None:
        return site_company_map.get(location_id)

    return None


def transform_rows(
    pg_conn,
    row: Dict[str, Any],
    company_external_map: Dict[int, str],
    company_email_map: Dict[str, str],
    site_company_map: Dict[int, str],
    user_map: Dict[int, str],
    company_user_map: Dict[Tuple[str, str], str],
    company_user_external_map: Dict[Tuple[int, str], str],
    missing_company_user_pairs: set[Tuple[int, str]],
    user_type_external_map: Dict[Tuple[int, str], str],
    user_type_name_map: Dict[Tuple[str, str], str],
    regulatory_body_name_map: Dict[str, str],
    dry_run: bool,
) -> List[Dict[str, Any]]:
    source_user_id = parse_int(row.get("user_id"))
    if source_user_id is None:
        raise ValueError(f"Missing or invalid user_id for user_job_assigns.id={row.get('id')}")

    company_id = resolve_company_id(row, company_external_map, company_email_map, site_company_map)
    if not company_id:
        raise ValueError(
            f"No target company found for user_job_assigns.id={row.get('id')} "
            f"(head_office_id={row.get('head_office_id')}, location_id={row.get('location_id')})"
        )

    company_user_id = resolve_company_user_id(
        pg_conn,
        source_user_id,
        company_id,
        user_map,
        company_user_map,
        company_user_external_map,
        missing_company_user_pairs,
    )
    if not company_user_id:
        raise ValueError(f"No company_user found for source user_id {source_user_id} and company_id {company_id}")

    source_job_ids = []
    main_job_id = parse_int(row.get("job_id"))
    if main_job_id is not None:
        source_job_ids.append(main_job_id)
    for job_id in parse_also_is_job_ids(row.get("also_is")):
        if job_id not in source_job_ids:
            source_job_ids.append(job_id)

    regulatory_body_id = get_or_create_regulatory_body(
        pg_conn=pg_conn,
        name=row.get("regulatory_body_name"),
        regex=row.get("regulatory_body_regex"),
        regulatory_body_name_map=regulatory_body_name_map,
        dry_run=dry_run,
    )

    result: List[Dict[str, Any]] = []
    for index, source_job_id in enumerate(source_job_ids):
        user_type_id = get_or_create_user_type(
            pg_conn,
            source_job_id,
            company_id,
            row.get("job_name"),
            row.get("job_description"),
            user_type_external_map,
            user_type_name_map,
            dry_run,
        )
        if not user_type_id:
            logging.warning(
                "Skipping user_job_assigns.id=%s job_id=%s because no matching or creatable public.user_types row exists",
                row.get("id"),
                source_job_id,
            )
            continue

        result.append(
            {
                "source_id": parse_int(row.get("id")),
                "company_user_id": company_user_id,
                "user_type_id": user_type_id,
                "is_main": index == 0,
                "regulatory_body_id": regulatory_body_id if index == 0 else None,
                "registration_number": clean_text(row.get("reg_no")) if index == 0 else None,
                "created_at": row.get("created_at") or now_utc(),
                "updated_at": row.get("updated_at") or now_utc(),
            }
        )

    return result


def dedupe_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_pair: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for row in rows:
        key = (row["company_user_id"], row["user_type_id"])
        existing = by_pair.get(key)
        if not existing:
            by_pair[key] = row.copy()
            continue

        existing["is_main"] = bool(existing.get("is_main")) or bool(row.get("is_main"))
        if not existing.get("regulatory_body_id") and row.get("regulatory_body_id"):
            existing["regulatory_body_id"] = row["regulatory_body_id"]
        if not existing.get("registration_number") and row.get("registration_number"):
            existing["registration_number"] = row["registration_number"]
        existing["created_at"] = min(existing["created_at"], row["created_at"])
        existing["updated_at"] = max(existing["updated_at"], row["updated_at"])

    # Enforce the partial unique index: only one main user type per company user.
    main_seen: set[str] = set()
    for row in sorted(by_pair.values(), key=lambda r: (r["company_user_id"], r["source_id"] or 0)):
        if not row["is_main"]:
            continue
        if row["company_user_id"] in main_seen:
            row["is_main"] = False
        else:
            main_seen.add(row["company_user_id"])

    return list(by_pair.values())


def insert_batch(pg_conn, rows: List[Dict[str, Any]]) -> int:
    deduped_rows = dedupe_rows(rows)
    if not deduped_rows:
        return 0

    with pg_conn.cursor() as cur:
        cur.execute("SELECT company_user_id::text FROM public.company_user_user_types WHERE is_main = true")
        existing_main_company_users = {row[0] for row in cur.fetchall()}
    for row in deduped_rows:
        if row["company_user_id"] in existing_main_company_users:
            row["is_main"] = False

    cols = [
        "company_user_id",
        "user_type_id",
        "is_main",
        "regulatory_body_id",
        "registration_number",
    ]
    template = "(%s)" % ",".join(["%s"] * len(cols))
    values = [
        (
            row["company_user_id"],
            row["user_type_id"],
            row["is_main"],
            row["regulatory_body_id"],
            row["registration_number"],
        )
        for row in deduped_rows
    ]

    sql = (
        "INSERT INTO public.company_user_user_types (" +
        ",".join(cols) + ") VALUES %s "
        "ON CONFLICT (company_user_id, user_type_id) DO UPDATE SET "
        "is_main = CASE "
        "WHEN public.company_user_user_types.is_main THEN true "
        "WHEN EXCLUDED.is_main AND NOT EXISTS ("
        "SELECT 1 FROM public.company_user_user_types existing "
        "WHERE existing.company_user_id = EXCLUDED.company_user_id "
        "AND existing.is_main = true "
        "AND existing.id <> public.company_user_user_types.id"
        ") THEN true "
        "ELSE public.company_user_user_types.is_main END, "
        "regulatory_body_id = COALESCE(EXCLUDED.regulatory_body_id, public.company_user_user_types.regulatory_body_id), "
        "registration_number = COALESCE(EXCLUDED.registration_number, public.company_user_user_types.registration_number)"
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
        site_company_map = build_site_company_map(pg_conn)
        user_map = build_user_map(pg_conn)
        company_user_map = build_company_user_map(pg_conn)
        company_user_external_map = build_company_user_external_map(pg_conn)
        missing_company_user_pairs: set[Tuple[int, str]] = set()
        user_type_external_map, user_type_name_map = build_user_type_maps(pg_conn)
        regulatory_body_name_map = build_regulatory_body_name_map(pg_conn)
        logging.info(
            "Loaded maps: companies=%d emails=%d sites=%d users=%d company_users=%d company_user_external=%d user_type_external=%d user_type_names=%d regulatory_bodies=%d",
            len(company_external_map),
            len(company_email_map),
            len(site_company_map),
            len(user_map),
            len(company_user_map),
            len(company_user_external_map),
            len(user_type_external_map),
            len(user_type_name_map),
            len(regulatory_body_name_map),
        )

        offset = 0
        total_inserted = 0
        while True:
            rows = fetch_mysql_rows(mysql_conn, offset, BATCH_SIZE)
            if not rows:
                break

            transformed: List[Dict[str, Any]] = []
            for row in rows:
                try:
                    transformed.extend(
                        transform_rows(
                            pg_conn,
                            row,
                            company_external_map,
                            company_email_map,
                            site_company_map,
                            user_map,
                            company_user_map,
                            company_user_external_map,
                            missing_company_user_pairs,
                            user_type_external_map,
                            user_type_name_map,
                            regulatory_body_name_map,
                            dry_run,
                        )
                    )
                except ValueError as e:
                    logging.warning("Skipping row: %s", e)

            deduped_count = len(dedupe_rows(transformed))
            if dry_run:
                logging.info("Dry-run: would insert/update %d rows for offset %d", deduped_count, offset)
            else:
                inserted = insert_batch(pg_conn, transformed)
                total_inserted += inserted
                logging.info("Inserted/updated %d rows (offset %d)", inserted, offset)

            offset += BATCH_SIZE

        logging.info("Done. Total inserted/updated: %d", total_inserted)

    finally:
        mysql_conn.close()
        pg_conn.close()


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    main(dry_run=dry)
