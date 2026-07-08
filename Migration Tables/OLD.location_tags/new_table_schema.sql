-- public.tags definition

-- Drop table

-- DROP TABLE public.tags;

CREATE TABLE public.tags (
	id uuid DEFAULT gen_random_uuid() NOT NULL,
	"name" text NOT NULL,
	company_id uuid NOT NULL,
	parent_id uuid NULL,
	category_id uuid NULL,
	"order" int4 DEFAULT 0 NOT NULL,
	"type" public."tag_type" NOT NULL,
	text_color text DEFAULT '#FFFFFF'::text NOT NULL,
	background_color text DEFAULT '#000000'::text NOT NULL,
	icon text DEFAULT 'tag-01'::text NOT NULL,
	icon_color text DEFAULT '#000000'::text NOT NULL,
	visibility public."tag_visibility" DEFAULT 'all'::tag_visibility NOT NULL,
	priority int4 DEFAULT 1 NOT NULL,
	display public."tag_display" DEFAULT 'main_only'::tag_display NOT NULL,
	"permission" public."tag_permission" DEFAULT 'all'::tag_permission NOT NULL,
	created_at timestamptz DEFAULT now() NOT NULL,
	updated_at timestamptz DEFAULT now() NOT NULL,
	archived_at timestamptz NULL,
	CONSTRAINT tags_pkey PRIMARY KEY (id),
	CONSTRAINT tags_category_id_categories_id_fk FOREIGN KEY (category_id) REFERENCES public.categories(id),
	CONSTRAINT tags_company_id_companies_id_fk FOREIGN KEY (company_id) REFERENCES public.companies(id),
	CONSTRAINT tags_parent_id_tags_id_fk FOREIGN KEY (parent_id) REFERENCES public.tags(id)
);
CREATE UNIQUE INDEX tags_company_id_category_id_parent_id_name_index ON public.tags USING btree (company_id, category_id, parent_id, name);



-- public.site_tag definition

-- Drop table

-- DROP TABLE public.site_tag;

CREATE TABLE public.site_tag (
	site_id uuid NOT NULL,
	tag_id uuid NOT NULL,
	CONSTRAINT site_tag_site_id_sites_id_fk FOREIGN KEY (site_id) REFERENCES public.sites(id) ON DELETE CASCADE,
	CONSTRAINT site_tag_tag_id_tags_id_fk FOREIGN KEY (tag_id) REFERENCES public.tags(id) ON DELETE CASCADE
);
CREATE UNIQUE INDEX site_tag_site_id_tag_id_index ON public.site_tag USING btree (site_id, tag_id);