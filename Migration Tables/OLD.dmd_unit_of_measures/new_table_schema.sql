-- public.dmd_lookup_units_of_measure definition

-- Drop table

-- DROP TABLE public.dmd_lookup_units_of_measure;

CREATE TABLE public.dmd_lookup_units_of_measure (
	id int8 NOT NULL,
	description text NOT NULL,
	created_at timestamptz DEFAULT now() NOT NULL,
	updated_at timestamptz DEFAULT now() NOT NULL,
	CONSTRAINT dmd_lookup_units_of_measure_pkey PRIMARY KEY (id)
);