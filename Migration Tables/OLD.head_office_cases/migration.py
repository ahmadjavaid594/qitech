#!/usr/bin/env python3
"""
Comprehensive Migration: Old System (MySQL) -> New System (Postgres)
Covers: Templates, Statuses, Workflows, Cases, Case Statuses, Closing Reasons, 
        Case Stages, and Investigator Groups (Handlers).
Includes strict deduplication for templates and circular FK resolution.
"""
import os
import sys
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple, Optional

try:
    import pymysql.cursors
    import psycopg2
    import psycopg2.extras
except Exception as e:
    logging.error("Missing Python dependency: %s", e)
    logging.error("Install dependencies: pip install pymysql psycopg2-binary")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# --- Configuration ---
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

BATCH_SIZE = int(os.getenv("BATCH_SIZE", "500"))

def build_maps(pg_conn) -> Tuple[Dict, Dict, Dict]:
    """Build all necessary mapping dictionaries from Postgres."""
    company_map = {}
    company_user_map = {}
    template_name_cache = {}
    
    with pg_conn.cursor() as cur:
        cur.execute("SELECT id, external_id FROM public.companies WHERE external_id IS NOT NULL")
        for row in cur.fetchall():
            company_map[str(row[1])] = str(row[0])
            
        cur.execute("SELECT id, external_id FROM public.company_users WHERE external_id IS NOT NULL")
        for row in cur.fetchall():
            company_user_map[str(row[1])] = str(row[0])
            
        cur.execute("SELECT id, name, company_id FROM public.case_templates")
        for row in cur.fetchall():
            comp = str(row[2])
            name = str(row[1]).lower()
            if comp not in template_name_cache:
                template_name_cache[comp] = {}
            template_name_cache[comp][name] = str(row[0])
            
    return company_map, company_user_map, template_name_cache

# ==========================================
# PHASE 1: TEMPLATES & CONFIGURATIONS
# ==========================================
def migrate_templates_and_configs(mysql_conn, pg_conn, company_map):
    logging.info("=== PHASE 1: Migrating Templates & Configurations (With Deduplication) ===")
    form_to_template_map = {}
    template_to_workflow_map = {}
    company_templates = {} 

    # 1.1 Migrate case_templates (Deduplicated)
    logging.info("Migrating case_templates from be_spoke_form...")
    with mysql_conn.cursor() as m_cur:
        m_cur.execute("""
            SELECT id, name, display_name, reference_id, requires_final_approval, 
                   is_close_case_mandatory, is_archived, deleted_at
            FROM be_spoke_form WHERE reference_type IN ('head_office', 'company')
        """)
        forms = m_cur.fetchall()
        
    template_inserts = []
    closing_reason_template_inserts = []
    seen_templates = {} # Tracks (company_id, name_lower) -> template_id to prevent dups
    
    for form in forms:
        ho_id = str(form['reference_id'])
        company_id = company_map.get(ho_id)
        if not company_id: continue
            
        name = form['display_name'] or form['name'] or f"Template {form['id']}"
        name_lower = name.lower().strip()
        cache_key = (company_id, name_lower)
        
        if cache_key in seen_templates:
            template_id = seen_templates[cache_key]
        else:
            template_id = str(uuid.uuid4())
            seen_templates[cache_key] = template_id
            
            if company_id not in company_templates:
                company_templates[company_id] = []
            company_templates[company_id].append(template_id)
            
            deleted_at = form.get('deleted_at') or (datetime.now(timezone.utc) if form.get('is_archived') else None)
            
            template_inserts.append((
                template_id, name, company_id, False, False, 
                bool(form.get('requires_final_approval')), bool(form.get('is_close_case_mandatory')),
                datetime.now(timezone.utc), datetime.now(timezone.utc), deleted_at
            ))
            
            closing_reason_template_inserts.append((
                str(uuid.uuid4()), template_id, 'Closed', 'Migrated from legacy system',
                datetime.now(timezone.utc), datetime.now(timezone.utc)
            ))
            
        form_to_template_map[form['id']] = template_id
        
    if template_inserts:
        with pg_conn.cursor() as p_cur:
            psycopg2.extras.execute_values(
                p_cur,
                """INSERT INTO public.case_templates (
                    id, name, company_id, can_all_users_access, ask_case_handler_to_create_case_name,
                    requires_final_approval_before_close, requires_closing_case_reason,
                    created_at, updated_at, deleted_at
                ) VALUES %s ON CONFLICT (id) DO NOTHING""",
                template_inserts
            )
            psycopg2.extras.execute_values(
                p_cur,
                """INSERT INTO public.case_template_closing_reason_templates (
                    id, template_id, name, reason, created_at, updated_at
                ) VALUES %s ON CONFLICT (id) DO NOTHING""",
                closing_reason_template_inserts
            )
        pg_conn.commit()
    logging.info(f"Migrated {len(template_inserts)} UNIQUE case_templates.")

    # 1.2 Migrate case_template_statuses (Deduplicated)
    logging.info("Migrating case_template_statuses...")
    with mysql_conn.cursor() as m_cur:
        m_cur.execute("SELECT id, head_office_id, status, form_id FROM case_statuses")
        old_statuses = m_cur.fetchall()
        
    status_inserts = []
    seen_statuses = set() 
    
    for stat in old_statuses:
        ho_id = str(stat['head_office_id'])
        company_id = company_map.get(ho_id)
        if not company_id or not stat['status']: continue
            
        template_ids = []
        if stat['form_id'] and stat['form_id'] in form_to_template_map:
            template_ids = [form_to_template_map[stat['form_id']]]
        elif company_id in company_templates:
            template_ids = company_templates[company_id]
            
        status_key = stat['status'].strip().lower()
        for tid in template_ids:
            if (tid, status_key) in seen_statuses:
                continue
            seen_statuses.add((tid, status_key))
            
            status_inserts.append((
                str(uuid.uuid4()), tid, status_key, stat['status'],
                None, False, 0, datetime.now(timezone.utc), datetime.now(timezone.utc)
            ))
            
    if status_inserts:
        with pg_conn.cursor() as p_cur:
            psycopg2.extras.execute_values(
                p_cur,
                """INSERT INTO public.case_template_statuses (
                    id, template_id, key, name, parent_id, is_system_generated, sort_order,
                    created_at, updated_at
                ) VALUES %s ON CONFLICT (template_id, key) DO NOTHING""",
                status_inserts
            )
        pg_conn.commit()
    logging.info(f"Migrated {len(status_inserts)} UNIQUE case_template_statuses.")

    # 1.3 Migrate Workflows & Stages (Deduplicated)
    logging.info("Migrating case_template_workflows and stages...")
    with mysql_conn.cursor() as m_cur:
        m_cur.execute("SELECT id, be_spoke_form_id, name FROM default_case_stages")
        default_stages = m_cur.fetchall()
        
    stages_by_form = {}
    for stage in default_stages:
        fid = stage['be_spoke_form_id']
        if fid not in stages_by_form: stages_by_form[fid] = []
        stages_by_form[fid].append(stage)
        
    workflow_inserts = []
    stage_inserts = []
    seen_workflows = {} 
    seen_stages = set() 
    
    for fid, stages in stages_by_form.items():
        if fid not in form_to_template_map: continue
        tid = form_to_template_map[fid]
        
        if tid in seen_workflows:
            workflow_id = seen_workflows[tid]
        else:
            workflow_id = str(uuid.uuid4())
            seen_workflows[tid] = workflow_id
            template_to_workflow_map[tid] = workflow_id
            workflow_inserts.append((workflow_id, tid, "Default Workflow", datetime.now(timezone.utc), datetime.now(timezone.utc)))
            
        for stage in stages:
            stage_name_lower = stage['name'].lower().strip()
            stage_key = (workflow_id, stage_name_lower)
            if stage_key in seen_stages:
                continue
            seen_stages.add(stage_key)
            stage_inserts.append((str(uuid.uuid4()), workflow_id, stage['name'], datetime.now(timezone.utc), datetime.now(timezone.utc)))
            
    if workflow_inserts:
        with pg_conn.cursor() as p_cur:
            psycopg2.extras.execute_values(
                p_cur,
                """INSERT INTO public.case_template_workflows (id, template_id, name, created_at, updated_at) 
                   VALUES %s ON CONFLICT (id) DO NOTHING""", workflow_inserts
            )
            psycopg2.extras.execute_values(
                p_cur,
                """INSERT INTO public.case_template_workflow_stages (id, workflow_id, name, created_at, updated_at) 
                   VALUES %s ON CONFLICT (id) DO NOTHING""", stage_inserts
            )
        pg_conn.commit()
    logging.info(f"Migrated {len(workflow_inserts)} UNIQUE template workflows and {len(stage_inserts)} UNIQUE stages.")
    
    return form_to_template_map, template_to_workflow_map, company_templates

# ==========================================
# PHASE 2, 3, 4: CASES, WORKFLOWS, HANDLERS
# ==========================================
def migrate_cases_and_instances(mysql_conn, pg_conn, company_map, company_user_map, 
                                template_name_cache, form_to_template_map, template_to_workflow_map):
    logging.info("=== PHASE 2, 3, 4: Migrating Cases, Workflows & Handlers ===")
    
    record_to_form_map = {}
    with mysql_conn.cursor() as m_cur:
        m_cur.execute("SELECT id, form_id FROM be_spoke_form_records")
        for row in m_cur.fetchall():
            record_to_form_map[row['id']] = row['form_id']
            
    case_mapping = {} # old_case_id -> (new_case_id, new_workflow_id, new_investigator_group_id)
    
    offset = 0
    total_cases = 0
    
    while True:
        logging.info(f"Fetching cases batch offset {offset}...")
        with mysql_conn.cursor() as m_cur:
            m_cur.execute("""
                SELECT id, head_office_id, incident_type, status, description, case_closed, 
                       created_at, updated_at, form_name, requires_final_approval, isArchived, 
                       last_linked_incident_id
                FROM head_office_cases ORDER BY id LIMIT %s OFFSET %s
            """, (BATCH_SIZE, offset))
            cases = m_cur.fetchall()
            
        if not cases: break
            
        case_inserts = []
        status_inserts = []
        closing_inserts = []
        workflow_inserts = []
        case_status_updates = []
        investigator_group_inserts = []
        case_external_id_updates = []
        case_rows = []
        
        for c in cases:
            ho_id = str(c['head_office_id'])
            company_id = company_map.get(ho_id)
            if not company_id: continue
                
            template_id = None
            if c['last_linked_incident_id'] in record_to_form_map:
                fid = record_to_form_map[c['last_linked_incident_id']]
                template_id = form_to_template_map.get(fid)
                
            if not template_id:
                inc_type = str(c['incident_type']).lower()
                if company_id in template_name_cache and inc_type in template_name_cache[company_id]:
                    template_id = template_name_cache[company_id][inc_type]
                    
            if not template_id: continue
                
            title = c['form_name'] or c['description'] or f"Case {c['id']}"
            identifier = f"CASE-{c['id']}"
            case_type = c['incident_type'] or 'general'
            status_key = (c['status'] or 'open').strip().lower()
            
            created_at = c['created_at'] or datetime.now(timezone.utc)
            updated_at = c['updated_at'] or datetime.now(timezone.utc)
            deleted_at = updated_at if c['isArchived'] else None

            case_rows.append({
                'source_id': c['id'],
                'company_id': company_id,
                'template_id': template_id,
                'title': title,
                'identifier': identifier,
                'case_type': case_type,
                'status_key': status_key,
                'created_at': created_at,
                'updated_at': updated_at,
                'deleted_at': deleted_at,
                'requires_final_approval': bool(c['requires_final_approval']),
                'case_closed': bool(c['case_closed']),
                'description': c['description'],
            })

        existing_case_lookup = {}
        if case_rows:
            identifiers = [row['identifier'] for row in case_rows]
            placeholders = ', '.join(['%s'] * len(identifiers))
            with pg_conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT c.identifier, c.id, wf.id AS workflow_id, ig.id AS group_id
                    FROM public.cases c
                    LEFT JOIN public.case_workflows wf ON wf.case_id = c.id
                    LEFT JOIN public.case_investigator_groups ig ON ig.case_id = c.id
                    WHERE c.identifier IN ({placeholders})
                    """,
                    identifiers,
                )
                existing_case_lookup = {
                    str(row[0]): (str(row[1]), str(row[2]) if row[2] else None, str(row[3]) if row[3] else None)
                    for row in cur.fetchall()
                }

        for case_row in case_rows:
            existing_case_state = existing_case_lookup.get(case_row['identifier'])
            if existing_case_state:
                existing_case_id, existing_workflow_id, existing_group_id = existing_case_state
                case_mapping[case_row['source_id']] = (existing_case_id, existing_workflow_id, existing_group_id)
                case_external_id_updates.append((case_row['source_id'], case_row['updated_at'], existing_case_id))
                continue

            new_case_id = str(uuid.uuid4())
            new_status_id = str(uuid.uuid4())
            new_workflow_id = str(uuid.uuid4())
            new_investigator_group_id = str(uuid.uuid4())
            
            case_mapping[case_row['source_id']] = (new_case_id, new_workflow_id, new_investigator_group_id)
            
            case_inserts.append((
                new_case_id, case_row['company_id'], case_row['template_id'], case_row['title'], case_row['identifier'],
                case_row['case_type'], case_row['source_id'], None,
                False, False, case_row['requires_final_approval'], True,
                case_row['created_at'], case_row['updated_at'], case_row['deleted_at']
            ))
            
            status_inserts.append((
                new_status_id, new_case_id, None, case_row['status_key'], case_row['status_key'].replace('_', ' ').title(),
                False, 0, case_row['created_at'], case_row['updated_at']
            ))
            case_status_updates.append((new_status_id, new_case_id))
            
            if case_row['case_closed']:
                closing_inserts.append((
                    str(uuid.uuid4()), new_case_id, 'Closed',
                    case_row['description'] or 'Migrated as closed', case_row['updated_at'], case_row['updated_at']
                ))
                
            template_workflow_id = template_to_workflow_map.get(case_row['template_id'])
            workflow_inserts.append((
                new_workflow_id, new_case_id, template_workflow_id, "Case Workflow", case_row['created_at'], case_row['updated_at']
            ))
            
            investigator_group_inserts.append((
                new_investigator_group_id, new_case_id, "Legacy Handlers", case_row['created_at']
            ))
            
        if case_inserts or case_external_id_updates:
            with pg_conn.cursor() as p_cur:
                if case_external_id_updates:
                    psycopg2.extras.execute_batch(
                        p_cur,
                        "UPDATE public.cases SET external_id = %s, updated_at = %s WHERE id = %s",
                        case_external_id_updates
                    )

                # Step 1: Insert Cases (status_id = NULL to bypass circular FK)
                psycopg2.extras.execute_values(
                    p_cur,
                    """INSERT INTO public.cases (
                        id, company_id, template_id, title, identifier, case_type, external_id, status_id,
                        can_all_users_access, ask_case_handler_to_create_case_name,
                        requires_final_approval_before_close, requires_closing_case_reason,
                        created_at, updated_at, deleted_at
                    ) VALUES %s
                    ON CONFLICT (id) DO UPDATE SET external_id = EXCLUDED.external_id""", case_inserts
                )
                
                # Step 2: Insert Statuses
                psycopg2.extras.execute_values(
                    p_cur,
                    """INSERT INTO public.case_statuses (
                        id, case_id, parent_id, key, name, is_system_generated, sort_order,
                        created_at, updated_at
                    ) VALUES %s ON CONFLICT (case_id, key) DO NOTHING""", status_inserts
                )
                
                # Step 3: Resolve Circular FK
                psycopg2.extras.execute_batch(
                    p_cur,
                    "UPDATE public.cases SET status_id = %s WHERE id = %s AND status_id IS NULL",
                    case_status_updates
                )
                
                if closing_inserts:
                    psycopg2.extras.execute_values(
                        p_cur,
                        """INSERT INTO public.case_closing_reasons (
                            id, case_id, name, reason, created_at, updated_at
                        ) VALUES %s ON CONFLICT (id) DO NOTHING""", closing_inserts
                    )
                    
                psycopg2.extras.execute_values(
                    p_cur,
                    """INSERT INTO public.case_workflows (
                        id, case_id, template_workflow_id, name, created_at, updated_at
                    ) VALUES %s ON CONFLICT (id) DO NOTHING""", workflow_inserts
                )
                
                psycopg2.extras.execute_values(
                    p_cur,
                    """INSERT INTO public.case_investigator_groups (
                        id, case_id, name, created_at
                    ) VALUES %s ON CONFLICT (id) DO NOTHING""", investigator_group_inserts
                )
                
            pg_conn.commit()
            total_cases += len(case_inserts)
            logging.info(f"Inserted {len(case_inserts)} cases. Total: {total_cases}")
            
        offset += BATCH_SIZE
        
    # Migrate case_workflow_stages from case_stages
    logging.info("Migrating case_workflow_stages from case_stages...")
    offset = 0
    while True:
        with mysql_conn.cursor() as m_cur:
            m_cur.execute("SELECT id, case_id, name FROM case_stages ORDER BY id LIMIT %s OFFSET %s", (BATCH_SIZE, offset))
            stages = m_cur.fetchall()
            
        if not stages: break
            
        stage_inserts = []
        for s in stages:
            if s['case_id'] in case_mapping:
                new_case_id, new_workflow_id, _ = case_mapping[s['case_id']]
                stage_inserts.append((
                    str(uuid.uuid4()), new_workflow_id, None, s['name'],
                    datetime.now(timezone.utc), datetime.now(timezone.utc)
                ))
                
        if stage_inserts:
            with pg_conn.cursor() as p_cur:
                psycopg2.extras.execute_values(
                    p_cur,
                    """INSERT INTO public.case_workflow_stages (
                        id, workflow_id, template_stage_id, name, created_at, updated_at
                    ) VALUES %s ON CONFLICT (id) DO NOTHING""", stage_inserts
                )
            pg_conn.commit()
        offset += BATCH_SIZE

    # Migrate case_handler_users to case_investigator_group_users
    logging.info("Migrating case_handler_users to investigator group users...")
    offset = 0
    while True:
        with mysql_conn.cursor() as m_cur:
            m_cur.execute("SELECT head_office_user_id, case_id FROM case_handler_users ORDER BY id LIMIT %s OFFSET %s", (BATCH_SIZE, offset))
            handlers = m_cur.fetchall()
            
        if not handlers: break
            
        user_inserts = []
        for h in handlers:
            if h['case_id'] in case_mapping:
                _, _, group_id = case_mapping[h['case_id']]
                user_id = company_user_map.get(str(h['head_office_user_id']))
                if user_id:
                    user_inserts.append((
                        str(uuid.uuid4()), group_id, user_id, True, None, None
                    ))
                    
        if user_inserts:
            with pg_conn.cursor() as p_cur:
                psycopg2.extras.execute_values(
                    p_cur,
                    """INSERT INTO public.case_investigator_group_users (
                        id, investigator_group_id, user_id, all_sites, priority_min, priority_max
                    ) VALUES %s ON CONFLICT (id) DO NOTHING""", user_inserts
                )
            pg_conn.commit()
        offset += BATCH_SIZE

    logging.info("=== PHASE 2, 3, 4 COMPLETE ===")

def main():
    logging.info("Connecting to MySQL %s:%s/%s", MYSQL_HOST, MYSQL_PORT, MYSQL_DB)
    mysql_conn = pymysql.connect(
        host=MYSQL_HOST, port=MYSQL_PORT, user=MYSQL_USER, password=MYSQL_PASSWORD,
        db=MYSQL_DB, charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor,
    )

    logging.info("Connecting to Postgres %s:%s/%s", PG_HOST, PG_PORT, PG_DB)
    pg_conn = psycopg2.connect(host=PG_HOST, port=PG_PORT, user=PG_USER, password=PG_PASSWORD, dbname=PG_DB)

    try:
        company_map, company_user_map, template_name_cache = build_maps(pg_conn)
        logging.info(f"Loaded {len(company_map)} companies, {len(company_user_map)} users.")
        
        form_to_template_map, template_to_workflow_map, company_templates = migrate_templates_and_configs(mysql_conn, pg_conn, company_map)
        
        # Refresh template cache after Phase 1 to ensure fallback matching works perfectly
        with pg_conn.cursor() as cur:
            cur.execute("SELECT id, name, company_id FROM public.case_templates")
            for row in cur.fetchall():
                comp = str(row[2])
                name = str(row[1]).lower()
                if comp not in template_name_cache: template_name_cache[comp] = {}
                template_name_cache[comp][name] = str(row[0])
        
        migrate_cases_and_instances(
            mysql_conn, pg_conn, company_map, company_user_map, 
            template_name_cache, form_to_template_map, template_to_workflow_map
        )
        
        logging.info("Full comprehensive migration completed successfully!")

    finally:
        mysql_conn.close()
        pg_conn.close()

if __name__ == "__main__":
    main()