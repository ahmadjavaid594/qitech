-- public.dmd_lookup_suppliers definition

-- Drop table

-- DROP TABLE public.dmd_lookup_suppliers;

CREATE TABLE public.dmd_lookup_suppliers (
	id text NOT NULL,
	description text NOT NULL,
	created_at timestamptz DEFAULT now() NOT NULL,
	updated_at timestamptz DEFAULT now() NOT NULL,
	CONSTRAINT dmd_lookup_suppliers_pkey PRIMARY KEY (id)
);