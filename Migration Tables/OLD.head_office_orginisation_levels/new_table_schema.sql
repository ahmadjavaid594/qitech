-- public.org_levels definition

-- Drop table

-- DROP TABLE public.org_levels;

CREATE TABLE public.org_levels (
	id uuid DEFAULT gen_random_uuid() NOT NULL,
	"name" text NOT NULL,
	"level" int4 NOT NULL,
	company_id uuid NOT NULL,
	text_color text NULL,
	background_color text NULL,
	created_at timestamptz DEFAULT now() NOT NULL,
	updated_at timestamptz DEFAULT now() NOT NULL,
	CONSTRAINT org_levels_level_company_id_unique UNIQUE (level, company_id),
	CONSTRAINT org_levels_name_company_id_unique UNIQUE (name, company_id),
	CONSTRAINT org_levels_pkey PRIMARY KEY (id),
	CONSTRAINT org_levels_company_id_companies_id_fk FOREIGN KEY (company_id) REFERENCES public.companies(id)
);