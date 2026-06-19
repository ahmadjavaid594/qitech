-- public.dmd_lookup_routes definition

-- Drop table

-- DROP TABLE public.dmd_lookup_routes;

CREATE TABLE public.dmd_lookup_routes (
	id int8 NOT NULL,
	description text NOT NULL,
	created_at timestamptz DEFAULT now() NOT NULL,
	updated_at timestamptz DEFAULT now() NOT NULL,
	CONSTRAINT dmd_lookup_routes_pkey PRIMARY KEY (id)
);