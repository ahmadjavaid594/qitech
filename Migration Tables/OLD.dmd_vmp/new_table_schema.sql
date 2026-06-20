-- public.dmd_virtual_medicinal_products definition

-- Drop table

-- DROP TABLE public.dmd_virtual_medicinal_products;

CREATE TABLE public.dmd_virtual_medicinal_products (
	id uuid DEFAULT gen_random_uuid() NOT NULL,
	external_id int8 NOT NULL,
	new_id uuid NULL,
	release_version text NOT NULL,
	invalid bool DEFAULT false NOT NULL,
	virtual_therapeutic_moiety_id int8 NULL,
	"name" text NOT NULL,
	basis_name_code int2 NULL,
	pres_status_code int2 NULL,
	udfs numeric(10, 3) NULL,
	udfs_uom_code int8 NULL,
	created_at timestamptz DEFAULT now() NOT NULL,
	CONSTRAINT dmd_virtual_medicinal_products_pkey PRIMARY KEY (id),
	CONSTRAINT dmd_virtual_medicinal_products_new_id_dmd_virtual_medicinal_pro FOREIGN KEY (new_id) REFERENCES public.dmd_virtual_medicinal_products(id)
);