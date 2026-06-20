-- public.dmd_lookup_control_drug_categories definition

-- Drop table

-- DROP TABLE public.dmd_lookup_control_drug_categories;

CREATE TABLE public.dmd_lookup_control_drug_categories (
	id int8 NOT NULL,
	description text NOT NULL,
	created_at timestamptz DEFAULT now() NOT NULL,
	updated_at timestamptz DEFAULT now() NOT NULL,
	CONSTRAINT dmd_lookup_control_drug_categories_pkey PRIMARY KEY (id)
);