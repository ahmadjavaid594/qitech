-- public.case_handlers definition

-- Drop table

-- DROP TABLE public.case_handlers;

CREATE TABLE public.case_handlers (
	id uuid DEFAULT gen_random_uuid() NOT NULL,
	case_id uuid NOT NULL,
	company_user_id uuid NOT NULL,
	assigned_by_company_user_id uuid NULL,
	created_at timestamptz DEFAULT now() NOT NULL,
	CONSTRAINT case_handlers_case_id_company_user_id_unique UNIQUE (case_id, company_user_id),
	CONSTRAINT case_handlers_pkey PRIMARY KEY (id)
);


-- public.case_handlers foreign keys

ALTER TABLE public.case_handlers ADD CONSTRAINT case_handlers_assigned_by_company_user_id_company_users_id_fk FOREIGN KEY (assigned_by_company_user_id) REFERENCES public.company_users(id);
ALTER TABLE public.case_handlers ADD CONSTRAINT case_handlers_case_id_cases_id_fk FOREIGN KEY (case_id) REFERENCES public.cases(id) ON DELETE CASCADE;
ALTER TABLE public.case_handlers ADD CONSTRAINT case_handlers_company_user_id_company_users_id_fk FOREIGN KEY (company_user_id) REFERENCES public.company_users(id) ON DELETE CASCADE;