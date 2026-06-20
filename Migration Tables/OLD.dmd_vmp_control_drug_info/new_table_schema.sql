-- public.dmd_controlled_drugs definition

-- Drop table

-- DROP TABLE public.dmd_controlled_drugs;

CREATE TABLE public.dmd_controlled_drugs (
	id uuid DEFAULT gen_random_uuid() NOT NULL,
	external_id int8 NOT NULL,
	new_id uuid NULL,
	release_version text NOT NULL,
	category_code int2 NOT NULL,
	category_date date NULL,
	category_prev_code int2 NULL,
	created_at timestamptz DEFAULT now() NOT NULL,
	CONSTRAINT dmd_controlled_drugs_pkey PRIMARY KEY (id),
	CONSTRAINT dmd_controlled_drugs_new_id_dmd_controlled_drugs_id_fk FOREIGN KEY (new_id) REFERENCES public.dmd_controlled_drugs(id)
);