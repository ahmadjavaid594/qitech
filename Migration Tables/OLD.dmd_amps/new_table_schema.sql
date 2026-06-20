-- public.dmd_actual_medicinal_products definition

-- Drop table

-- DROP TABLE public.dmd_actual_medicinal_products;

CREATE TABLE public.dmd_actual_medicinal_products (
	id uuid DEFAULT gen_random_uuid() NOT NULL,
	external_id int8 NOT NULL,
	new_id uuid NULL,
	release_version text NOT NULL,
	invalid bool DEFAULT false NOT NULL,
	virtual_medicinal_product_id int8 NOT NULL,
	"name" text NOT NULL,
	supplier_code int8 NULL,
	lic_auth_code int2 NULL,
	created_at timestamptz DEFAULT now() NOT NULL,
	CONSTRAINT dmd_actual_medicinal_products_pkey PRIMARY KEY (id),
	CONSTRAINT dmd_actual_medicinal_products_new_id_dmd_actual_medicinal_produ FOREIGN KEY (new_id) REFERENCES public.dmd_actual_medicinal_products(id)
);