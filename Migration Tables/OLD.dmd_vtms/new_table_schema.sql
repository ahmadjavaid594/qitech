-- public.dmd_virtual_therapeutic_moieties definition

-- Drop table

-- DROP TABLE public.dmd_virtual_therapeutic_moieties;

CREATE TABLE public.dmd_virtual_therapeutic_moieties (
	id uuid DEFAULT gen_random_uuid() NOT NULL,
	external_id int8 NOT NULL,
	new_id uuid NULL,
	release_version text NOT NULL,
	invalid bool DEFAULT false NOT NULL,
	"name" text NOT NULL,
	created_at timestamptz DEFAULT now() NOT NULL,
	CONSTRAINT dmd_virtual_therapeutic_moieties_pkey PRIMARY KEY (id),
	CONSTRAINT dmd_virtual_therapeutic_moieties_new_id_dmd_virtual_therapeutic FOREIGN KEY (new_id) REFERENCES public.dmd_virtual_therapeutic_moieties(id)
);