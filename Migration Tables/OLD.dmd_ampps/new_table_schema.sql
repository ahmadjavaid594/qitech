-- public.dmd_actual_medicinal_product_packs definition

-- Drop table

-- DROP TABLE public.dmd_actual_medicinal_product_packs;

CREATE TABLE public.dmd_actual_medicinal_product_packs (
	id uuid DEFAULT gen_random_uuid() NOT NULL,
	external_id int8 NOT NULL,
	new_id uuid NULL,
	release_version text NOT NULL,
	invalid bool DEFAULT false NOT NULL,
	actual_medicinal_product_id int8 NOT NULL,
	virtual_medicinal_product_pack_id int8 NULL,
	"name" text NOT NULL,
	legal_cat_code int2 NULL,
	disc_code int2 NULL,
	disc_date date NULL,
	created_at timestamptz DEFAULT now() NOT NULL,
	CONSTRAINT dmd_actual_medicinal_product_packs_pkey PRIMARY KEY (id),
	CONSTRAINT dmd_actual_medicinal_product_packs_new_id_dmd_actual_medicinal_ FOREIGN KEY (new_id) REFERENCES public.dmd_actual_medicinal_product_packs(id)
);