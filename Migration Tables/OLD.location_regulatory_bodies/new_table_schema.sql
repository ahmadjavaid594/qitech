-- public.regulatory_bodies definition

-- Drop table

-- DROP TABLE public.regulatory_bodies;

CREATE TABLE public.regulatory_bodies (
	id uuid DEFAULT gen_random_uuid() NOT NULL,
	external_id int8 NULL,
	"name" text NOT NULL,
	country_id uuid NULL,
	registration_number_regex text NULL,
	created_at timestamptz DEFAULT now() NOT NULL,
	updated_at timestamptz DEFAULT now() NOT NULL,
	CONSTRAINT regulatory_bodies_pkey PRIMARY KEY (id)
);


-- public.regulatory_bodies foreign keys

ALTER TABLE public.regulatory_bodies ADD CONSTRAINT regulatory_bodies_country_id_countries_id_fk FOREIGN KEY (country_id) REFERENCES public.countries(id);