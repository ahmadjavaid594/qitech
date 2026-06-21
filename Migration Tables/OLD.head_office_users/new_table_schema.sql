-- public.company_users definition

-- Drop table

-- DROP TABLE public.company_users;

CREATE TABLE public.company_users (
	id uuid DEFAULT gen_random_uuid() NOT NULL,
	external_id int8 NULL,
	user_id uuid NOT NULL,
	company_id uuid NOT NULL,
	company_role_id uuid NOT NULL,
	"position" text NOT NULL,
	"location" text NULL,
	about text NULL,
	photo text NULL,
	invited_by_company_id uuid NULL,
	invited_by_user_id uuid NULL,
	"status" public."status" DEFAULT 'active'::status NOT NULL,
	status_comment text NULL,
	display_message text NULL,
	work_environment_id uuid NULL,
	"work_status" public."work_status" DEFAULT 'active'::work_status NOT NULL,
	timezone text NULL,
	pin_hash text NULL,
	created_at timestamptz DEFAULT now() NOT NULL,
	updated_at timestamptz DEFAULT now() NOT NULL,
	start_date date NULL,
	end_date date NULL,
	is_role_active bool DEFAULT true NOT NULL,
	CONSTRAINT company_users_pkey PRIMARY KEY (id),
	CONSTRAINT company_users_user_id_company_id_unique UNIQUE (user_id, company_id)
);


-- public.company_users foreign keys

ALTER TABLE public.company_users ADD CONSTRAINT company_users_company_id_companies_id_fk FOREIGN KEY (company_id) REFERENCES public.companies(id);
ALTER TABLE public.company_users ADD CONSTRAINT company_users_company_role_id_company_roles_id_fk FOREIGN KEY (company_role_id) REFERENCES public.company_roles(id);
ALTER TABLE public.company_users ADD CONSTRAINT company_users_invited_by_company_id_companies_id_fk FOREIGN KEY (invited_by_company_id) REFERENCES public.companies(id);
ALTER TABLE public.company_users ADD CONSTRAINT company_users_invited_by_user_id_users_id_fk FOREIGN KEY (invited_by_user_id) REFERENCES public.users(id);
ALTER TABLE public.company_users ADD CONSTRAINT company_users_user_id_users_id_fk FOREIGN KEY (user_id) REFERENCES public.users(id);
ALTER TABLE public.company_users ADD CONSTRAINT company_users_work_environment_id_work_environments_id_fk FOREIGN KEY (work_environment_id) REFERENCES public.work_environments(id);