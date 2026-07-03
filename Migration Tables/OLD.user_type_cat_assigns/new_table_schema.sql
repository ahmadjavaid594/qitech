-- public.user_type_categories definition

-- Drop table

-- DROP TABLE public.user_type_categories;

CREATE TABLE public.user_type_categories (
	id uuid DEFAULT gen_random_uuid() NOT NULL,
	user_type_id uuid NOT NULL,
	category_id uuid NOT NULL,
	CONSTRAINT user_type_categories_pkey PRIMARY KEY (id),
	CONSTRAINT user_type_categories_category_id_categories_id_fk FOREIGN KEY (category_id) REFERENCES public.categories(id),
	CONSTRAINT user_type_categories_user_type_id_user_types_id_fk FOREIGN KEY (user_type_id) REFERENCES public.user_types(id)
);
CREATE UNIQUE INDEX user_type_categories_user_type_id_category_id_index ON public.user_type_categories USING btree (user_type_id, category_id);


-- public.company_user_user_types definition

-- Drop table

-- DROP TABLE public.company_user_user_types;

CREATE TABLE public.company_user_user_types (
	id uuid DEFAULT gen_random_uuid() NOT NULL,
	company_user_id uuid NOT NULL,
	user_type_id uuid NOT NULL,
	is_main bool DEFAULT false NOT NULL,
	regulatory_body_id uuid NULL,
	registration_number text NULL,
	CONSTRAINT company_user_user_types_pkey PRIMARY KEY (id),
	CONSTRAINT company_user_user_types_company_user_id_company_users_id_fk FOREIGN KEY (company_user_id) REFERENCES public.company_users(id),
	CONSTRAINT company_user_user_types_regulatory_body_id_regulatory_bodies_id FOREIGN KEY (regulatory_body_id) REFERENCES public.regulatory_bodies(id),
	CONSTRAINT company_user_user_types_user_type_id_user_types_id_fk FOREIGN KEY (user_type_id) REFERENCES public.user_types(id)
);
CREATE UNIQUE INDEX company_user_user_types_company_user_id_user_type_id_index ON public.company_user_user_types USING btree (company_user_id, user_type_id);
CREATE UNIQUE INDEX company_user_user_types_one_main_idx ON public.company_user_user_types USING btree (company_user_id) WHERE (is_main = true);