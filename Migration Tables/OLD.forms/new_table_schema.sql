-- public.form_template_tags definition

-- Drop table

-- DROP TABLE public.form_template_tags;

CREATE TABLE public.form_template_tags (
	id uuid DEFAULT gen_random_uuid() NOT NULL,
	"name" text NOT NULL,
	"position" int4 DEFAULT 0 NOT NULL,
	created_at timestamptz DEFAULT now() NOT NULL,
	CONSTRAINT form_template_tags_pkey PRIMARY KEY (id)
);
CREATE UNIQUE INDEX form_template_tags_name_index ON public.form_template_tags USING btree (name);


-- public.form_access definition

-- Drop table

-- DROP TABLE public.form_access;

CREATE TABLE public.form_access (
	id uuid DEFAULT gen_random_uuid() NOT NULL,
	form_definition_id uuid NOT NULL,
	relation public."form_access_relation" NOT NULL,
	kind public."form_access_kind" NOT NULL,
	subject_id uuid NULL,
	created_at timestamptz DEFAULT now() NOT NULL,
	CONSTRAINT form_principals_pkey PRIMARY KEY (id)
);
CREATE UNIQUE INDEX form_access_all_uq ON public.form_access USING btree (form_definition_id, relation, kind) WHERE (subject_id IS NULL);
CREATE UNIQUE INDEX form_access_subject_uq ON public.form_access USING btree (form_definition_id, relation, kind, subject_id) WHERE (subject_id IS NOT NULL);


-- public.form_activity definition

-- Drop table

-- DROP TABLE public.form_activity;

CREATE TABLE public.form_activity (
	id uuid DEFAULT gen_random_uuid() NOT NULL,
	form_definition_id uuid NOT NULL,
	company_id uuid NOT NULL,
	user_id uuid NOT NULL,
	"event" public."form_activity_event" NOT NULL,
	entity_type public."form_activity_entity_type" NOT NULL,
	entity_id uuid NULL,
	payload jsonb NOT NULL,
	created_at timestamptz DEFAULT now() NOT NULL,
	CONSTRAINT form_activity_pkey PRIMARY KEY (id)
);
CREATE INDEX form_activity_company_id_created_at_index ON public.form_activity USING btree (company_id, created_at);
CREATE INDEX form_activity_form_definition_id_created_at_index ON public.form_activity USING btree (form_definition_id, created_at);


-- public.form_definition_categories definition

-- Drop table

-- DROP TABLE public.form_definition_categories;

CREATE TABLE public.form_definition_categories (
	id uuid DEFAULT gen_random_uuid() NOT NULL,
	form_definition_id uuid NOT NULL,
	category_id uuid NOT NULL,
	created_at timestamptz DEFAULT now() NOT NULL,
	CONSTRAINT form_definition_categories_pkey PRIMARY KEY (id)
);
CREATE UNIQUE INDEX form_definition_categories_form_definition_id_category_id_index ON public.form_definition_categories USING btree (form_definition_id, category_id);


-- public.form_definition_update_notices definition

-- Drop table

-- DROP TABLE public.form_definition_update_notices;

CREATE TABLE public.form_definition_update_notices (
	id uuid DEFAULT gen_random_uuid() NOT NULL,
	form_definition_id uuid NOT NULL,
	template_version int4 NOT NULL,
	pending_updates jsonb NOT NULL,
	due_date timestamptz NULL,
	acknowledged_at timestamptz NULL,
	reminded_at timestamptz NULL,
	created_at timestamptz DEFAULT now() NOT NULL,
	CONSTRAINT form_definition_update_notices_pkey PRIMARY KEY (id)
);
CREATE UNIQUE INDEX form_definition_update_notices_form_definition_id_template_vers ON public.form_definition_update_notices USING btree (form_definition_id, template_version);


-- public.form_definitions definition

-- Drop table

-- DROP TABLE public.form_definitions;

CREATE TABLE public.form_definitions (
	id uuid DEFAULT gen_random_uuid() NOT NULL,
	company_id uuid NOT NULL,
	"name" text NOT NULL,
	created_at timestamptz DEFAULT now() NOT NULL,
	updated_at timestamptz DEFAULT now() NOT NULL,
	deleted_at timestamptz NULL,
	description text NULL,
	photo text NULL,
	"type" public."form_type" DEFAULT 'internal'::form_type NOT NULL,
	generate_as public."form_generate_as" DEFAULT 'board'::form_generate_as NOT NULL,
	expires_at timestamptz NULL,
	publish_at timestamptz NULL,
	generate_qr bool DEFAULT false NOT NULL,
	capture_responder bool DEFAULT false NOT NULL,
	allow_drafts bool DEFAULT false NOT NULL,
	allow_offsite_draft_completion bool DEFAULT false NOT NULL,
	draft_visibility public."form_draft_visibility" DEFAULT 'creator'::form_draft_visibility NOT NULL,
	edit_after_submit_mode public."form_edit_after_submit_mode" DEFAULT 'disabled'::form_edit_after_submit_mode NOT NULL,
	edit_after_submit_minutes int4 NULL,
	responder_update_mode public."form_responder_action_mode" DEFAULT 'disabled'::form_responder_action_mode NOT NULL,
	responder_update_minutes int4 NULL,
	responder_delete_mode public."form_responder_action_mode" DEFAULT 'disabled'::form_responder_action_mode NOT NULL,
	responder_delete_minutes int4 NULL,
	submission_limit_total int4 NULL,
	submission_limit_per_user int4 NULL,
	submission_limit_per_site int4 NULL,
	rate_limit_max int4 NULL,
	rate_limit_period_minutes int4 NULL,
	allow_print_site_team bool DEFAULT false NOT NULL,
	allow_print_company bool DEFAULT false NOT NULL,
	show_in_quick_report bool DEFAULT false NOT NULL,
	color text DEFAULT '#000000'::text NOT NULL,
	assign_all_org_units bool DEFAULT false NOT NULL,
	timeline_display_config jsonb DEFAULT '{"sitesTimeline": {"columns": [], "enabled": false}, "companyTimeline": {"columns": [], "enabled": false}}'::jsonb NOT NULL,
	purpose text NULL,
	created_by uuid NULL,
	updated_by uuid NULL,
	archived_at timestamptz NULL,
	deleted_reason text NULL,
	case_template_id uuid NULL,
	form_template_id uuid NULL,
	system_template_key text NULL,
	last_acknowledged_template_version int4 NULL,
	pending_system_updates jsonb NULL,
	integration_api_key text NULL,
	integration_key_status public."form_integration_key_status" NULL,
	integration_key_approved_by uuid NULL,
	integration_key_approved_at timestamptz NULL,
	integration_settings jsonb DEFAULT '{}'::jsonb NOT NULL,
	CONSTRAINT forms_pkey PRIMARY KEY (id)
);
CREATE UNIQUE INDEX form_definitions_company_id_name_index ON public.form_definitions USING btree (company_id, name) WHERE (deleted_at IS NULL);
CREATE UNIQUE INDEX form_definitions_company_system_key_uq ON public.form_definitions USING btree (company_id, system_template_key) WHERE ((system_template_key IS NOT NULL) AND (deleted_at IS NULL));


-- public.form_org_units definition

-- Drop table

-- DROP TABLE public.form_org_units;

CREATE TABLE public.form_org_units (
	id uuid DEFAULT gen_random_uuid() NOT NULL,
	form_definition_id uuid NOT NULL,
	org_unit_id uuid NOT NULL,
	created_at timestamptz DEFAULT now() NOT NULL,
	CONSTRAINT form_org_units_pkey PRIMARY KEY (id)
);
CREATE UNIQUE INDEX form_org_units_form_definition_id_org_unit_id_index ON public.form_org_units USING btree (form_definition_id, org_unit_id);


-- public.form_schema_snapshots definition

-- Drop table

-- DROP TABLE public.form_schema_snapshots;

CREATE TABLE public.form_schema_snapshots (
	id uuid DEFAULT gen_random_uuid() NOT NULL,
	"schema" jsonb NOT NULL,
	created_by uuid NULL,
	created_at timestamptz DEFAULT now() NOT NULL,
	form_version_id uuid NOT NULL,
	parent_snapshot_id uuid NULL,
	CONSTRAINT form_schema_versions_pkey PRIMARY KEY (id)
);
CREATE INDEX form_schema_snapshots_form_version_id_created_at_index ON public.form_schema_snapshots USING btree (form_version_id, created_at);


-- public.form_schemas definition

-- Drop table

-- DROP TABLE public.form_schemas;

CREATE TABLE public.form_schemas (
	id uuid DEFAULT gen_random_uuid() NOT NULL,
	form_definition_id uuid NOT NULL,
	current_version_id uuid NULL,
	draft_version_id uuid NULL,
	created_at timestamptz DEFAULT now() NOT NULL,
	updated_at timestamptz DEFAULT now() NOT NULL,
	CONSTRAINT form_schemas_form_definition_id_unique UNIQUE (form_definition_id),
	CONSTRAINT form_schemas_pkey PRIMARY KEY (id)
);


-- public.form_submission_answers definition

-- Drop table

-- DROP TABLE public.form_submission_answers;

CREATE TABLE public.form_submission_answers (
	id uuid DEFAULT gen_random_uuid() NOT NULL,
	form_submission_id uuid NOT NULL,
	block_id text NOT NULL,
	block_type text NOT NULL,
	"label" text NOT NULL,
	raw_value jsonb NOT NULL,
	display_value text NOT NULL,
	"summary_context" public._summary_context NULL,
	sort_order int4 DEFAULT 0 NOT NULL,
	created_at timestamptz DEFAULT now() NOT NULL,
	updated_at timestamptz DEFAULT now() NOT NULL,
	CONSTRAINT form_submission_answers_pkey PRIMARY KEY (id)
);


-- public.form_submission_revisions definition

-- Drop table

-- DROP TABLE public.form_submission_revisions;

CREATE TABLE public.form_submission_revisions (
	id uuid DEFAULT gen_random_uuid() NOT NULL,
	form_submission_id uuid NOT NULL,
	form_version_schema_snapshot_id uuid NOT NULL,
	"data" jsonb NOT NULL,
	revision int4 NOT NULL,
	edited_by_id uuid NULL,
	edited_at timestamptz DEFAULT now() NOT NULL,
	form_version_id uuid NOT NULL,
	CONSTRAINT form_submission_revisions_pkey PRIMARY KEY (id)
);
CREATE UNIQUE INDEX form_submission_revisions_form_submission_id_revision_index ON public.form_submission_revisions USING btree (form_submission_id, revision);


-- public.form_submissions definition

-- Drop table

-- DROP TABLE public.form_submissions;

CREATE TABLE public.form_submissions (
	id uuid DEFAULT gen_random_uuid() NOT NULL,
	external_id int8 NULL,
	company_id uuid NOT NULL,
	form_definition_id uuid NOT NULL,
	form_version_schema_snapshot_id uuid NOT NULL,
	"status" public."form_submission_status" DEFAULT 'submitted'::form_submission_status NOT NULL,
	submitted_by_id uuid NULL,
	responder_name text NULL,
	responder_email text NULL,
	responder_phone text NULL,
	site_id uuid NULL,
	case_id uuid NULL,
	submitted_at timestamptz NULL,
	created_at timestamptz DEFAULT now() NOT NULL,
	updated_at timestamptz DEFAULT now() NOT NULL,
	deleted_at timestamptz NULL,
	form_version_id uuid NOT NULL,
	CONSTRAINT form_submissions_pkey PRIMARY KEY (id)
);
CREATE INDEX form_submissions_case_id_index ON public.form_submissions USING btree (case_id);
CREATE INDEX form_submissions_company_id_submitted_at_index ON public.form_submissions USING btree (company_id, submitted_at);
CREATE UNIQUE INDEX form_submissions_external_id_unique ON public.form_submissions USING btree (external_id) WHERE (external_id IS NOT NULL);
CREATE INDEX form_submissions_form_definition_id_status_index ON public.form_submissions USING btree (form_definition_id, status);
CREATE INDEX form_submissions_submitted_by_id_index ON public.form_submissions USING btree (submitted_by_id);


-- public.form_template_activity definition

-- Drop table

-- DROP TABLE public.form_template_activity;

CREATE TABLE public.form_template_activity (
	id uuid DEFAULT gen_random_uuid() NOT NULL,
	form_template_id uuid NOT NULL,
	user_id uuid NOT NULL,
	"event" public."form_template_activity_event" NOT NULL,
	entity_type public."form_template_activity_entity_type" NOT NULL,
	entity_id uuid NULL,
	payload jsonb NOT NULL,
	created_at timestamptz DEFAULT now() NOT NULL,
	CONSTRAINT form_template_activity_pkey PRIMARY KEY (id)
);
CREATE INDEX form_template_activity_form_template_id_created_at_index ON public.form_template_activity USING btree (form_template_id, created_at);


-- public.form_template_industries definition

-- Drop table

-- DROP TABLE public.form_template_industries;

CREATE TABLE public.form_template_industries (
	id uuid DEFAULT gen_random_uuid() NOT NULL,
	form_template_id uuid NOT NULL,
	industry_id uuid NOT NULL,
	created_at timestamptz DEFAULT now() NOT NULL,
	CONSTRAINT form_template_industries_pkey PRIMARY KEY (id)
);
CREATE UNIQUE INDEX form_template_industries_form_template_id_industry_id_index ON public.form_template_industries USING btree (form_template_id, industry_id);


-- public.form_template_owners definition

-- Drop table

-- DROP TABLE public.form_template_owners;

CREATE TABLE public.form_template_owners (
	id uuid DEFAULT gen_random_uuid() NOT NULL,
	form_template_id uuid NOT NULL,
	user_id uuid NOT NULL,
	created_at timestamptz DEFAULT now() NOT NULL,
	CONSTRAINT form_template_owners_pkey PRIMARY KEY (id)
);
CREATE UNIQUE INDEX form_template_owners_form_template_id_user_id_index ON public.form_template_owners USING btree (form_template_id, user_id);


-- public.form_template_tag_assignments definition

-- Drop table

-- DROP TABLE public.form_template_tag_assignments;

CREATE TABLE public.form_template_tag_assignments (
	id uuid DEFAULT gen_random_uuid() NOT NULL,
	form_template_id uuid NOT NULL,
	tag_id uuid NOT NULL,
	created_at timestamptz DEFAULT now() NOT NULL,
	CONSTRAINT form_template_tag_assignments_pkey PRIMARY KEY (id)
);
CREATE UNIQUE INDEX form_template_tag_assignments_form_template_id_tag_id_index ON public.form_template_tag_assignments USING btree (form_template_id, tag_id);


-- public.form_templates definition

-- Drop table

-- DROP TABLE public.form_templates;

CREATE TABLE public.form_templates (
	id uuid DEFAULT gen_random_uuid() NOT NULL,
	"name" text NOT NULL,
	description text NULL,
	photo text NULL,
	"status" public."form_template_status" DEFAULT 'draft'::form_template_status NOT NULL,
	"schema" jsonb DEFAULT '{}'::jsonb NOT NULL,
	allow_multiple_downloads bool DEFAULT true NOT NULL,
	show_in_templates bool DEFAULT false NOT NULL,
	created_by uuid NULL,
	updated_by uuid NULL,
	created_at timestamptz DEFAULT now() NOT NULL,
	updated_at timestamptz DEFAULT now() NOT NULL,
	archived_at timestamptz NULL,
	deleted_at timestamptz NULL,
	deleted_reason text NULL,
	system_template_key text NULL,
	template_version int4 DEFAULT 1 NOT NULL,
	block_policies jsonb DEFAULT '[]'::jsonb NOT NULL,
	integrations_config jsonb DEFAULT '{"requireApiKey": false, "submissionMode": "realtime"}'::jsonb NOT NULL,
	CONSTRAINT form_templates_pkey PRIMARY KEY (id)
);
CREATE UNIQUE INDEX form_templates_name_index ON public.form_templates USING btree (name) WHERE (deleted_at IS NULL);
CREATE UNIQUE INDEX form_templates_system_key_uq ON public.form_templates USING btree (system_template_key) WHERE ((system_template_key IS NOT NULL) AND (deleted_at IS NULL));


-- public.form_versions definition

-- Drop table

-- DROP TABLE public.form_versions;

CREATE TABLE public.form_versions (
	id uuid DEFAULT gen_random_uuid() NOT NULL,
	form_schema_id uuid NOT NULL,
	"version" int4 NOT NULL,
	description text NULL,
	"status" public."form_schema_version_status" DEFAULT 'draft'::form_schema_version_status NOT NULL,
	published_at timestamptz NULL,
	review_at timestamptz NULL,
	current_schema_snapshot_id uuid NULL,
	created_by uuid NULL,
	created_at timestamptz DEFAULT now() NOT NULL,
	CONSTRAINT form_versions_pkey PRIMARY KEY (id)
);
CREATE UNIQUE INDEX form_versions_form_schema_id_version_index ON public.form_versions USING btree (form_schema_id, version);


-- public.form_access foreign keys

ALTER TABLE public.form_access ADD CONSTRAINT form_access_form_definition_id_form_definitions_id_fk FOREIGN KEY (form_definition_id) REFERENCES public.form_definitions(id) ON DELETE CASCADE;


-- public.form_activity foreign keys

ALTER TABLE public.form_activity ADD CONSTRAINT form_activity_company_id_companies_id_fk FOREIGN KEY (company_id) REFERENCES public.companies(id);
ALTER TABLE public.form_activity ADD CONSTRAINT form_activity_form_definition_id_form_definitions_id_fk FOREIGN KEY (form_definition_id) REFERENCES public.form_definitions(id) ON DELETE CASCADE;
ALTER TABLE public.form_activity ADD CONSTRAINT form_activity_user_id_users_id_fk FOREIGN KEY (user_id) REFERENCES public.users(id);


-- public.form_definition_categories foreign keys

ALTER TABLE public.form_definition_categories ADD CONSTRAINT form_definition_categories_category_id_categories_id_fk FOREIGN KEY (category_id) REFERENCES public.categories(id) ON DELETE CASCADE;
ALTER TABLE public.form_definition_categories ADD CONSTRAINT form_definition_categories_form_definition_id_form_definitions_ FOREIGN KEY (form_definition_id) REFERENCES public.form_definitions(id) ON DELETE CASCADE;


-- public.form_definition_update_notices foreign keys

ALTER TABLE public.form_definition_update_notices ADD CONSTRAINT form_definition_update_notices_form_definition_id_form_definiti FOREIGN KEY (form_definition_id) REFERENCES public.form_definitions(id) ON DELETE CASCADE;


-- public.form_definitions foreign keys

ALTER TABLE public.form_definitions ADD CONSTRAINT form_definitions_case_template_id_case_templates_id_fk FOREIGN KEY (case_template_id) REFERENCES public.case_templates(id);
ALTER TABLE public.form_definitions ADD CONSTRAINT form_definitions_company_id_companies_id_fk FOREIGN KEY (company_id) REFERENCES public.companies(id);
ALTER TABLE public.form_definitions ADD CONSTRAINT form_definitions_created_by_users_id_fk FOREIGN KEY (created_by) REFERENCES public.users(id);
ALTER TABLE public.form_definitions ADD CONSTRAINT form_definitions_form_template_id_form_templates_id_fk FOREIGN KEY (form_template_id) REFERENCES public.form_templates(id) ON DELETE SET NULL;
ALTER TABLE public.form_definitions ADD CONSTRAINT form_definitions_integration_key_approved_by_users_id_fk FOREIGN KEY (integration_key_approved_by) REFERENCES public.users(id);
ALTER TABLE public.form_definitions ADD CONSTRAINT form_definitions_updated_by_users_id_fk FOREIGN KEY (updated_by) REFERENCES public.users(id);


-- public.form_org_units foreign keys

ALTER TABLE public.form_org_units ADD CONSTRAINT form_org_units_form_definition_id_form_definitions_id_fk FOREIGN KEY (form_definition_id) REFERENCES public.form_definitions(id) ON DELETE CASCADE;
ALTER TABLE public.form_org_units ADD CONSTRAINT form_org_units_org_unit_id_org_units_id_fk FOREIGN KEY (org_unit_id) REFERENCES public.org_units(id) ON DELETE CASCADE;


-- public.form_schema_snapshots foreign keys

ALTER TABLE public.form_schema_snapshots ADD CONSTRAINT form_schema_snapshots_created_by_users_id_fk FOREIGN KEY (created_by) REFERENCES public.users(id);
ALTER TABLE public.form_schema_snapshots ADD CONSTRAINT form_schema_snapshots_form_version_id_form_versions_id_fk FOREIGN KEY (form_version_id) REFERENCES public.form_versions(id) ON DELETE CASCADE;
ALTER TABLE public.form_schema_snapshots ADD CONSTRAINT form_schema_snapshots_parent_snapshot_id_form_schema_snapshots_ FOREIGN KEY (parent_snapshot_id) REFERENCES public.form_schema_snapshots(id);


-- public.form_schemas foreign keys

ALTER TABLE public.form_schemas ADD CONSTRAINT form_schemas_form_definition_id_form_definitions_id_fk FOREIGN KEY (form_definition_id) REFERENCES public.form_definitions(id) ON DELETE CASCADE;


-- public.form_submission_answers foreign keys

ALTER TABLE public.form_submission_answers ADD CONSTRAINT form_submission_answers_form_submission_id_form_submissions_id_ FOREIGN KEY (form_submission_id) REFERENCES public.form_submissions(id) ON DELETE CASCADE;


-- public.form_submission_revisions foreign keys

ALTER TABLE public.form_submission_revisions ADD CONSTRAINT form_submission_revisions_edited_by_id_users_id_fk FOREIGN KEY (edited_by_id) REFERENCES public.users(id);
ALTER TABLE public.form_submission_revisions ADD CONSTRAINT form_submission_revisions_form_submission_id_form_submissions_i FOREIGN KEY (form_submission_id) REFERENCES public.form_submissions(id) ON DELETE CASCADE;
ALTER TABLE public.form_submission_revisions ADD CONSTRAINT form_submission_revisions_form_version_id_form_versions_id_fk FOREIGN KEY (form_version_id) REFERENCES public.form_versions(id);
ALTER TABLE public.form_submission_revisions ADD CONSTRAINT form_submission_revisions_form_version_schema_snapshot_id_form_ FOREIGN KEY (form_version_schema_snapshot_id) REFERENCES public.form_schema_snapshots(id);


-- public.form_submissions foreign keys

ALTER TABLE public.form_submissions ADD CONSTRAINT form_submissions_case_id_cases_id_fk FOREIGN KEY (case_id) REFERENCES public.cases(id);
ALTER TABLE public.form_submissions ADD CONSTRAINT form_submissions_company_id_companies_id_fk FOREIGN KEY (company_id) REFERENCES public.companies(id);
ALTER TABLE public.form_submissions ADD CONSTRAINT form_submissions_form_definition_id_form_definitions_id_fk FOREIGN KEY (form_definition_id) REFERENCES public.form_definitions(id);
ALTER TABLE public.form_submissions ADD CONSTRAINT form_submissions_form_version_id_form_versions_id_fk FOREIGN KEY (form_version_id) REFERENCES public.form_versions(id);
ALTER TABLE public.form_submissions ADD CONSTRAINT form_submissions_form_version_schema_snapshot_id_form_schema_sn FOREIGN KEY (form_version_schema_snapshot_id) REFERENCES public.form_schema_snapshots(id);
ALTER TABLE public.form_submissions ADD CONSTRAINT form_submissions_site_id_sites_id_fk FOREIGN KEY (site_id) REFERENCES public.sites(id);
ALTER TABLE public.form_submissions ADD CONSTRAINT form_submissions_submitted_by_id_users_id_fk FOREIGN KEY (submitted_by_id) REFERENCES public.users(id);


-- public.form_template_activity foreign keys

ALTER TABLE public.form_template_activity ADD CONSTRAINT form_template_activity_form_template_id_form_templates_id_fk FOREIGN KEY (form_template_id) REFERENCES public.form_templates(id) ON DELETE CASCADE;
ALTER TABLE public.form_template_activity ADD CONSTRAINT form_template_activity_user_id_users_id_fk FOREIGN KEY (user_id) REFERENCES public.users(id);


-- public.form_template_industries foreign keys

ALTER TABLE public.form_template_industries ADD CONSTRAINT form_template_industries_form_template_id_form_templates_id_fk FOREIGN KEY (form_template_id) REFERENCES public.form_templates(id) ON DELETE CASCADE;
ALTER TABLE public.form_template_industries ADD CONSTRAINT form_template_industries_industry_id_industries_id_fk FOREIGN KEY (industry_id) REFERENCES public.industries(id) ON DELETE CASCADE;


-- public.form_template_owners foreign keys

ALTER TABLE public.form_template_owners ADD CONSTRAINT form_template_owners_form_template_id_form_templates_id_fk FOREIGN KEY (form_template_id) REFERENCES public.form_templates(id) ON DELETE CASCADE;
ALTER TABLE public.form_template_owners ADD CONSTRAINT form_template_owners_user_id_users_id_fk FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


-- public.form_template_tag_assignments foreign keys

ALTER TABLE public.form_template_tag_assignments ADD CONSTRAINT form_template_tag_assignments_form_template_id_form_templates_i FOREIGN KEY (form_template_id) REFERENCES public.form_templates(id) ON DELETE CASCADE;
ALTER TABLE public.form_template_tag_assignments ADD CONSTRAINT form_template_tag_assignments_tag_id_form_template_tags_id_fk FOREIGN KEY (tag_id) REFERENCES public.form_template_tags(id) ON DELETE CASCADE;


-- public.form_templates foreign keys

ALTER TABLE public.form_templates ADD CONSTRAINT form_templates_created_by_users_id_fk FOREIGN KEY (created_by) REFERENCES public.users(id);
ALTER TABLE public.form_templates ADD CONSTRAINT form_templates_updated_by_users_id_fk FOREIGN KEY (updated_by) REFERENCES public.users(id);


-- public.form_versions foreign keys

ALTER TABLE public.form_versions ADD CONSTRAINT form_versions_created_by_users_id_fk FOREIGN KEY (created_by) REFERENCES public.users(id);
ALTER TABLE public.form_versions ADD CONSTRAINT form_versions_form_schema_id_form_schemas_id_fk FOREIGN KEY (form_schema_id) REFERENCES public.form_schemas(id) ON DELETE CASCADE;
