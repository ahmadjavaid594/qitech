-- public.sites definition

-- Drop table

-- DROP TABLE public.sites;

CREATE TABLE public.sites (
	id uuid DEFAULT gen_random_uuid() NOT NULL,
	external_id int8 NULL,
	company_id uuid NOT NULL,
	type_id uuid NULL,
	regulatory_body_id uuid NULL,
	postal_code text NULL,
	registered_name text NOT NULL,
	trading_name text NOT NULL,
	organization_code text NULL,
	registration_number text NULL,
	username text NULL,
	address_line_1 text NULL,
	address_line_2 text NULL,
	country_id text NULL,
	city text NULL,
	state text NULL,
	phone_number text NULL,
	email text NULL,
	email_verified_at timestamptz NULL,
	password_updated_at timestamptz NULL,
	password_hash text NULL,
	password_reset_attempts int4 DEFAULT 0 NOT NULL,
	password_reset_window_start timestamptz NULL,
	"status" public."status" DEFAULT 'inactive'::status NOT NULL,
	"register_policy" public."register_policy" NULL,
	allow_unlicensed_registers bool DEFAULT false NOT NULL,
	current_theme_id uuid NULL,
	created_at timestamptz DEFAULT now() NOT NULL,
	updated_at timestamptz DEFAULT now() NOT NULL,
	deleted_at timestamptz NULL,
	is_system_generated bool DEFAULT false NOT NULL,
	nickname text NULL,
	CONSTRAINT sites_email_unique UNIQUE (email),
	CONSTRAINT sites_pkey PRIMARY KEY (id),
	CONSTRAINT sites_required_fields_chk CHECK (((is_system_generated = true) OR ((type_id IS NOT NULL) AND (postal_code IS NOT NULL) AND (organization_code IS NOT NULL) AND (registration_number IS NOT NULL) AND (username IS NOT NULL) AND (address_line_1 IS NOT NULL) AND (address_line_2 IS NOT NULL) AND (country_id IS NOT NULL) AND (email IS NOT NULL))))
);
CREATE UNIQUE INDEX sites_company_system_generated_uq ON public.sites USING btree (company_id) WHERE (is_system_generated = true);


-- public.sites foreign keys

ALTER TABLE public.sites ADD CONSTRAINT sites_company_id_companies_id_fk FOREIGN KEY (company_id) REFERENCES public.companies(id);
ALTER TABLE public.sites ADD CONSTRAINT sites_current_theme_id_themes_id_fk FOREIGN KEY (current_theme_id) REFERENCES public.themes(id);
ALTER TABLE public.sites ADD CONSTRAINT sites_regulatory_body_id_regulatory_bodies_id_fk FOREIGN KEY (regulatory_body_id) REFERENCES public.regulatory_bodies(id);
ALTER TABLE public.sites ADD CONSTRAINT sites_type_id_site_types_id_fk FOREIGN KEY (type_id) REFERENCES public.site_types(id);