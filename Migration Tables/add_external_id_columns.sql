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
