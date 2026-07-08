-- Add external_id columns for legacy ID tracking on UUID-generated tables.

ALTER TABLE public.companies
    ADD COLUMN IF NOT EXISTS external_id int8 NULL;

ALTER TABLE public.users
    ADD COLUMN IF NOT EXISTS external_id int8 NULL;

ALTER TABLE public.company_users
    ADD COLUMN IF NOT EXISTS external_id int8 NULL;

ALTER TABLE public.user_types
    ADD COLUMN IF NOT EXISTS external_id int8 NULL;

ALTER TABLE public.company_user_work_schedules
    ADD COLUMN IF NOT EXISTS external_id int8 NULL;

ALTER TABLE public.site_types
    ADD COLUMN IF NOT EXISTS external_id int8 NULL;

ALTER TABLE public.regulatory_bodies
    ADD COLUMN IF NOT EXISTS external_id int8 NULL;

ALTER TABLE public.sites
    ADD COLUMN IF NOT EXISTS external_id int8 NULL;

ALTER TABLE public.cases
    ADD COLUMN IF NOT EXISTS external_id int8 NULL;

ALTER TABLE public.roles
    ADD COLUMN IF NOT EXISTS external_id int8 NULL;

ALTER TABLE public.tags
    ADD COLUMN IF NOT EXISTS external_id int8 NULL;

ALTER TABLE public.form_definitions
    ADD COLUMN IF NOT EXISTS external_id int8 NULL;

ALTER TABLE public.form_submissions
    ADD COLUMN IF NOT EXISTS external_id int8 NULL;

CREATE UNIQUE INDEX IF NOT EXISTS form_submissions_external_id_unique
    ON public.form_submissions (external_id)
    WHERE external_id IS NOT NULL;
