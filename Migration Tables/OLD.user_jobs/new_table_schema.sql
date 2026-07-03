-- public.user_types definition

-- Drop table

-- DROP TABLE public.user_types;

CREATE TABLE public.user_types (
	id uuid DEFAULT gen_random_uuid() NOT NULL,
	external_id int8 NULL,
	company_id uuid NOT NULL,
	"name" text NOT NULL,
	description text NULL,
	"isSystemGenerated" bool DEFAULT false NOT NULL,
	enabled bool DEFAULT false NOT NULL,
	allow_multiple_sub_types bool DEFAULT false NOT NULL,
	sub_type_selection_required bool DEFAULT false NOT NULL,
	has_regulatory_body bool DEFAULT false NULL,
	assignment_mode public."user_type_assignment_mode" DEFAULT 'open'::user_type_assignment_mode NOT NULL,
	created_at timestamptz DEFAULT now() NOT NULL,
	updated_at timestamptz DEFAULT now() NOT NULL,
	CONSTRAINT user_types_pkey PRIMARY KEY (id)
);
CREATE UNIQUE INDEX user_types_company_id_name_index ON public.user_types USING btree (company_id, name);


-- public.user_types foreign keys

ALTER TABLE public.user_types ADD CONSTRAINT user_types_company_id_companies_id_fk FOREIGN KEY (company_id) REFERENCES public.companies(id);