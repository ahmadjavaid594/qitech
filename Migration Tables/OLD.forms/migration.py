#!/usr/bin/env python3
"""Migrate legacy form data from MySQL to Postgres form tables."""
import json
import logging
import os
import sys
import uuid
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

try:
    import pymysql.cursors
    import psycopg2
    import psycopg2.extras
except Exception as e:  # pragma: no cover - import guard
    logging.error("Missing Python dependency: %s", e)
    logging.error("Install dependencies: pip install pymysql psycopg2-binary")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

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
COMMIT_EVERY = int(os.getenv("COMMIT_EVERY", "50"))
SUBMISSION_CHUNK_SIZE = int(os.getenv("SUBMISSION_CHUNK_SIZE", "100"))
LEGACY_UUID_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "qitech:legacy-forms")


def parse_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


FORM_START_ID = parse_int(os.getenv("FORM_START_ID"))
FORM_ONLY_ID = parse_int(os.getenv("FORM_ONLY_ID"))


def parse_bool(value: Any) -> bool:
    return value in (1, "1", True, "t", "true", "True")


def sanitize_json(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, dict):
        return {str(k): sanitize_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [sanitize_json(item) for item in value]
    return str(value)


def to_json(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (TypeError, json.JSONDecodeError):
            return sanitize_json(value)
        return sanitize_json(parsed)
    return sanitize_json(value)


def json_param(value: Any) -> Any:
    if value is None:
        return None
    normalized = sanitize_json(value)
    return psycopg2.extras.Json(normalized)


def normalize_status(value: Any) -> str:
    if value is None:
        return "submitted"
    val = str(value).strip().lower()
    if val in {"draft", "incomplete", "in_progress", "pending"}:
        return "draft"
    if val in {"submitted", "complete", "completed", "approved", "closed"}:
        return "submitted"
    return "submitted"


def fetch_mysql_forms(connection, offset: int, limit: int) -> List[Dict[str, Any]]:
    conditions: List[str] = []
    params: List[Any] = []
    if FORM_ONLY_ID is not None:
        conditions.append("id = %s")
        params.append(FORM_ONLY_ID)
    elif FORM_START_ID is not None:
        conditions.append("id >= %s")
        params.append(FORM_START_ID)

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    with connection.cursor() as cur:
        cur.execute(
            f"""
            SELECT id, name, display_name, fields_updated_at, is_active, created_at, updated_at,
                   add_to_case_manager, hide_in_company_timeline, case_description_field,
                   reference_type, reference_id, is_external_link, external_link,
                   be_spoke_form_category_id, is_case_close_priority, case_close_priority_rule,
                   case_close_priority_value, case_close_priority_comment, requires_final_approval,
                   note, color_code, is_allow_non_approved_emails, is_archived, is_deleted,
                   deleted_at, purpose, allow_editing_state, allow_editing_time,
                   allow_responder_update, limits, active_limit_by_amount, amount_total_max_res,
                   limit_to_one_user, limit_to_one_location, limit_by_period_max_state,
                   limit_by_period_max_value, limit_by_period_min_state, limit_by_period_min_value,
                   active_limit_by_period, expiry_state, expiry_time, schedule_state,
                   schedule_by_day, allow_drafts_off_site, show_submission_loc, form_json,
                   submitable_to_nhs_lfpse, limit_by_per_user_value, limit_by_per_location_value,
                   case_must_review, org_groups, is_quick_report, is_qr_code, created_by_id,
                   updated_by_id, allow_update_time, deleted, soft_deleted, submission_text,
                   show_to_responder, is_draft, allow_update_state, generate_qr_code,
                   allow_delete_submission, delete_submission_time, allow_delete_select,
                   allow_user_to_share_case_log, form_label, delete_time_mode,
                   is_allow_case_handler_feedback, is_close_case_mandatory,
                   allow_print_by_site_team, allow_print_by_company_user,
                   show_in_site_timeline_site, show_in_site_timeline_company,
                   show_in_contact_timeline_company
            FROM be_spoke_form
            {where_clause}
            ORDER BY id
            LIMIT %s OFFSET %s
            """,
            (*params, limit, offset),
        )
        return cur.fetchall()


def fetch_form_related(mysql_conn, form_id: int) -> Dict[str, List[Dict[str, Any]]]:
    with mysql_conn.cursor() as cur:
        cur.execute(
            "SELECT id, stage_name, form_id, created_at, updated_at FROM be_spoke_form_stages WHERE form_id = %s ORDER BY id",
            (form_id,),
        )
        stages = cur.fetchall()

        cur.execute(
            "SELECT id, group_name, stage_id, created_at, updated_at FROM be_spoke_form_question_groups WHERE stage_id IN (SELECT id FROM be_spoke_form_stages WHERE form_id = %s) ORDER BY id",
            (form_id,),
        )
        question_groups = cur.fetchall()

        cur.execute(
            "SELECT id, question_id, condition_if_value, condition_value, condition_value_2, condition_action_type, created_at, updated_at, condition_action_value, condition_action_value_1 FROM be_spoke_form_action_conditions WHERE question_id IN (SELECT id FROM be_spoke_form_question_groups WHERE stage_id IN (SELECT id FROM be_spoke_form_stages WHERE form_id = %s)) ORDER BY id",
            (form_id,),
        )
        action_conditions = cur.fetchall()

    return {
        "stages": stages,
        "question_groups": question_groups,
        "action_conditions": action_conditions,
    }


def build_company_map(pg_conn, mysql_conn) -> Tuple[Dict[int, str], Optional[str]]:
    mapping: Dict[int, str] = {}
    with pg_conn.cursor() as cur:
        cur.execute("SELECT id, external_id FROM public.companies")
        companies = cur.fetchall()

    fallback_company_id = None
    for row in companies:
        if not row:
            continue
        company_id = str(row[0])
        if fallback_company_id is None:
            fallback_company_id = company_id
        external_id = row[1] if len(row) > 1 else None
        try:
            if external_id is not None:
                mapping[int(external_id)] = company_id
        except (TypeError, ValueError):
            pass

    with mysql_conn.cursor() as cur:
        cur.execute("SELECT id, company_name FROM head_offices")
        head_offices = cur.fetchall()

    for row in head_offices:
        old_id = parse_int(row.get("id"))
        if old_id is None:
            continue
        if old_id not in mapping:
            mapping[old_id] = fallback_company_id

    return {k: v for k, v in mapping.items() if v is not None}, fallback_company_id


def build_user_map(pg_conn) -> Dict[int, str]:
    mapping: Dict[int, str] = {}
    with pg_conn.cursor() as cur:
        cur.execute("SELECT id, external_id FROM public.users WHERE external_id IS NOT NULL")
        for row in cur.fetchall():
            if not row:
                continue
            try:
                external_id = row[1] if len(row) > 1 else None
                if external_id is not None:
                    mapping[int(external_id)] = str(row[0])
            except (TypeError, ValueError, IndexError):
                continue
    return mapping


def build_site_maps(pg_conn) -> Tuple[Dict[int, str], Dict[str, str]]:
    site_map: Dict[int, str] = {}
    site_company_map: Dict[str, str] = {}
    with pg_conn.cursor() as cur:
        cur.execute("SELECT id, external_id, company_id FROM public.sites WHERE external_id IS NOT NULL")
        for row in cur.fetchall():
            if not row:
                continue
            site_id = str(row[0])
            company_id = row[2] if len(row) > 2 else None
            if company_id is not None:
                site_company_map[site_id] = str(company_id)
            try:
                external_id = row[1] if len(row) > 1 else None
                if external_id is not None:
                    site_map[int(external_id)] = site_id
            except (TypeError, ValueError, IndexError):
                continue
    return site_map, site_company_map


def ensure_form_submission_external_id(pg_conn) -> None:
    with pg_conn.cursor() as cur:
        cur.execute("ALTER TABLE public.form_submissions ADD COLUMN IF NOT EXISTS external_id int8 NULL")
        cur.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS form_submissions_external_id_unique
            ON public.form_submissions (external_id)
            WHERE external_id IS NOT NULL
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS form_submission_answers_form_submission_id_index
            ON public.form_submission_answers (form_submission_id)
            """
        )
    pg_conn.commit()


def build_head_office_user_map(mysql_conn) -> Dict[int, int]:
    mapping: Dict[int, int] = {}
    with mysql_conn.cursor() as cur:
        cur.execute("SELECT id, user_id FROM head_office_users")
        for row in cur.fetchall():
            try:
                mapping[int(row.get("id"))] = int(row.get("user_id"))
            except (TypeError, ValueError):
                continue
    return mapping


LEGACY_BLOCK_TYPE_MAP = {
    "text": "shortAnswer",
    "textarea": "longAnswer",
    "select": "dropdown",
    "checkbox": "checkbox",
    "radio": "radio",
    "date": "date",
    "time": "time",
    "number": "number",
    "email": "email",
    "file": "fileUpload",
    "image": "fileUpload",
    "signature": "signature",
    "text_block": "content",
}


def convert_legacy_form_schema(schema: Dict[str, Any], form_row: Dict[str, Any]) -> Dict[str, Any]:
    """Convert the legacy pages/items document to sections/pages/blocks."""
    if isinstance(schema.get("sections"), list):
        return schema
    legacy_pages = schema.get("pages")
    if not isinstance(legacy_pages, list):
        return schema

    pages: List[Dict[str, Any]] = []
    for page_index, legacy_page in enumerate(legacy_pages):
        if not isinstance(legacy_page, dict):
            continue
        blocks: List[Dict[str, Any]] = []
        items = legacy_page.get("items")
        if not isinstance(items, list):
            items = []
        for item_index, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            input_config = item.get("input") if isinstance(item.get("input"), dict) else {}
            legacy_type = str(input_config.get("type") or item.get("type") or "text")
            item_id = str(item.get("id") if item.get("id") is not None else f"legacy-{page_index}-{item_index}")
            label = str(item.get("label") or item.get("name") or f"Question {item_id}")
            block: Dict[str, Any] = {
                "id": item_id,
                "type": LEGACY_BLOCK_TYPE_MAP.get(legacy_type, legacy_type),
                "name": str(item.get("name") or f"legacy_{item_id}"),
                "label": label,
                "isRequired": parse_bool(input_config.get("required")),
                "legacyConfig": sanitize_json(item),
            }
            options = input_config.get("options")
            if isinstance(options, list):
                block["options"] = [
                    {
                        "type": "option",
                        "value": str(option.get("value", option.get("val", option.get("id", "")))),
                        "label": str(option.get("label", option.get("text", option.get("val", "")))),
                    }
                    for option in options
                    if isinstance(option, dict)
                ]
            if input_config.get("placeholder") is not None:
                block["placeholder"] = input_config.get("placeholder")
            if input_config.get("conditions") is not None:
                block["conditions"] = sanitize_json(input_config.get("conditions"))
            blocks.append(block)

        page_id = str(legacy_page.get("id") if legacy_page.get("id") is not None else f"legacy-page-{page_index}")
        pages.append(
            {
                "id": page_id,
                "title": str(legacy_page.get("label") or legacy_page.get("name") or f"Page {page_index + 1}"),
                "blocks": blocks,
                "legacyConfig": sanitize_json({key: value for key, value in legacy_page.items() if key != "items"}),
            }
        )

    title = str(form_row.get("display_name") or form_row.get("name") or schema.get("name") or "Imported form")
    return {
        "title": title,
        "description": str(form_row.get("note") or ""),
        "sections": [{"id": f"legacy-section-{form_row.get('id')}", "title": title, "pages": pages}],
        "legacyFormMetadata": sanitize_json({key: value for key, value in schema.items() if key != "pages"}),
    }


def build_form_definition_schema(form_row: Dict[str, Any], related: Dict[str, List[Dict[str, Any]]]) -> Any:
    """Return the form document itself, which is what the form renderer consumes.

    The previous migration nested the document below ``legacy_form`` and placed
    relational metadata beside it.  That changed the schema's root shape and
    made otherwise valid imported definitions appear empty in the application.
    Legacy metadata is already represented in the original form JSON and does
    not belong at the renderable schema root.
    """
    del related  # fetched for legacy compatibility; it must not alter the schema shape
    schema = to_json(form_row.get("form_json"))
    if isinstance(schema, dict):
        return convert_legacy_form_schema(schema, form_row)
    return schema if isinstance(schema, list) else {}


def build_question_catalog(schema: Any) -> Dict[str, Dict[str, Any]]:
    """Index legacy question/block metadata found anywhere in a form schema."""
    catalog: Dict[str, Dict[str, Any]] = {}
    sort_order = 0

    def visit(value: Any) -> None:
        nonlocal sort_order
        if isinstance(value, dict):
            identifier = next(
                (
                    value.get(key)
                    for key in ("id", "question_id", "questionId", "block_id", "blockId", "key")
                    if value.get(key) is not None
                ),
                None,
            )
            label = next(
                (
                    value.get(key)
                    for key in ("label", "question", "title", "name", "text")
                    if isinstance(value.get(key), str) and value.get(key).strip()
                ),
                None,
            )
            block_type = next(
                (
                    value.get(key)
                    for key in ("type", "block_type", "blockType", "input_type", "inputType")
                    if value.get(key) is not None
                ),
                None,
            )
            if identifier is not None and (label is not None or block_type is not None):
                key = str(identifier)
                if key not in catalog:
                    catalog[key] = {
                        "label": str(label or f"Question {key}"),
                        "block_type": str(block_type or "legacy"),
                        "sort_order": sort_order,
                    }
                    sort_order += 1
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(schema)
    return catalog


def find_existing_form_definition(pg_conn, company_id: str, form_name: str) -> Optional[Tuple[str, Optional[str], Optional[str]]]:
    with pg_conn.cursor() as cur:
        cur.execute(
            """
            SELECT fd.id, fs.id AS schema_id, COALESCE(fs.current_version_id, latest_version.id) AS version_id
            FROM public.form_definitions fd
            LEFT JOIN public.form_schemas fs ON fs.form_definition_id = fd.id
            LEFT JOIN LATERAL (
                SELECT id
                FROM public.form_versions
                WHERE form_schema_id = fs.id
                ORDER BY version DESC, created_at DESC, id DESC
                LIMIT 1
            ) latest_version ON TRUE
            WHERE fd.company_id = %s AND fd.name = %s
            ORDER BY fd.updated_at DESC, latest_version.id DESC
            LIMIT 1
            """,
            (company_id, form_name),
        )
        row = cur.fetchone()

    if row is None:
        return None

    return (
        str(row[0]),
        str(row[1]) if row[1] is not None else None,
        str(row[2]) if row[2] is not None else None,
    )


def find_existing_form_definition_by_external_id(pg_conn, company_id: str, external_id: Optional[str]) -> Optional[Tuple[str, Optional[str], Optional[str]]]:
    if external_id is None:
        return None

    with pg_conn.cursor() as cur:
        cur.execute(
            """
            SELECT fd.id, fs.id AS schema_id, COALESCE(fs.current_version_id, latest_version.id) AS version_id
            FROM public.form_definitions fd
            LEFT JOIN public.form_schemas fs ON fs.form_definition_id = fd.id
            LEFT JOIN LATERAL (
                SELECT id
                FROM public.form_versions
                WHERE form_schema_id = fs.id
                ORDER BY version DESC, created_at DESC, id DESC
                LIMIT 1
            ) latest_version ON TRUE
            WHERE fd.company_id = %s AND fd.external_id = %s
            ORDER BY fd.updated_at DESC, latest_version.id DESC
            LIMIT 1
            """,
            (company_id, external_id),
        )
        row = cur.fetchone()

    if row is None:
        return None

    return (
        str(row[0]),
        str(row[1]) if row[1] is not None else None,
        str(row[2]) if row[2] is not None else None,
    )


def find_existing_form_definitions_by_external_id(pg_conn, company_id: str, external_id: Optional[str]) -> List[Tuple[str, Optional[str], Optional[str]]]:
    del company_id  # duplicate cleanup must cover older runs that used duplicate company UUIDs
    if external_id is None:
        return []

    with pg_conn.cursor() as cur:
        cur.execute(
            """
            SELECT fd.id, fs.id AS schema_id, COALESCE(fs.current_version_id, latest_version.id) AS version_id
            FROM public.form_definitions fd
            LEFT JOIN public.form_schemas fs ON fs.form_definition_id = fd.id
            LEFT JOIN LATERAL (
                SELECT id
                FROM public.form_versions
                WHERE form_schema_id = fs.id
                ORDER BY version DESC, created_at DESC, id DESC
                LIMIT 1
            ) latest_version ON TRUE
            WHERE fd.external_id = %s
            ORDER BY fd.updated_at DESC, latest_version.id DESC
            """,
            (external_id,),
        )
        rows = cur.fetchall()

    return [
        (
            str(row[0]),
            str(row[1]) if row[1] is not None else None,
            str(row[2]) if row[2] is not None else None,
        )
        for row in rows
    ]


def ensure_form_schema_and_version(
    pg_conn,
    form_definition_id: str,
    form_schema_id: Optional[str],
    form_version_id: Optional[str],
    created_at: Any,
    updated_at: Any,
    created_by_uuid: Optional[str],
) -> Tuple[str, str]:
    with pg_conn.cursor() as cur:
        if form_schema_id is None:
            form_schema_id = str(uuid.uuid4())
            cur.execute(
                """
                INSERT INTO public.form_schemas (id, form_definition_id, current_version_id, draft_version_id, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (form_schema_id, form_definition_id, None, None, created_at, updated_at),
            )

        if form_version_id is None:
            form_version_id = str(uuid.uuid4())
            cur.execute(
                """
                INSERT INTO public.form_versions (id, form_schema_id, version, description, status, published_at, review_at, current_schema_snapshot_id, created_by, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (form_version_id, form_schema_id, 1, "Migrated from legacy be_spoke_form", "published", created_at, None, None, created_by_uuid, created_at),
            )

        cur.execute(
            """
            UPDATE public.form_schemas
            SET current_version_id = %s, draft_version_id = %s, updated_at = %s
            WHERE id = %s
            """,
            (form_version_id, form_version_id, updated_at, form_schema_id),
        )

    return form_schema_id, form_version_id


def update_existing_form_definition_metadata(
    pg_conn,
    form_definition_id: str,
    form_row: Dict[str, Any],
    updated_by_uuid: Optional[str],
    updated_at: Any,
) -> None:
    with pg_conn.cursor() as cur:
        cur.execute(
            """
            UPDATE public.form_definitions
            SET description = %s,
                color = COALESCE(%s, color),
                purpose = COALESCE(%s, purpose),
                updated_by = COALESCE(%s, updated_by),
                updated_at = %s,
                deleted_at = %s,
                archived_at = %s,
                show_in_quick_report = %s,
                allow_print_site_team = %s,
                allow_print_company = %s
            WHERE id = %s
            """,
            (
                form_row.get("note"),
                form_row.get("color_code"),
                form_row.get("purpose"),
                updated_by_uuid,
                updated_at,
                form_row.get("deleted_at"),
                updated_at if parse_bool(form_row.get("is_archived")) else None,
                parse_bool(form_row.get("is_quick_report")),
                parse_bool(form_row.get("allow_print_by_site_team")),
                parse_bool(form_row.get("allow_print_by_company_user")),
                form_definition_id,
            ),
        )


def insert_form_definition(pg_conn, form_row: Dict[str, Any], company_id: str, user_map: Dict[int, str], head_office_user_map: Dict[int, int]) -> Tuple[str, str, str, str]:
    form_source_id = parse_int(form_row.get("id"))
    created_by_id = parse_int(form_row.get("created_by_id"))
    updated_by_id = parse_int(form_row.get("updated_by_id"))

    created_by_uuid = None
    updated_by_uuid = None
    if created_by_id is not None:
        source_user_id = head_office_user_map.get(created_by_id)
        if source_user_id is not None:
            created_by_uuid = user_map.get(source_user_id)
    if updated_by_id is not None:
        source_user_id = head_office_user_map.get(updated_by_id)
        if source_user_id is not None:
            updated_by_uuid = user_map.get(source_user_id)

    form_name = str(form_row.get("name") or f"legacy_form_{form_source_id}")
    external_id = str(form_source_id) if form_source_id is not None else None
    created_at = form_row.get("created_at") or datetime.now(timezone.utc)
    updated_at = form_row.get("updated_at") or datetime.now(timezone.utc)
    form_snapshot_id = str(uuid.uuid5(LEGACY_UUID_NAMESPACE, f"form_schema_snapshot:{form_source_id}"))

    existing = find_existing_form_definition_by_external_id(pg_conn, company_id, external_id)
    if existing is not None:
        existing_definition_id, existing_schema_id, existing_version_id = existing
        logging.info("Reusing existing form definition %s for legacy form %s via external_id %s", existing_definition_id, form_source_id, external_id)
        update_existing_form_definition_metadata(pg_conn, existing_definition_id, form_row, updated_by_uuid, updated_at)
        existing_schema_id, existing_version_id = ensure_form_schema_and_version(
            pg_conn,
            existing_definition_id,
            existing_schema_id,
            existing_version_id,
            created_at,
            updated_at,
            created_by_uuid,
        )
        return existing_definition_id, existing_schema_id, existing_version_id, form_snapshot_id

    form_definition_id = str(uuid.uuid4())
    form_schema_id = str(uuid.uuid4())
    form_version_id = str(uuid.uuid4())
    deleted_at = form_row.get("deleted_at")
    archived_at = created_at if parse_bool(form_row.get("is_archived")) else None

    with pg_conn.cursor() as cur:
        form_definition_values = (
            form_definition_id,
            company_id,
            external_id,
            form_name,
            created_at,
            updated_at,
            deleted_at,
            form_row.get("note"),
            None,
            "internal",
            "board",
            form_row.get("expiry_time"),
            None,
            bool(parse_int(form_row.get("generate_qr_code")) or parse_bool(form_row.get("is_qr_code"))),
            False,
            False,
            parse_bool(form_row.get("allow_drafts_off_site")),
            "creator",
            "disabled",
            None,
            "disabled",
            None,
            "disabled",
            None,
            parse_int(form_row.get("limits")) or parse_int(form_row.get("limit_by_per_user_value")),
            parse_int(form_row.get("limit_by_per_user_value")),
            parse_int(form_row.get("limit_by_per_location_value")),
            None,
            None,
            parse_bool(form_row.get("allow_print_by_site_team")),
            parse_bool(form_row.get("allow_print_by_company_user")),
            parse_bool(form_row.get("is_quick_report")),
            form_row.get("color_code") or "#000000",
            False,
            json_param({"sitesTimeline": {"columns": [], "enabled": False}, "companyTimeline": {"columns": [], "enabled": False}}),
            form_row.get("purpose"),
            created_by_uuid,
            updated_by_uuid,
            archived_at,
            form_row.get("case_close_priority_comment"),
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            json_param({}),
        )
        placeholders = ", ".join(["%s"] * len(form_definition_values))
        try:
            cur.execute(
                f"""
                INSERT INTO public.form_definitions (
                    id, company_id, external_id, name, created_at, updated_at, deleted_at, description, photo,
                    type, generate_as, expires_at, publish_at, generate_qr, capture_responder,
                    allow_drafts, allow_offsite_draft_completion, draft_visibility,
                    edit_after_submit_mode, edit_after_submit_minutes, responder_update_mode,
                    responder_update_minutes, responder_delete_mode, responder_delete_minutes,
                    submission_limit_total, submission_limit_per_user, submission_limit_per_site,
                    rate_limit_max, rate_limit_period_minutes, allow_print_site_team,
                    allow_print_company, show_in_quick_report, color, assign_all_org_units,
                    timeline_display_config, purpose, created_by, updated_by, archived_at,
                    deleted_reason, case_template_id, form_template_id, system_template_key,
                    last_acknowledged_template_version, pending_system_updates, integration_api_key,
                    integration_key_status, integration_key_approved_by, integration_key_approved_at,
                    integration_settings
                ) VALUES ({placeholders})
                """,
                form_definition_values,
            )
        except psycopg2.Error as exc:
            constraint_name = getattr(getattr(exc, "diag", None), "constraint_name", None)
            if constraint_name in {"form_definitions_company_id_name_index", "form_definitions_company_system_key_uq"} or "form_definitions_company_id_name_index" in str(exc):
                pg_conn.rollback()
                existing = find_existing_form_definition(pg_conn, company_id, form_name)
                if existing is not None:
                    existing_definition_id, existing_schema_id, existing_version_id = existing
                    update_existing_form_definition_metadata(pg_conn, existing_definition_id, form_row, updated_by_uuid, updated_at)
                    existing_schema_id, existing_version_id = ensure_form_schema_and_version(
                        pg_conn,
                        existing_definition_id,
                        existing_schema_id,
                        existing_version_id,
                        created_at,
                        updated_at,
                        created_by_uuid,
                    )
                    logging.info("Reusing existing form definition %s for company %s and name %s", existing_definition_id, company_id, form_name)
                    return existing_definition_id, existing_schema_id, existing_version_id, form_snapshot_id
            raise

        cur.execute(
            """
            INSERT INTO public.form_schemas (id, form_definition_id, current_version_id, draft_version_id, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (form_schema_id, form_definition_id, None, None, created_at, updated_at),
        )

        cur.execute(
            """
            INSERT INTO public.form_versions (id, form_schema_id, version, description, status, published_at, review_at, current_schema_snapshot_id, created_by, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (form_version_id, form_schema_id, 1, "Migrated from legacy be_spoke_form", "published", created_at, None, None, created_by_uuid, created_at),
        )

        cur.execute(
            """
            UPDATE public.form_schemas
            SET current_version_id = %s, draft_version_id = %s, updated_at = %s
            WHERE id = %s
            """,
            (form_version_id, form_version_id, updated_at, form_schema_id),
        )

    return form_definition_id, form_schema_id, form_version_id, form_snapshot_id


def insert_form_schema_snapshot(pg_conn, form_snapshot_id: str, schema_payload: Any, created_by_uuid: Optional[str], created_at: Any, form_version_id: str) -> None:
    with pg_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO public.form_schema_snapshots (id, schema, created_by, created_at, form_version_id, parent_snapshot_id)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                schema = EXCLUDED.schema,
                created_by = COALESCE(EXCLUDED.created_by, public.form_schema_snapshots.created_by),
                form_version_id = EXCLUDED.form_version_id
            """,
            (form_snapshot_id, json_param(schema_payload), created_by_uuid, created_at, form_version_id, None),
        )
        cur.execute(
            "UPDATE public.form_versions SET current_schema_snapshot_id = %s WHERE id = %s",
            (form_snapshot_id, form_version_id),
        )


def soft_delete_untraceable_submissions(pg_conn, form_definition_id: str, form_source_id: int) -> int:
    with pg_conn.cursor() as cur:
        cur.execute(
            """
            UPDATE public.form_submissions
            SET deleted_at = COALESCE(deleted_at, now()),
                updated_at = now()
            WHERE form_definition_id = %s
              AND external_id IS NULL
              AND deleted_at IS NULL
            """,
            (form_definition_id,),
        )
        deleted_count = cur.rowcount

    if deleted_count:
        logging.warning(
            "Soft-deleted %d untraceable submission(s) for legacy form %s",
            deleted_count,
            form_source_id,
        )
    return deleted_count


def refresh_duplicate_form_definitions(
    pg_conn,
    form_row: Dict[str, Any],
    company_id: str,
    schema_payload: Any,
    primary_form_definition_id: str,
    primary_form_version_id: str,
    primary_form_snapshot_id: str,
    user_map: Dict[int, str],
    head_office_user_map: Dict[int, int],
) -> int:
    """Backfill all existing duplicate definitions for this legacy form.

    Older migration runs could create/reuse more than one definition for the
    same legacy external_id.  Updating only the first match leaves stale rows in
    the UI with the old ``legacy_form`` wrapper, which looks like an empty form.
    """
    form_source_id = parse_int(form_row.get("id"))
    external_id = str(form_source_id) if form_source_id is not None else None
    if external_id is None:
        return 0

    created_at = form_row.get("created_at") or datetime.now(timezone.utc)
    updated_at = form_row.get("updated_at") or datetime.now(timezone.utc)
    created_by_id = parse_int(form_row.get("created_by_id"))
    updated_by_id = parse_int(form_row.get("updated_by_id"))
    created_by_uuid = user_map.get(head_office_user_map.get(created_by_id)) if created_by_id is not None else None
    updated_by_uuid = user_map.get(head_office_user_map.get(updated_by_id)) if updated_by_id is not None else None

    refreshed = 0
    for definition_id, schema_id, version_id in find_existing_form_definitions_by_external_id(pg_conn, company_id, external_id):
        update_existing_form_definition_metadata(pg_conn, definition_id, form_row, updated_by_uuid, updated_at)
        schema_id, version_id = ensure_form_schema_and_version(
            pg_conn,
            definition_id,
            schema_id,
            version_id,
            created_at,
            updated_at,
            created_by_uuid,
        )

        snapshot_id = primary_form_snapshot_id
        if definition_id != primary_form_definition_id or version_id != primary_form_version_id:
            snapshot_id = str(uuid.uuid5(LEGACY_UUID_NAMESPACE, f"form_schema_snapshot:{form_source_id}:{version_id}"))

        insert_form_schema_snapshot(pg_conn, snapshot_id, schema_payload, created_by_uuid, created_at, version_id)
        soft_delete_untraceable_submissions(pg_conn, definition_id, form_source_id)
        refreshed += 1

    return refreshed


def insert_form_submissions(
    pg_conn,
    mysql_conn,
    form_definition_id: str,
    form_version_id: str,
    form_snapshot_id: str,
    form_source_id: int,
    form_company_id: Optional[str],
    user_map: Dict[int, str],
    site_map: Dict[int, str],
    site_company_map: Dict[str, str],
) -> int:
    question_catalog: Dict[str, Dict[str, Any]] = {}
    with pg_conn.cursor() as cur:
        cur.execute(
            "SELECT schema FROM public.form_schema_snapshots WHERE id = %s",
            (form_snapshot_id,),
        )
        schema_row = cur.fetchone()
        if schema_row is not None:
            question_catalog = build_question_catalog(schema_row[0])

        cur.execute(
            """
            SELECT COUNT(*) AS total, COUNT(external_id) AS with_external_id
            FROM public.form_submissions
            WHERE form_definition_id = %s
            """,
            (form_definition_id,),
        )
        existing_total, existing_with_external_id = cur.fetchone()

    if existing_total and existing_total > existing_with_external_id:
        untraceable_total = existing_total - existing_with_external_id
        logging.warning(
            "Soft-deleting %d untraceable submission(s) for legacy form %s before canonical remigration",
            untraceable_total,
            form_source_id,
        )
        soft_delete_untraceable_submissions(pg_conn, form_definition_id, form_source_id)

    inserted = 0
    with mysql_conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) AS total FROM be_spoke_form_records WHERE form_id = %s",
            (form_source_id,),
        )
        count_row = cur.fetchone()
        total_records = int(count_row.get("total") or 0)

    if total_records:
        logging.info("Migrating form %s submissions: %d record(s)", form_source_id, total_records)

    for start in range(0, total_records, SUBMISSION_CHUNK_SIZE):
        with mysql_conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, form_id, location_id, reported_location_id, user_id, priority, created_at, updated_at,
                       status, case_status, hide, json_submission, raw_form, record_id, linked_forms,
                       hide_in_company_timeline, deleted_at, is_deleted, is_qr, is_show_reported_site,
                       display_submission, count_submission, count_submission_external, case_summary,
                       location_summary, form_involved_sites
                FROM be_spoke_form_records
                WHERE form_id = %s
                ORDER BY id
                LIMIT %s OFFSET %s
                """,
                (form_source_id, SUBMISSION_CHUNK_SIZE, start),
            )
            chunk = cur.fetchall()

        submission_rows: List[Tuple[Any, ...]] = []
        revision_rows: List[Tuple[Any, ...]] = []
        answer_rows: List[Tuple[Any, ...]] = []
        record_ids = [record.get("id") for record in chunk if record.get("id") is not None]
        answers_by_record_id: Dict[Any, List[Dict[str, Any]]] = {record_id: [] for record_id in record_ids}

        if record_ids:
            placeholders = ", ".join(["%s"] * len(record_ids))
            with mysql_conn.cursor() as data_cur:
                data_cur.execute(
                    f"""
                    SELECT id, record_id, question_id, question_value, created_at, updated_at
                    FROM be_spoke_form_record_data
                    WHERE record_id IN ({placeholders})
                    ORDER BY record_id, id
                    """,
                    tuple(record_ids),
                )
                for answer in data_cur.fetchall():
                    answers_by_record_id.setdefault(answer.get("record_id"), []).append(answer)

        for record in chunk:
            source_user_id = parse_int(record.get("user_id"))
            source_location_id = parse_int(record.get("location_id"))
            submitted_by_id = user_map.get(source_user_id) if source_user_id is not None else None
            site_id = site_map.get(source_location_id) if source_location_id is not None else None
            company_id = site_company_map.get(site_id) if site_id is not None else None
            company_id = company_id or form_company_id

            if company_id is None:
                logging.warning("Skipping submission %s because no matching company/site mapping was found", record.get("id"))
                continue

            source_record_id = record.get("id")
            submission_id = str(uuid.uuid5(LEGACY_UUID_NAMESPACE, f"form_submission:{source_record_id}"))
            created_at = record.get("created_at") or datetime.now(timezone.utc)
            updated_at = record.get("updated_at") or datetime.now(timezone.utc)
            deleted_at = record.get("deleted_at")
            submission_status = normalize_status(record.get("status"))

            submission_rows.append(
                (
                    submission_id,
                    source_record_id,
                    company_id,
                    form_definition_id,
                    form_snapshot_id,
                    submission_status,
                    submitted_by_id,
                    site_id,
                    None,
                    created_at,
                    created_at,
                    updated_at,
                    deleted_at,
                    form_version_id,
                )
            )
            revision_rows.append(
                (
                    str(uuid.uuid5(LEGACY_UUID_NAMESPACE, f"form_submission_revision:{source_record_id}:1")),
                    submission_id,
                    form_snapshot_id,
                    json_param(to_json(record.get("json_submission")) or to_json(record.get("raw_form")) or {}),
                    1,
                    submitted_by_id,
                    updated_at,
                    form_version_id,
                )
            )

            for answer in answers_by_record_id.get(record.get("id"), []):
                question_key = str(answer.get("question_id") or "legacy-question")
                question = question_catalog.get(question_key, {})
                raw_value = to_json(answer.get("question_value"))
                if raw_value is None:
                    raw_value = {}
                display_value = answer.get("question_value")
                if display_value is None:
                    display_value = ""
                elif isinstance(display_value, (dict, list, int, float, bool)):
                    display_value = json.dumps(display_value)
                elif not isinstance(display_value, str):
                    display_value = str(display_value)

                answer_rows.append(
                    (
                        str(uuid.uuid5(LEGACY_UUID_NAMESPACE, f"form_submission_answer:{answer.get('id')}")),
                        submission_id,
                        question_key,
                        question.get("block_type", "legacy"),
                        question.get("label", f"Legacy question {answer.get('question_id')}"),
                        json_param(raw_value),
                        display_value,
                        None,
                        question.get("sort_order", 0),
                        answer.get("created_at") or created_at,
                        answer.get("updated_at") or created_at,
                    )
                )

            inserted += 1

        if submission_rows:
            with pg_conn.cursor() as cur:
                psycopg2.extras.execute_values(
                    cur,
                    """
                    INSERT INTO public.form_submissions (
                        id, external_id, company_id, form_definition_id, form_version_schema_snapshot_id, status,
                        submitted_by_id, site_id, case_id, submitted_at, created_at, updated_at,
                        deleted_at, form_version_id
                    ) VALUES %s
                    ON CONFLICT (external_id) WHERE external_id IS NOT NULL DO UPDATE SET
                        company_id = EXCLUDED.company_id,
                        form_definition_id = EXCLUDED.form_definition_id,
                        form_version_schema_snapshot_id = EXCLUDED.form_version_schema_snapshot_id,
                        status = EXCLUDED.status,
                        submitted_by_id = EXCLUDED.submitted_by_id,
                        site_id = EXCLUDED.site_id,
                        case_id = EXCLUDED.case_id,
                        submitted_at = EXCLUDED.submitted_at,
                        updated_at = EXCLUDED.updated_at,
                        deleted_at = EXCLUDED.deleted_at,
                        form_version_id = EXCLUDED.form_version_id
                    """,
                    submission_rows,
                    page_size=500,
                )

        if revision_rows:
            with pg_conn.cursor() as cur:
                psycopg2.extras.execute_values(
                    cur,
                    """
                    INSERT INTO public.form_submission_revisions (
                        id, form_submission_id, form_version_schema_snapshot_id, data, revision,
                        edited_by_id, edited_at, form_version_id
                    ) VALUES %s
                    ON CONFLICT (id) DO UPDATE SET
                        form_version_schema_snapshot_id = EXCLUDED.form_version_schema_snapshot_id,
                        data = EXCLUDED.data,
                        edited_by_id = EXCLUDED.edited_by_id,
                        edited_at = EXCLUDED.edited_at,
                        form_version_id = EXCLUDED.form_version_id
                    """,
                    revision_rows,
                    page_size=500,
                )

        if answer_rows:
            with pg_conn.cursor() as cur:
                psycopg2.extras.execute_values(
                    cur,
                    """
                    INSERT INTO public.form_submission_answers (
                        id, form_submission_id, block_id, block_type, label, raw_value, display_value,
                        summary_context, sort_order, created_at, updated_at
                    ) VALUES %s
                    ON CONFLICT (id) DO UPDATE SET
                        block_id = EXCLUDED.block_id,
                        block_type = EXCLUDED.block_type,
                        label = EXCLUDED.label,
                        raw_value = EXCLUDED.raw_value,
                        display_value = EXCLUDED.display_value,
                        sort_order = EXCLUDED.sort_order,
                        updated_at = EXCLUDED.updated_at
                    """,
                    answer_rows,
                    page_size=500,
                )

        logging.info(
            "Processed form %s submissions %d-%d of %d",
            form_source_id,
            start + 1,
            min(start + len(chunk), total_records),
            total_records,
        )

    return inserted


def main(dry_run: bool = False):
    logging.info("Connecting to MySQL %s:%s/%s", MYSQL_HOST, MYSQL_PORT, MYSQL_DB)
    mysql_conn = pymysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DB,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )

    logging.info("Connecting to Postgres %s:%s/%s", PG_HOST, PG_PORT, PG_DB)
    pg_conn = psycopg2.connect(host=PG_HOST, port=PG_PORT, user=PG_USER, password=PG_PASSWORD, dbname=PG_DB)

    try:
        ensure_form_submission_external_id(pg_conn)
        company_map, fallback_company_id = build_company_map(pg_conn, mysql_conn)
        user_map = build_user_map(pg_conn)
        site_map, site_company_map = build_site_maps(pg_conn)
        head_office_user_map = build_head_office_user_map(mysql_conn)
        logging.info("Loaded %d companies, %d users, %d sites, %d head-office-user mappings", len(company_map), len(user_map), len(site_map), len(head_office_user_map))

        offset = 0
        migrated_forms = 0
        migrated_submissions = 0
        forms_since_commit = 0
        while True:
            forms = fetch_mysql_forms(mysql_conn, offset, BATCH_SIZE)
            if not forms:
                break

            for form_row in forms:
                source_form_id = parse_int(form_row.get("id"))
                if source_form_id is None:
                    continue

                reference_type = str(form_row.get("reference_type") or "").strip().lower()
                reference_id = parse_int(form_row.get("reference_id"))
                company_id = None
                if reference_type in {"head_office", "company"} and reference_id is not None:
                    company_id = company_map.get(reference_id)

                if company_id is None:
                    company_id = fallback_company_id

                if company_id is None:
                    logging.warning("Skipping form %s because no matching company was found", source_form_id)
                    continue

                try:
                    related = fetch_form_related(mysql_conn, source_form_id)
                    schema_payload = build_form_definition_schema(form_row, related)
                    form_definition_id, form_schema_id, form_version_id, form_snapshot_id = insert_form_definition(pg_conn, form_row, company_id, user_map, head_office_user_map)
                    insert_form_schema_snapshot(pg_conn, form_snapshot_id, schema_payload, None, form_row.get("created_at") or datetime.now(timezone.utc), form_version_id)
                    refreshed_definitions = refresh_duplicate_form_definitions(
                        pg_conn,
                        form_row,
                        company_id,
                        schema_payload,
                        form_definition_id,
                        form_version_id,
                        form_snapshot_id,
                        user_map,
                        head_office_user_map,
                    )
                    submissions_count = insert_form_submissions(pg_conn, mysql_conn, form_definition_id, form_version_id, form_snapshot_id, source_form_id, company_id, user_map, site_map, site_company_map)
                    pg_conn.commit()
                    migrated_forms += 1
                    migrated_submissions += submissions_count
                    forms_since_commit += 1
                    if forms_since_commit >= COMMIT_EVERY:
                        pg_conn.commit()
                        forms_since_commit = 0
                    logging.info("Migrated form %s with %d submissions; refreshed %d definition(s)", source_form_id, submissions_count, refreshed_definitions)
                except Exception:  # pragma: no cover - runtime guard
                    pg_conn.rollback()
                    logging.exception("Skipping form %s due to error", source_form_id)
                    continue

            offset += BATCH_SIZE

        if forms_since_commit:
            pg_conn.commit()
        logging.info("Completed. Migrated %d forms and %d submissions", migrated_forms, migrated_submissions)

    finally:
        mysql_conn.close()
        pg_conn.close()


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    main(dry_run=dry)
