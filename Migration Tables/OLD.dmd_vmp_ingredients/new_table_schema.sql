-- public.dmd_virtual_medicinal_product_ingredients definition

-- Drop table

-- DROP TABLE public.dmd_virtual_medicinal_product_ingredients;

CREATE TABLE public.dmd_virtual_medicinal_product_ingredients (
	virtual_medicinal_product_id uuid NOT NULL,
	ingredient_substance_id int8 NOT NULL,
	basis_strength_code int8 NULL,
	strength_num_val numeric NULL,
	strength_num_uom int8 NULL,
	strength_denom_val numeric NULL,
	strength_denom_uom int8 NULL,
	created_at timestamptz DEFAULT now() NOT NULL,
	CONSTRAINT dmd_virtual_medicinal_product_ingredients_virtual_medicinal_pro PRIMARY KEY (virtual_medicinal_product_id, ingredient_substance_id)
);