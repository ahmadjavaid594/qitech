-- public.dmd_virtual_medicinal_product_packs definition

-- Drop table

-- DROP TABLE public.dmd_virtual_medicinal_product_packs;

CREATE TABLE public.dmd_virtual_medicinal_product_packs (
	id uuid DEFAULT gen_random_uuid() NOT NULL,
	external_id int8 NOT NULL,
	new_id uuid NULL,
	release_version text NOT NULL,
	invalid bool DEFAULT false NOT NULL,
	virtual_medicinal_product_id int8 NOT NULL,
	"name" text NOT NULL,
	quantity numeric(10, 2) NULL,
	qty_uom_code int8 NULL,
	created_at timestamptz DEFAULT now() NOT NULL,
	CONSTRAINT dmd_virtual_medicinal_product_packs_pkey PRIMARY KEY (id),
	CONSTRAINT dmd_virtual_medicinal_product_packs_new_id_dmd_virtual_medicina FOREIGN KEY (new_id) REFERENCES public.dmd_virtual_medicinal_product_packs(id)
);