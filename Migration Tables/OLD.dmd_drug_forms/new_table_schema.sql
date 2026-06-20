-- public.dmd_lookup_forms definition

-- Drop table

-- DROP TABLE public.dmd_lookup_forms;

CREATE TABLE public.dmd_lookup_forms (
	id int8 NOT NULL,
	description text NOT NULL,
	created_at timestamptz DEFAULT now() NOT NULL,
	updated_at timestamptz DEFAULT now() NOT NULL,
	CONSTRAINT dmd_lookup_forms_pkey PRIMARY KEY (id)
);