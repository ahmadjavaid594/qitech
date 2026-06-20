-- public.dmd_virtual_medicinal_product_routes definition

-- Drop table

-- DROP TABLE public.dmd_virtual_medicinal_product_routes;

CREATE TABLE public.dmd_virtual_medicinal_product_routes (
	virtual_medicinal_product_id uuid NOT NULL,
	route_code int8 NOT NULL,
	created_at timestamptz DEFAULT now() NOT NULL,
	CONSTRAINT dmd_virtual_medicinal_product_routes_virtual_medicinal_product_ PRIMARY KEY (virtual_medicinal_product_id, route_code)
);