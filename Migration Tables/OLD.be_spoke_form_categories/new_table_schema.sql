-- public.categories definition

-- Drop table

-- DROP TABLE public.categories;

CREATE TABLE public.categories (
	id uuid DEFAULT gen_random_uuid() NOT NULL,
	"name" text NOT NULL,
	company_id uuid NOT NULL,
	"type" public."category_type" NOT NULL,
	"position" int4 DEFAULT 0 NOT NULL,
	CONSTRAINT categories_pkey PRIMARY KEY (id),
	CONSTRAINT categories_company_id_companies_id_fk FOREIGN KEY (company_id) REFERENCES public.companies(id)
);
CREATE UNIQUE INDEX categories_company_id_type_name_index ON public.categories USING btree (company_id, type, name);