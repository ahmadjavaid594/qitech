-- public.org_units definition

-- Drop table

-- DROP TABLE public.org_units;

CREATE TABLE public.org_units (
	id uuid DEFAULT gen_random_uuid() NOT NULL,
	external_id int8 NULL,
	company_id uuid NOT NULL,
	parent_id uuid NULL,
	"name" text NOT NULL,
	created_at timestamptz DEFAULT now() NOT NULL,
	updated_at timestamptz DEFAULT now() NOT NULL,
	CONSTRAINT org_units_pkey PRIMARY KEY (id),
	CONSTRAINT org_units_company_id_companies_id_fk FOREIGN KEY (company_id) REFERENCES public.companies(id),
	CONSTRAINT org_units_parent_id_org_units_id_fk FOREIGN KEY (parent_id) REFERENCES public.org_units(id) ON DELETE CASCADE
);
CREATE UNIQUE INDEX org_units_external_id_uq ON public.org_units USING btree (external_id) WHERE (external_id IS NOT NULL);
CREATE UNIQUE INDEX org_units_company_name_uq ON public.org_units USING btree (company_id, name) WHERE (parent_id IS NULL);
CREATE UNIQUE INDEX org_units_company_parent_name_uq ON public.org_units USING btree (company_id, parent_id, name) WHERE (parent_id IS NOT NULL);
