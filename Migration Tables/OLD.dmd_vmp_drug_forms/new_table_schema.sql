-- public.dmd_virtual_medicinal_product_forms definition

-- Drop table

-- DROP TABLE public.dmd_virtual_medicinal_product_forms;

CREATE TABLE public.dmd_virtual_medicinal_product_forms (
	virtual_medicinal_product_id uuid NOT NULL,
	form_code int8 NOT NULL,
	created_at timestamptz DEFAULT now() NOT NULL,
	CONSTRAINT dmd_virtual_medicinal_product_forms_virtual_medicinal_product_i PRIMARY KEY (virtual_medicinal_product_id, form_code)
);