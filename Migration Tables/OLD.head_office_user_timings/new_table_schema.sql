-- public.company_user_work_schedules definition

-- Drop table

-- DROP TABLE public.company_user_work_schedules;

CREATE TABLE public.company_user_work_schedules (
	id uuid DEFAULT gen_random_uuid() NOT NULL,
	external_id int8 NULL,
	company_user_id uuid NOT NULL,
	"from" _text NOT NULL,
	"to" _text NOT NULL,
	same_hours bool DEFAULT false NOT NULL,
	created_at timestamptz DEFAULT now() NOT NULL,
	updated_at timestamptz DEFAULT now() NOT NULL,
	CONSTRAINT company_user_work_schedules_company_user_id_unique UNIQUE (company_user_id),
	CONSTRAINT company_user_work_schedules_pkey PRIMARY KEY (id),
	CONSTRAINT company_user_work_schedules_company_user_id_company_users_id_fk FOREIGN KEY (company_user_id) REFERENCES public.company_users(id)
);