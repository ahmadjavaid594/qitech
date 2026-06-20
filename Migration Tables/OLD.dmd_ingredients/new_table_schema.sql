-- public.dmd_ingredient_substances definition

-- Drop table

-- DROP TABLE public.dmd_ingredient_substances;

CREATE TABLE public.dmd_ingredient_substances (
	id uuid DEFAULT gen_random_uuid() NOT NULL,
	external_id int8 NOT NULL,
	new_id uuid NULL,
	release_version text NOT NULL,
	invalid bool DEFAULT false NOT NULL,
	"name" text NOT NULL,
	created_at timestamptz DEFAULT now() NOT NULL,
	CONSTRAINT dmd_ingredient_substances_pkey PRIMARY KEY (id),
	CONSTRAINT dmd_ingredient_substances_new_id_dmd_ingredient_substances_id_f FOREIGN KEY (new_id) REFERENCES public.dmd_ingredient_substances(id)
);