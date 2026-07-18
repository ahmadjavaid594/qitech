#!/usr/bin/env python3
"""Migrate MySQL `qitech.location_tags` to Postgres `public.tags` and `public.site_tag`.

Uses:
- `public.companies.external_id` to resolve source `head_office_id`
- `public.sites.external_id` to resolve source `location_id`
- `public.tags.external_id` to store source `location_tags.id`
"""
import os
import sys
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

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


def normalize_color(value: Any, default: str) -> str:
    return normalize_text(value) or default


def normalize_icon(value: Any) -> str:
    icon_number = parse_int(value)
    if icon_number is None or icon_number <= 0:
        return "tag-01"
    return f"tag-{icon_number:02d}"


def lookup_key(company_id: str, name: str) -> Tuple[str, str]:
    return company_id, name.strip().lower()


def fetch_mysql_rows(connection, offset: int, limit: int) -> List[Dict[str, Any]]:
    with connection.cursor() as cur:
        cur.execute(
            """
            SELECT id, head_office_id, name, color, created_at, updated_at,
                   location_id, icon, icon_color, text_color
            FROM location_tags
            ORDER BY id
            LIMIT %s OFFSET %s
            """,
            (limit, offset),
        )
        return cur.fetchall()


def build_company_map(pg_conn) -> Dict[int, str]:
    with pg_conn.cursor() as cur:
        cur.execute("SELECT id::text, external_id FROM public.companies WHERE external_id IS NOT NULL")
        mapping: Dict[int, str] = {}
        for company_id, external_id in cur.fetchall():
            source_id = parse_int(external_id)
            if source_id is not None:
                mapping[source_id] = company_id
        return mapping


def build_site_map(pg_conn) -> Dict[int, Tuple[str, str]]:
    with pg_conn.cursor() as cur:
        cur.execute(
            """
            SELECT external_id, id::text, company_id::text
            FROM public.sites
            WHERE external_id IS NOT NULL
            """
        )
        mapping: Dict[int, Tuple[str, str]] = {}
        for external_id, site_id, company_id in cur.fetchall():
            source_id = parse_int(external_id)
            if source_id is not None:
                mapping[source_id] = (site_id, company_id)
        return mapping


def get_tag_type(pg_conn) -> str:
    with pg_conn.cursor() as cur:
        cur.execute(
            """
            SELECT e.enumlabel
            FROM pg_enum e
            JOIN pg_type t ON t.oid = e.enumtypid
            WHERE t.typname = 'tag_type'
            ORDER BY e.enumsortorder
            """
        )
        values = [row[0] for row in cur.fetchall()]
    if not values:
        raise ValueError("Postgres enum public.tag_type has no values")
    for preferred in ("site", "location"):
        if preferred in values:
            return preferred
    logging.warning("Neither 'site' nor 'location' exists in public.tag_type; using %r", values[0])
    return values[0]


def build_existing_tag_maps(pg_conn, tag_type: str) -> Tuple[Dict[int, str], Dict[Tuple[str, str], str]]:
    external_map: Dict[int, str] = {}
    natural_map: Dict[Tuple[str, str], str] = {}
    with pg_conn.cursor() as cur:
        cur.execute(
            """
            SELECT id::text, external_id, company_id::text, name
            FROM public.tags
            WHERE category_id IS NULL
              AND parent_id IS NULL
              AND "type" = %s::public.tag_type
            """,
            (tag_type,),
        )
        for tag_id, external_id, company_id, name in cur.fetchall():
            source_id = parse_int(external_id)
            if source_id is not None:
                external_map[source_id] = tag_id
            if name is not None:
                natural_map[lookup_key(company_id, name)] = tag_id
    return external_map, natural_map


def build_existing_site_tags(pg_conn) -> set[Tuple[str, str]]:
    with pg_conn.cursor() as cur:
        cur.execute("SELECT site_id::text, tag_id::text FROM public.site_tag")
        return {(site_id, tag_id) for site_id, tag_id in cur.fetchall()}


def transform_row(
    row: Dict[str, Any],
    company_map: Dict[int, str],
    site_map: Dict[int, Tuple[str, str]],
    tag_type: str,
) -> Dict[str, Any]:
    source_id = row.get("id")
    name = normalize_text(row.get("name"))
    if not name:
        raise ValueError(f"location_tags row {source_id} is missing name")

    head_office_id = parse_int(row.get("head_office_id"))
    if head_office_id is None or head_office_id not in company_map:
        raise ValueError(f"Unable to resolve company for head_office_id {row.get('head_office_id')}")
    company_id = company_map[head_office_id]

    location_id = parse_int(row.get("location_id"))
    if location_id is None or location_id not in site_map:
        raise ValueError(f"Unable to resolve site for location_id {row.get('location_id')}")
    site_id, site_company_id = site_map[location_id]

    if site_company_id != company_id:
        logging.warning(
            "location_tags row %s maps head_office_id %s to company %s but location_id %s belongs to company %s",
            source_id,
            head_office_id,
            company_id,
            location_id,
            site_company_id,
        )

    now = datetime.now(timezone.utc)
    return {
        "source_id": source_id,
        "external_id": parse_int(source_id),
        "site_id": site_id,
        "company_id": company_id,
        "name": name,
        "parent_id": None,
        "category_id": None,
        "order": 0,
        "type": tag_type,
        "text_color": normalize_color(row.get("text_color"), "#FFFFFF"),
        "background_color": normalize_color(row.get("color"), "#000000"),
        "icon": normalize_icon(row.get("icon")),
        "icon_color": normalize_color(row.get("icon_color"), "#000000"),
        "visibility": "all",
        "priority": 1,
        "display": "main_only",
        "permission": "all",
        "created_at": row.get("created_at") or now,
        "updated_at": row.get("updated_at") or now,
        "archived_at": None,
    }


def insert_tags(
    pg_conn,
    rows: List[Dict[str, Any]],
    existing_tag_external_ids: Dict[int, str],
    existing_tag_keys: Dict[Tuple[str, str], str],
) -> int:
    inserted = 0
    with pg_conn.cursor() as cur:
        for row in rows:
            external_id = row["external_id"]
            if external_id is not None and external_id in existing_tag_external_ids:
                row["tag_id"] = existing_tag_external_ids[external_id]
                continue

            key = lookup_key(row["company_id"], row["name"])
            if key in existing_tag_keys:
                tag_id = existing_tag_keys[key]
                row["tag_id"] = tag_id
                if external_id is not None:
                    cur.execute(
                        """
                        UPDATE public.tags
                        SET external_id = COALESCE(external_id, %s)
                        WHERE id = %s
                        """,
                        (external_id, tag_id),
                    )
                    existing_tag_external_ids[external_id] = tag_id
                continue

            cur.execute(
                """
                INSERT INTO public.tags (
                    external_id, name, company_id, parent_id, category_id, "order", "type",
                    text_color, background_color, icon, icon_color, visibility,
                    priority, display, "permission", created_at, updated_at, archived_at
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s::public.tag_type,
                    %s, %s, %s, %s, %s::public.tag_visibility,
                    %s, %s::public.tag_display, %s::public.tag_permission,
                    %s, %s, %s
                )
                RETURNING id::text
                """,
                (
                    row["external_id"],
                    row["name"],
                    row["company_id"],
                    row["parent_id"],
                    row["category_id"],
                    row["order"],
                    row["type"],
                    row["text_color"],
                    row["background_color"],
                    row["icon"],
                    row["icon_color"],
                    row["visibility"],
                    row["priority"],
                    row["display"],
                    row["permission"],
                    row["created_at"],
                    row["updated_at"],
                    row["archived_at"],
                ),
            )
            tag_id = cur.fetchone()[0]
            row["tag_id"] = tag_id
            if external_id is not None:
                existing_tag_external_ids[external_id] = tag_id
            existing_tag_keys[key] = tag_id
            inserted += 1
    return inserted


def insert_site_tags(pg_conn, rows: List[Dict[str, Any]], existing_site_tags: set[Tuple[str, str]]) -> int:
    values = []
    for row in rows:
        tag_id = row.get("tag_id")
        if not tag_id:
            continue
        key = (row["site_id"], tag_id)
        if key in existing_site_tags:
            continue
        values.append(key)
        existing_site_tags.add(key)

    if not values:
        return 0

    sql = """
        INSERT INTO public.site_tag (site_id, tag_id)
        VALUES %s
        ON CONFLICT (site_id, tag_id) DO NOTHING
    """
    with pg_conn.cursor() as cur:
        psycopg2.extras.execute_values(cur, sql, values, template="(%s,%s)")
    return len(values)


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
        site_map = build_site_map(pg_conn)
        tag_type = get_tag_type(pg_conn)
        existing_tag_external_ids, existing_tag_keys = build_existing_tag_maps(pg_conn, tag_type)
        existing_site_tags = build_existing_site_tags(pg_conn)
        logging.info(
            "Loaded %d companies, %d sites, %d existing tag external_ids, %d existing tag keys, %d existing site_tag rows; using tag_type=%r",
            len(company_map),
            len(site_map),
            len(existing_tag_external_ids),
            len(existing_tag_keys),
            len(existing_site_tags),
            tag_type,
        )

        offset = 0
        total_tags_inserted = 0
        total_site_tags_inserted = 0
        total_skipped = 0
        while True:
            rows = fetch_mysql_rows(mysql_conn, offset, BATCH_SIZE)
            if not rows:
                break

            transformed = []
            for row in rows:
                try:
                    transformed.append(transform_row(row, company_map, site_map, tag_type))
                except ValueError as exc:
                    total_skipped += 1
                    logging.warning("Skipping location_tags row %s: %s", row.get("id"), exc)

            if dry_run:
                new_tags = sum(
                    1
                    for row in transformed
                    if row["external_id"] not in existing_tag_external_ids
                    and lookup_key(row["company_id"], row["name"]) not in existing_tag_keys
                )
                logging.info(
                    "Dry-run: would process %d rows, insert up to %d tags, and insert site_tag rows for offset %d",
                    len(transformed),
                    new_tags,
                    offset,
                )
            else:
                tags_inserted = insert_tags(pg_conn, transformed, existing_tag_external_ids, existing_tag_keys)
                site_tags_inserted = insert_site_tags(pg_conn, transformed, existing_site_tags)
                pg_conn.commit()
                total_tags_inserted += tags_inserted
                total_site_tags_inserted += site_tags_inserted
                logging.info(
                    "Inserted %d tags and %d site_tag rows (offset %d)",
                    tags_inserted,
                    site_tags_inserted,
                    offset,
                )

            offset += BATCH_SIZE

        logging.info(
            "Done. Total tags inserted: %d. Total site_tag rows inserted: %d. Total skipped: %d",
            total_tags_inserted,
            total_site_tags_inserted,
            total_skipped,
        )

    finally:
        mysql_conn.close()
        pg_conn.close()


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    main(dry_run=dry)
