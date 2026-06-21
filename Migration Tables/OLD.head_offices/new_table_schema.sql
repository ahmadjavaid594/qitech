-- public.companies definition

-- Drop table

-- DROP TABLE public.companies;

CREATE TABLE public.companies (
	id uuid DEFAULT gen_random_uuid() NOT NULL,
	external_id int8 NULL,
	"name" text NOT NULL,
	address text NULL,
	email text NOT NULL,
	phone_number text NOT NULL,
	website text NULL,
	estimated_site_count int4 NULL,
	estimated_staff_count_id uuid NULL,
	subdomain text NULL,
	"status" public."company_status" DEFAULT 'new_request'::company_status NOT NULL,
	status_comment text NULL,
	current_theme_id uuid NULL,
	created_at timestamptz DEFAULT now() NOT NULL,
	updated_at timestamptz DEFAULT now() NOT NULL,
	deleted_at timestamptz NULL,
	timezone text DEFAULT 'Europe/London'::text NOT NULL,
	CONSTRAINT companies_email_unique UNIQUE (email),
	CONSTRAINT companies_pkey PRIMARY KEY (id),
	CONSTRAINT companies_subdomain_unique UNIQUE (subdomain)
);


-- public.companies foreign keys

ALTER TABLE public.companies ADD CONSTRAINT companies_current_theme_id_themes_id_fk FOREIGN KEY (current_theme_id) REFERENCES public.themes(id);
ALTER TABLE public.companies ADD CONSTRAINT companies_estimated_staff_count_id_staff_sizes_id_fk FOREIGN KEY (estimated_staff_count_id) REFERENCES public.staff_sizes(id);