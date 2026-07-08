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

PG_HOST = os.getenv("PG_HOST", "qitech-pg-test-17943.postgres.database.azure.com")
PG_PORT = int(os.getenv("PG_PORT", "5432"))
PG_USER = os.getenv("PG_USER", "pgadmin")
PG_PASSWORD = os.getenv("PG_PASSWORD", "2fac05f6ac12e581bc2aeb8bc188deac")
PG_DB = os.getenv("PG_DB", "qi-tech")

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
    if isinstance(normalized, (dict, list)):
        return psycopg2.extras.Json(normalized)
    return normalized


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


def build_form_definition_schema(form_row: Dict[str, Any], related: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "legacy_form": to_json(form_row.get("form_json")) or {},
        "stages": [to_json(dict(item)) for item in related.get("stages", [])],
        "question_groups": [to_json(dict(item)) for item in related.get("question_groups", [])],
        "action_conditions": [to_json(dict(item)) for item in related.get("action_conditions", [])],
    }
    return payload


def find_existing_form_definition(pg_conn, company_id: str, form_name: str) -> Optional[Tuple[str, Optional[str], Optional[str]]]:
    with pg_conn.cursor() as cur:
        cur.execute(
            """
            SELECT fd.id, fs.id AS schema_id, fv.id AS version_id
            FROM public.form_definitions fd
            LEFT JOIN public.form_schemas fs ON fs.form_definition_id = fd.id
            LEFT JOIN public.form_versions fv ON fv.form_schema_id = fs.id
            WHERE fd.company_id = %s AND fd.name = %s
            ORDER BY fd.updated_at DESC, fv.created_at DESC, fv.id DESC
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
            SELECT fd.id, fs.id AS schema_id, fv.id AS version_id
            FROM public.form_definitions fd
            LEFT JOIN public.form_schemas fs ON fs.form_definition_id = fd.id
            LEFT JOIN public.form_versions fv ON fv.form_schema_id = fs.id
            WHERE fd.company_id = %s AND fd.external_id = %s
            ORDER BY fd.updated_at DESC, fv.created_at DESC, fv.id DESC
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

    existing = find_existing_form_definition_by_external_id(pg_conn, company_id, external_id)
    if existing is not None:
        existing_definition_id, existing_schema_id, existing_version_id = existing
        logging.info("Reusing existing form definition %s for legacy form %s via external_id %s", existing_definition_id, form_source_id, external_id)
        if existing_schema_id is None:
            existing_schema_id = str(uuid.uuid4())
            with pg_conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO public.form_schemas (id, form_definition_id, current_version_id, draft_version_id, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (existing_schema_id, existing_definition_id, None, None, created_at, updated_at),
                )
        if existing_version_id is None:
            existing_version_id = str(uuid.uuid4())
            with pg_conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO public.form_versions (id, form_schema_id, version, description, status, published_at, review_at, current_schema_snapshot_id, created_by, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (existing_version_id, existing_schema_id, 1, "Migrated from legacy be_spoke_form", "published", created_at, None, None, created_by_uuid, created_at),
                )
                cur.execute(
                    """
                    UPDATE public.form_schemas
                    SET current_version_id = %s, draft_version_id = %s, updated_at = %s
                    WHERE id = %s
                    """,
                    (existing_version_id, existing_version_id, updated_at, existing_schema_id),
                )
        return existing_definition_id, existing_schema_id, existing_version_id, str(uuid.uuid4())

    form_definition_id = str(uuid.uuid4())
    form_schema_id = str(uuid.uuid4())
    form_version_id = str(uuid.uuid4())
    form_snapshot_id = str(uuid.uuid4())

    created_at = form_row.get("created_at") or datetime.now(timezone.utc)
    updated_at = form_row.get("updated_at") or datetime.now(timezone.utc)
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
                    if existing_schema_id is None:
                        existing_schema_id = str(uuid.uuid4())
                        cur.execute(
                            """
                            INSERT INTO public.form_schemas (id, form_definition_id, current_version_id, draft_version_id, created_at, updated_at)
                            VALUES (%s, %s, %s, %s, %s, %s)
                            """,
                            (existing_schema_id, existing_definition_id, None, None, created_at, updated_at),
                        )
                    if existing_version_id is None:
                        existing_version_id = str(uuid.uuid4())
                        cur.execute(
                            """
                            INSERT INTO public.form_versions (id, form_schema_id, version, description, status, published_at, review_at, current_schema_snapshot_id, created_by, created_at)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            """,
                            (existing_version_id, existing_schema_id, 1, "Migrated from legacy be_spoke_form", "published", created_at, None, None, created_by_uuid, created_at),
                        )
                        cur.execute(
                            """
                            UPDATE public.form_schemas
                            SET current_version_id = %s, draft_version_id = %s, updated_at = %s
                            WHERE id = %s
                            """,
                            (existing_version_id, existing_version_id, updated_at, existing_schema_id),
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


def insert_form_schema_snapshot(pg_conn, form_snapshot_id: str, schema_payload: Dict[str, Any], created_by_uuid: Optional[str], created_at: Any, form_version_id: str) -> None:
    with pg_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO public.form_schema_snapshots (id, schema, created_by, created_at, form_version_id, parent_snapshot_id)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (form_snapshot_id, json_param(schema_payload), created_by_uuid, created_at, form_version_id, None),
        )
        cur.execute(
            "UPDATE public.form_versions SET current_schema_snapshot_id = %s WHERE id = %s",
            (form_snapshot_id, form_version_id),
        )


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
    with pg_conn.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*) AS total, COUNT(external_id) AS with_external_id
            FROM public.form_submissions
            WHERE form_definition_id = %s
            """,
            (form_definition_id,),
        )
        existing_total, existing_with_external_id = cur.fetchone()

    if existing_total and not existing_with_external_id:
        logging.warning(
            "Skipping submissions for legacy form %s because %d submission(s) already exist without external_id",
            form_source_id,
            existing_total,
        )
        return 0

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
            """,
            (form_source_id,),
        )
        records = cur.fetchall()

    inserted = 0
    total_records = len(records)
    if total_records:
        logging.info("Migrating form %s submissions: %d record(s)", form_source_id, total_records)

    for start in range(0, total_records, SUBMISSION_CHUNK_SIZE):
        chunk = records[start:start + SUBMISSION_CHUNK_SIZE]
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
                    json_param(to_json(record.get("raw_form")) or to_json(record.get("json_submission")) or {}),
                    1,
                    submitted_by_id,
                    updated_at,
                    form_version_id,
                )
            )

            for answer in answers_by_record_id.get(record.get("id"), []):
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
                        str(answer.get("question_id") or "legacy-question"),
                        "legacy",
                        f"Legacy question {answer.get('question_id')}",
                        json_param(raw_value),
                        display_value,
                        None,
                        0,
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
                    ON CONFLICT (id) DO NOTHING
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
                    ON CONFLICT (id) DO NOTHING
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
                    submissions_count = insert_form_submissions(pg_conn, mysql_conn, form_definition_id, form_version_id, form_snapshot_id, source_form_id, company_id, user_map, site_map, site_company_map)
                    pg_conn.commit()
                    migrated_forms += 1
                    migrated_submissions += submissions_count
                    forms_since_commit += 1
                    if forms_since_commit >= COMMIT_EVERY:
                        pg_conn.commit()
                        forms_since_commit = 0
                    logging.info("Migrated form %s with %d submissions", source_form_id, submissions_count)
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
