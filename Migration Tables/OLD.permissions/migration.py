#!/usr/bin/env python3
"""Full permissions metadata migration from MySQL qitech to PostgreSQL public schema.

Migrates / upserts, in dependency order:
  1. MySQL roles                         -> public.roles
  2. MySQL head_offices                   -> public.companies
  3. MySQL users + user_roles             -> public.users
  4. MySQL head_office_access_rights and
     head_office_user_profiles            -> public.company_roles
  5. MySQL head_office_users              -> public.company_users
  6. MySQL head_office_permissions plus
     access-right boolean columns         -> public.permissions
  7. Profile / user access-right rows     -> public.permission_assignments

Why this script is defensive:
- public.companies, public.users, public.roles, public.company_roles and
  public.company_users have external_id.
- public.company_roles.external_id stores head_office_user_profiles.id. Roles that
  only exist as access-right names or fallbacks have no legacy ID and remain NULL.
- public.permissions does not have external_id, so it is matched by (scope, name).
- public.permission_assignments has no external_id and no unique key in the metadata,
  so duplicate checks are done before insert.

Install:
  pip install pymysql psycopg2-binary

Run dry-run first:
  python migrate_permissions_metadata.py --dry-run

Run migration:
  python migrate_permissions_metadata.py
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import sys
from datetime import datetime, timezone, date
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

try:
    import pymysql.cursors
    import psycopg2
    import psycopg2.extras
except Exception as e:  # pragma: no cover
    logging.error("Missing dependency: %s", e)
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
PG_SSLMODE = os.getenv("PG_SSLMODE", "require")

BATCH_SIZE = int(os.getenv("BATCH_SIZE", "1000"))
DEFAULT_COMPANY_ROLE = os.getenv("DEFAULT_COMPANY_ROLE", "Staff")
DEFAULT_USER_ROLE = os.getenv("DEFAULT_USER_ROLE", "None")
DEFAULT_TIMEZONE = os.getenv("DEFAULT_TIMEZONE", "Europe/London")

# Boolean columns from old head_office_access_rights that represent permissions.
# The generated permission names intentionally stay close to the old column names
# but are human readable for the new permissions.name field.
ACCESS_RIGHT_PERMISSION_COLUMNS = [
    "super_access",
    "is_manage_forms",
    "is_manage_company_account",
    "is_manage_team",
    "is_manage_location_users",
    "is_manage_alert_settings",
    "is_access_company_activity_log",
    "is_access_contacts",
    "user_can_view",
    "bypass_case_handler",
    "is_allocated",
    "is_access_locations",
    "is_access_case_manager",
    "is_access_dashboard",
    "is_access_tasks",
]


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def parse_int(value: Any) -> Optional[int]:
    if value in (None, "", "NULL"):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def truthy(value: Any) -> bool:
    if value is True:
        return True
    if value is False or value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def clean_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def permission_label(name: str) -> str:
    name = re.sub(r"^(is_|can_)", "", name.strip())
    name = name.replace("_", " ")
    name = re.sub(r"\s+", " ", name)
    return name.title()


def status_from_user(row: Dict[str, Any]) -> str:
    if truthy(row.get("is_archived")):
        return "archived"
    if truthy(row.get("is_suspended")):
        return "suspended"
    if row.get("is_active") in (None, "") or truthy(row.get("is_active")):
        return "active"
    return "inactive"


def work_status_from_head_office_user(row: Dict[str, Any]) -> str:
    # If target enum names differ, set WORK_STATUS_FALLBACK in env or adjust here.
    raw = clean_text(row.get("work_status"))
    if raw in {"active", "inactive", "remote", "onsite", "hybrid"}:
        return raw
    return os.getenv("WORK_STATUS_FALLBACK", "active")


def company_user_status_from_head_office_user(row: Dict[str, Any]) -> str:
    if truthy(row.get("is_blocked")):
        return os.getenv("COMPANY_USER_BLOCKED_STATUS", "inactive")
    return "active"


def company_user_role_active(row: Dict[str, Any]) -> bool:
    if truthy(row.get("is_blocked")):
        return False
    return bool(truthy(row.get("is_active")) if row.get("is_active") not in (None, "") else True)


def connect_mysql():
    return pymysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        db=MYSQL_DB,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )


def connect_pg():
    return psycopg2.connect(
        host=PG_HOST,
        port=PG_PORT,
        user=PG_USER,
        password=PG_PASSWORD,
        dbname=PG_DB,
        sslmode=PG_SSLMODE,
    )


def mysql_fetch_all(conn, sql: str, params: Sequence[Any] = ()) -> List[Dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return list(cur.fetchall())


def pg_fetch_all(conn, sql: str, params: Sequence[Any] = ()) -> List[Tuple[Any, ...]]:
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def pg_fetch_one(conn, sql: str, params: Sequence[Any] = ()) -> Optional[Tuple[Any, ...]]:
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchone()


def execute_values(pg_conn, sql: str, rows: List[Tuple[Any, ...]], dry_run: bool = False) -> int:
    if not rows:
        return 0
    if dry_run:
        logging.info("Dry-run: would execute batch with %d rows", len(rows))
        return len(rows)
    with pg_conn.cursor() as cur:
        psycopg2.extras.execute_values(cur, sql, rows)
    pg_conn.commit()
    return len(rows)


def execute_external_id_upserts(
    pg_conn,
    rows: List[Tuple[Any, ...]],
    select_sql: str,
    update_sql: str,
    insert_sql: str,
    update_params,
    insert_params,
    select_params=None,
    dry_run: bool = False,
) -> int:
    """Upsert rows when external_id is not backed by a unique Postgres constraint."""
    if not rows:
        return 0
    if dry_run:
        logging.info("Dry-run: would externally upsert %d rows", len(rows))
        return len(rows)

    with pg_conn.cursor() as cur:
        for row in rows:
            cur.execute(select_sql, select_params(row) if select_params else (row[0],))
            existing = cur.fetchone()
            if existing:
                cur.execute(update_sql, update_params(row, existing[0]))
            else:
                cur.execute(insert_sql, insert_params(row))
    pg_conn.commit()
    return len(rows)


def get_columns(pg_conn, table: str) -> set[str]:
    rows = pg_fetch_all(
        pg_conn,
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = %s
        """,
        (table,),
    )
    return {r[0] for r in rows}


def load_id_map(pg_conn, table: str) -> Dict[int, str]:
    if "external_id" not in get_columns(pg_conn, table):
        return {}
    rows = pg_fetch_all(
        pg_conn,
        f"SELECT external_id, id::text FROM public.{table} WHERE external_id IS NOT NULL",
    )
    return {int(old): new for old, new in rows if old is not None}


def load_id_map_by_value(
    pg_conn,
    source_rows: List[Dict[str, Any]],
    table: str,
    source_id_col: str,
    source_value_col: str,
    target_value_col: str,
    fallback_value,
) -> Dict[int, str]:
    value_to_old_ids: Dict[str, List[int]] = {}
    for row in source_rows:
        old_id = parse_int(row.get(source_id_col))
        if old_id is None:
            continue
        value = clean_text(row.get(source_value_col)) or fallback_value(old_id)
        value_to_old_ids.setdefault(value, []).append(old_id)

    if not value_to_old_ids:
        return {}

    result: Dict[int, str] = {}
    values = list(value_to_old_ids.keys())
    with pg_conn.cursor() as cur:
        for start in range(0, len(values), BATCH_SIZE):
            chunk = values[start : start + BATCH_SIZE]
            cur.execute(
                f"SELECT {target_value_col}, id::text FROM public.{table} WHERE {target_value_col} = ANY(%s)",
                (chunk,),
            )
            for value, target_id in cur.fetchall():
                for old_id in value_to_old_ids.get(value, []):
                    result[old_id] = target_id
    return result


def upsert_roles(mysql_conn, pg_conn, dry_run: bool) -> Dict[int, str]:
    logging.info("Migrating roles")
    rows = mysql_fetch_all(mysql_conn, "SELECT id, name, created_at, updated_at FROM roles ORDER BY id")
    values = []
    for r in rows:
        values.append((parse_int(r["id"]), clean_text(r["name"]) or DEFAULT_USER_ROLE, r.get("created_at") or now_utc(), r.get("updated_at") or now_utc()))

    execute_external_id_upserts(
        pg_conn,
        values,
        "SELECT id FROM public.roles WHERE external_id = %s LIMIT 1",
        """
        UPDATE public.roles
        SET name = %s, updated_at = %s
        WHERE id = %s
        """,
        """
        INSERT INTO public.roles (external_id, name, created_at, updated_at)
        VALUES (%s, %s, %s, %s)
        """,
        lambda row, role_id: (row[1], row[3], role_id),
        lambda row: row,
        dry_run=dry_run,
    )
    return load_id_map(pg_conn, "roles") if not dry_run else {}


def get_or_create_user_role(pg_conn, name: str, dry_run: bool) -> Optional[str]:
    existing = pg_fetch_one(
        pg_conn,
        "SELECT id::text FROM public.roles WHERE lower(name) = lower(%s) LIMIT 1",
        (name,),
    )
    if existing:
        return existing[0]
    if dry_run:
        logging.info("Dry-run: would create fallback user role %s", name)
        return None
    with pg_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO public.roles (name, created_at, updated_at)
            VALUES (%s, %s, %s)
            RETURNING id::text
            """,
            (name, now_utc(), now_utc()),
        )
        role_id = cur.fetchone()[0]
    pg_conn.commit()
    return role_id


def upsert_companies(mysql_conn, pg_conn, dry_run: bool) -> Dict[int, str]:
    logging.info("Migrating companies from head_offices")
    rows = mysql_fetch_all(
        mysql_conn,
        """
        SELECT id, company_name, address, telephone_no, email, sites_count, created_at, updated_at
        FROM head_offices
        ORDER BY id
        """,
    )
    values_by_email = {}
    for r in rows:
        old_id = parse_int(r.get("id"))
        name = clean_text(r.get("company_name")) or f"Migrated Company {old_id}"
        email = clean_text(r.get("email")) or f"migrated+company-{old_id}@example.invalid"
        if email in values_by_email:
            logging.warning("Skipping duplicate company email %r for head_offices.id=%s", email, old_id)
            continue
        values_by_email[email] = (
            old_id,
            name,
            clean_text(r.get("address")),
            email,
            clean_text(r.get("telephone_no")),
            parse_int(r.get("sites_count")),
            DEFAULT_TIMEZONE,
            r.get("created_at") or now_utc(),
            r.get("updated_at") or now_utc(),
        )
    values = list(values_by_email.values())

    sql = """
        INSERT INTO public.companies
            (external_id, name, address, email, phone_number, estimated_site_count, timezone, created_at, updated_at)
        VALUES %s
        ON CONFLICT (email) DO UPDATE SET
            external_id = COALESCE(public.companies.external_id, EXCLUDED.external_id),
            name = EXCLUDED.name,
            address = EXCLUDED.address,
            phone_number = EXCLUDED.phone_number,
            estimated_site_count = EXCLUDED.estimated_site_count,
            updated_at = EXCLUDED.updated_at
    """
    execute_values(pg_conn, sql, values, dry_run)
    if dry_run:
        return {}
    return load_id_map_by_value(
        pg_conn,
        rows,
        "companies",
        "id",
        "email",
        "email",
        lambda old_id: f"migrated+company-{old_id}@example.invalid",
    )


def upsert_users(mysql_conn, pg_conn, role_map: Dict[int, str], dry_run: bool) -> Dict[int, str]:
    logging.info("Migrating users")
    default_role_id = get_or_create_user_role(pg_conn, DEFAULT_USER_ROLE, dry_run)
    rows = mysql_fetch_all(
        mysql_conn,
        """
        SELECT u.*, ur.role_id AS old_role_id
        FROM users u
        LEFT JOIN user_roles ur ON ur.user_id = u.id
        ORDER BY u.id
        """,
    )
    values_by_email = {}
    seen_external = set()
    for r in rows:
        old_id = parse_int(r.get("id"))
        if old_id in seen_external:
            continue
        seen_external.add(old_id)
        email = clean_text(r.get("email")) or f"migrated+user-{old_id}@example.invalid"
        if email in values_by_email:
            logging.warning("Skipping duplicate user email %r for users.id=%s", email, old_id)
            continue
        role_id = role_map.get(parse_int(r.get("old_role_id"))) or default_role_id
        if role_id is None and not dry_run:
            raise RuntimeError(f"Could not resolve fallback role {DEFAULT_USER_ROLE!r} for users.id={old_id}")
        values_by_email[email] = (
            old_id,
            role_id,
            clean_text(r.get("first_name")) or "Migrated",
            clean_text(r.get("middlename")),
            clean_text(r.get("surname")) or "User",
            email,
            clean_text(r.get("mobile_no")),
            clean_text(r.get("password")) or "",
            r.get("email_verified_at"),
            r.get("password_updated_at"),
            r.get("dob") or None,
            bool(truthy(r.get("is_email_hidden"))),
            bool(truthy(r.get("is_phone_hidden"))),
            status_from_user(r),
            clean_text(r.get("block_comment")),
            r.get("created_at") or now_utc(),
            r.get("updated_at") or now_utc(),
        )
    values = list(values_by_email.values())

    sql = """
        INSERT INTO public.users
            (external_id, role_id, first_name, middle_name, surname, email, phone_number,
             password_hash, email_verified_at, password_changed_at, date_of_birth,
             is_email_hidden, is_phone_number_hidden, status, status_comment, created_at, updated_at)
        VALUES %s
        ON CONFLICT (email) DO UPDATE SET
            external_id = COALESCE(public.users.external_id, EXCLUDED.external_id),
            role_id = COALESCE(EXCLUDED.role_id, public.users.role_id),
            first_name = EXCLUDED.first_name,
            middle_name = EXCLUDED.middle_name,
            surname = EXCLUDED.surname,
            phone_number = EXCLUDED.phone_number,
            status = EXCLUDED.status,
            status_comment = EXCLUDED.status_comment,
            updated_at = EXCLUDED.updated_at
    """
    execute_values(pg_conn, sql, values, dry_run)
    if dry_run:
        return {}
    return load_id_map_by_value(
        pg_conn,
        rows,
        "users",
        "id",
        "email",
        "email",
        lambda old_id: f"migrated+user-{old_id}@example.invalid",
    )


def get_or_create_company_role(
    pg_conn,
    company_id: str,
    name: str,
    dry_run: bool,
    external_id: Optional[int] = None,
) -> Optional[str]:
    if not company_id or not name:
        return None
    existing = pg_fetch_one(
        pg_conn,
        """
        SELECT id::text
        FROM public.company_roles
        WHERE (%s IS NOT NULL AND external_id = %s)
           OR (company_id = %s AND lower(name) = lower(%s))
        ORDER BY CASE WHEN %s IS NOT NULL AND external_id = %s THEN 0 ELSE 1 END
        LIMIT 1
        """,
        (external_id, external_id, company_id, name, external_id, external_id),
    )
    if existing:
        if external_id is not None and not dry_run:
            with pg_conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE public.company_roles
                    SET external_id = COALESCE(external_id, %s),
                        company_id = %s,
                        name = %s,
                        updated_at = %s
                    WHERE id = %s
                    """,
                    (external_id, company_id, name, now_utc(), existing[0]),
                )
            pg_conn.commit()
        return existing[0]
    if dry_run:
        logging.info(
            "Dry-run: would create company_role %s for company %s with external_id=%s",
            name,
            company_id,
            external_id,
        )
        return None
    with pg_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO public.company_roles (external_id, company_id, name, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id::text
            """,
            (external_id, company_id, name, now_utc(), now_utc()),
        )
        new_id = cur.fetchone()[0]
    pg_conn.commit()
    return new_id


def upsert_company_roles(mysql_conn, pg_conn, company_map: Dict[int, str], dry_run: bool) -> Dict[Tuple[int, str], str]:
    logging.info("Migrating company roles / profiles")
    role_map: Dict[Tuple[int, str], str] = {}

    profile_rows = mysql_fetch_all(
        mysql_conn,
        """
        SELECT id AS external_id, head_office_id, profile_name, created_at, updated_at
        FROM head_office_user_profiles
        WHERE profile_name IS NOT NULL AND profile_name <> ''
        UNION ALL
        SELECT hoar.id AS external_id, hoar.head_office_id, hoar.profile_name,
               hoar.created_at, hoar.updated_at
        FROM head_office_access_rights hoar
        WHERE hoar.profile_name IS NOT NULL
          AND hoar.profile_name <> ''
          AND NOT EXISTS (
              SELECT 1
              FROM head_office_user_profiles houp
              WHERE houp.head_office_id = hoar.head_office_id
                AND lower(houp.profile_name) = lower(hoar.profile_name)
          )
        ORDER BY head_office_id, profile_name
        """,
    )

    # Also ensure every company gets a fallback role.
    for old_company_id, company_id in company_map.items():
        role_id = get_or_create_company_role(pg_conn, company_id, DEFAULT_COMPANY_ROLE, dry_run)
        if role_id:
            role_map[(old_company_id, DEFAULT_COMPANY_ROLE.lower())] = role_id

    for r in profile_rows:
        old_company_id = parse_int(r.get("head_office_id"))
        company_id = company_map.get(old_company_id)
        name = clean_text(r.get("profile_name")) or DEFAULT_COMPANY_ROLE
        external_id = parse_int(r.get("external_id"))
        if not company_id:
            logging.warning("Skipping company_role %r because company external_id %r was not found", name, old_company_id)
            continue
        role_id = get_or_create_company_role(pg_conn, company_id, name, dry_run, external_id)
        if role_id:
            role_map[(old_company_id, name.lower())] = role_id

    return role_map


def resolve_profile_name_for_company_user(mysql_conn) -> Dict[int, str]:
    rows = mysql_fetch_all(
        mysql_conn,
        """
        SELECT houpa.head_office_user_id, houp.profile_name,
               2 AS source_priority, houpa.id AS source_id
        FROM head_office_users_profile_assigns houpa
        JOIN head_office_user_profiles houp ON houp.id = houpa.user_profile_id
        WHERE houp.profile_name IS NOT NULL AND houp.profile_name <> ''
        UNION ALL
        SELECT hoar.head_office_user_id, hoar.profile_name,
               1 AS source_priority, hoar.id AS source_id
        FROM head_office_access_rights hoar
        WHERE hoar.head_office_user_id IS NOT NULL
          AND hoar.profile_name IS NOT NULL
          AND hoar.profile_name <> ''
        ORDER BY head_office_user_id, source_priority, source_id
        """,
    )
    result = {}
    for r in rows:
        hou_id = parse_int(r.get("head_office_user_id"))
        if hou_id and hou_id not in result:
            result[hou_id] = clean_text(r.get("profile_name")) or DEFAULT_COMPANY_ROLE
    return result


def upsert_company_users(
    mysql_conn,
    pg_conn,
    company_map: Dict[int, str],
    user_map: Dict[int, str],
    company_role_map: Dict[Tuple[int, str], str],
    dry_run: bool,
) -> Dict[int, str]:
    logging.info("Migrating company_users from head_office_users")
    profile_by_hou = resolve_profile_name_for_company_user(mysql_conn)
    rows = mysql_fetch_all(mysql_conn, "SELECT * FROM head_office_users ORDER BY id")
    values = []
    for r in rows:
        old_hou_id = parse_int(r.get("id"))
        old_user_id = parse_int(r.get("user_id"))
        old_company_id = parse_int(r.get("head_office_id"))
        user_id = user_map.get(old_user_id)
        company_id = company_map.get(old_company_id)
        if not user_id or not company_id:
            logging.warning("Skipping head_office_users.id=%s because user/company mapping is missing", old_hou_id)
            continue

        profile_name = profile_by_hou.get(old_hou_id) or clean_text(r.get("position")) or DEFAULT_COMPANY_ROLE
        role_id = company_role_map.get((old_company_id, profile_name.lower())) or company_role_map.get((old_company_id, DEFAULT_COMPANY_ROLE.lower()))
        if role_id is None:
            role_id = get_or_create_company_role(pg_conn, company_id, profile_name, dry_run)
        position = clean_text(r.get("position")) or profile_name or DEFAULT_COMPANY_ROLE

        values.append((
            old_hou_id,
            company_id,
            user_id,
            role_id,
            position,
            clean_text(r.get("location")),
            clean_text(r.get("about_me")),
            company_user_role_active(r),
            company_user_status_from_head_office_user(r),
            clean_text(r.get("block_comment")),
            work_status_from_head_office_user(r),
            bool(truthy(r.get("is_access_to_dashboard"))),
            r.get("created_at") or now_utc(),
            r.get("updated_at") or now_utc(),
        ))

    execute_external_id_upserts(
        pg_conn,
        values,
        """
        SELECT id
        FROM public.company_users
        WHERE external_id = %s OR (user_id = %s AND company_id = %s)
        ORDER BY CASE WHEN external_id = %s THEN 0 ELSE 1 END
        LIMIT 1
        """,
        """
        UPDATE public.company_users
        SET external_id = COALESCE(external_id, %s),
            company_id = %s,
            user_id = %s,
            company_role_id = COALESCE(%s, company_role_id),
            position = %s,
            location = %s,
            about = %s,
            is_role_active = %s,
            status = %s,
            status_comment = %s,
            work_status = %s,
            can_create_reports = %s,
            updated_at = %s
        WHERE id = %s
        """,
        """
        INSERT INTO public.company_users
            (external_id, company_id, user_id, company_role_id, position, location, about,
             is_role_active, status, status_comment, work_status, can_create_reports,
             created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        lambda row, company_user_id: (
            row[0],
            row[1],
            row[2],
            row[3],
            row[4],
            row[5],
            row[6],
            row[7],
            row[8],
            row[9],
            row[10],
            row[11],
            row[13],
            company_user_id,
        ),
        lambda row: row,
        select_params=lambda row: (row[0], row[2], row[1], row[0]),
        dry_run=dry_run,
    )
    return load_id_map(pg_conn, "company_users") if not dry_run else {}


def get_or_create_permission(pg_conn, name: str, scope: str, dry_run: bool) -> Optional[str]:
    existing = pg_fetch_one(
        pg_conn,
        "SELECT id::text FROM public.permissions WHERE lower(name) = lower(%s) AND scope = %s LIMIT 1",
        (name, scope),
    )
    if existing:
        return existing[0]
    if dry_run:
        logging.info("Dry-run: would create permission %s / %s", scope, name)
        return None
    with pg_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO public.permissions (name, scope, created_at, updated_at)
            VALUES (%s, %s, %s, %s)
            RETURNING id::text
            """,
            (name, scope, now_utc(), now_utc()),
        )
        new_id = cur.fetchone()[0]
    pg_conn.commit()
    return new_id


def upsert_permissions(mysql_conn, pg_conn, dry_run: bool) -> Dict[str, str]:
    logging.info("Migrating permissions")
    permission_map: Dict[str, str] = {}

    rows = mysql_fetch_all(mysql_conn, "SELECT id, name, created_at, updated_at FROM head_office_permissions ORDER BY id")
    for r in rows:
        raw_name = clean_text(r.get("name"))
        if not raw_name:
            continue
        label = permission_label(raw_name)
        pid = get_or_create_permission(pg_conn, label, "company", dry_run)
        if pid:
            permission_map[f"head_office_permissions:{parse_int(r.get('id'))}"] = pid
            permission_map[f"name:{raw_name}"] = pid

    for col in ACCESS_RIGHT_PERMISSION_COLUMNS:
        label = permission_label(col)
        pid = get_or_create_permission(pg_conn, label, "company", dry_run)
        if pid:
            permission_map[f"access_right:{col}"] = pid

    return permission_map


def assignment_exists(pg_conn, permission_id: str, subject_type: str, subject_id: str) -> bool:
    row = pg_fetch_one(
        pg_conn,
        """
        SELECT 1
        FROM public.permission_assignments
        WHERE permission_id = %s AND subject_type = %s AND subject_id = %s
        LIMIT 1
        """,
        (permission_id, subject_type, subject_id),
    )
    return row is not None


def insert_permission_assignment(pg_conn, permission_id: str, subject_type: str, subject_id: str, created_at: Any, dry_run: bool) -> bool:
    if not permission_id or not subject_id:
        return False
    if not dry_run and assignment_exists(pg_conn, permission_id, subject_type, subject_id):
        return False
    if dry_run:
        return True
    with pg_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO public.permission_assignments (permission_id, subject_type, subject_id, created_at)
            VALUES (%s, %s, %s, %s)
            """,
            (permission_id, subject_type, subject_id, created_at or now_utc()),
        )
    return True


def grant_all_permissions_to_super_user_roles(pg_conn, dry_run: bool) -> int:
    if dry_run:
        row = pg_fetch_one(
            pg_conn,
            """
            SELECT count(*)
            FROM public.company_roles cr
            CROSS JOIN public.permissions p
            WHERE lower(cr.name) = lower(%s)
              AND NOT EXISTS (
                  SELECT 1
                  FROM public.permission_assignments pa
                  WHERE pa.permission_id = p.id
                    AND pa.subject_type = %s
                    AND pa.subject_id = cr.id
              )
            """,
            ("Super User", "company_role"),
        )
        count = int(row[0]) if row else 0
        logging.info("Dry-run: would assign all permissions to Super User company roles with %d new rows", count)
        return count

    with pg_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO public.permission_assignments (permission_id, subject_type, subject_id, created_at)
            SELECT p.id, %s, cr.id, now()
            FROM public.company_roles cr
            CROSS JOIN public.permissions p
            WHERE lower(cr.name) = lower(%s)
              AND NOT EXISTS (
                  SELECT 1
                  FROM public.permission_assignments pa
                  WHERE pa.permission_id = p.id
                    AND pa.subject_type = %s
                    AND pa.subject_id = cr.id
              )
            """,
            ("company_role", "Super User", "company_role"),
        )
        inserted = cur.rowcount
    return inserted


def migrate_permission_assignments(
    mysql_conn,
    pg_conn,
    company_map: Dict[int, str],
    company_role_map: Dict[Tuple[int, str], str],
    company_user_map: Dict[int, str],
    permission_map: Dict[str, str],
    dry_run: bool,
) -> int:
    logging.info("Migrating permission assignments")
    inserted = 0

    inserted += grant_all_permissions_to_super_user_roles(pg_conn, dry_run)

    # 1) Assign boolean access rights to company roles/profile names.
    access_rows = mysql_fetch_all(mysql_conn, "SELECT * FROM head_office_access_rights ORDER BY id")
    for r in access_rows:
        old_company_id = parse_int(r.get("head_office_id"))
        profile_name = clean_text(r.get("profile_name")) or DEFAULT_COMPANY_ROLE
        role_id = company_role_map.get((old_company_id, profile_name.lower()))
        if not role_id:
            continue

        for col in ACCESS_RIGHT_PERMISSION_COLUMNS:
            if truthy(r.get(col)):
                pid = permission_map.get(f"access_right:{col}")
                if insert_permission_assignment(pg_conn, pid, "company_role", role_id, r.get("created_at"), dry_run):
                    inserted += 1

    # 2) Assign permissions to individual company users where custom access rows exist.
    #    The source table itself only links head_office_user_id; permission detail comes from
    #    matching head_office_access_rights.custom_access_rights_id when present.
    direct_rows = mysql_fetch_all(
        mysql_conn,
        """
        SELECT houar.head_office_user_id, hoar.*
        FROM head_office_user_access_rights houar
        LEFT JOIN head_office_access_rights hoar
            ON hoar.custom_access_rights_id = houar.id
        ORDER BY houar.id
        """,
    )
    for r in direct_rows:
        old_hou_id = parse_int(r.get("head_office_user_id"))
        company_user_id = company_user_map.get(old_hou_id)
        if not company_user_id:
            continue
        for col in ACCESS_RIGHT_PERMISSION_COLUMNS:
            if truthy(r.get(col)):
                pid = permission_map.get(f"access_right:{col}")
                if insert_permission_assignment(pg_conn, pid, "company_user", company_user_id, r.get("created_at"), dry_run):
                    inserted += 1

    if not dry_run:
        pg_conn.commit()
    logging.info("Permission assignments inserted/skipped check complete. New assignments: %d", inserted)
    return inserted


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Show what would run without writing to Postgres")
    parser.add_argument("--skip-assignments", action="store_true", help="Skip public.permission_assignments migration")
    args = parser.parse_args()

    logging.info("Connecting to MySQL %s:%s/%s", MYSQL_HOST, MYSQL_PORT, MYSQL_DB)
    mysql_conn = connect_mysql()
    logging.info("Connecting to Postgres %s:%s/%s", PG_HOST, PG_PORT, PG_DB)
    pg_conn = connect_pg()

    try:
        role_map = upsert_roles(mysql_conn, pg_conn, args.dry_run)
        company_map = upsert_companies(mysql_conn, pg_conn, args.dry_run)
        user_map = upsert_users(mysql_conn, pg_conn, role_map, args.dry_run)
        company_role_map = upsert_company_roles(mysql_conn, pg_conn, company_map, args.dry_run)
        company_user_map = upsert_company_users(mysql_conn, pg_conn, company_map, user_map, company_role_map, args.dry_run)
        permission_map = upsert_permissions(mysql_conn, pg_conn, args.dry_run)

        if not args.skip_assignments:
            migrate_permission_assignments(
                mysql_conn,
                pg_conn,
                company_map,
                company_role_map,
                company_user_map,
                permission_map,
                args.dry_run,
            )

        logging.info("Migration finished")
        logging.info("Mappings loaded: roles=%d companies=%d users=%d company_roles=%d company_users=%d permissions=%d",
                     len(role_map), len(company_map), len(user_map), len(company_role_map), len(company_user_map), len(permission_map))
    finally:
        mysql_conn.close()
        pg_conn.close()


if __name__ == "__main__":
    main()
