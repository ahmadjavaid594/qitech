-- public.site_types definition

-- Drop table

-- DROP TABLE public.site_types;

CREATE TABLE public.site_types (
	id uuid DEFAULT gen_random_uuid() NOT NULL,
	external_id int8 NULL,
	"name" text NOT NULL,
	parent_id uuid NULL,
	has_regulatory_body bool DEFAULT false NOT NULL,
	created_at timestamptz DEFAULT now() NOT NULL,
	updated_at timestamptz DEFAULT now() NOT NULL,
	CONSTRAINT site_types_name_unique UNIQUE (name),
	CONSTRAINT site_types_pkey PRIMARY KEY (id),
	CONSTRAINT site_types_parent_id_site_types_id_fk FOREIGN KEY (parent_id) REFERENCES public.site_types(id)
);