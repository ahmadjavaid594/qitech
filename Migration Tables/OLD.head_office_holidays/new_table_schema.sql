-- public.company_user_leaves definition

-- Drop table

-- DROP TABLE public.company_user_leaves;

CREATE TABLE public.company_user_leaves (
	id uuid DEFAULT gen_random_uuid() NOT NULL,
	company_user_id uuid NOT NULL,
	"to" timestamptz DEFAULT now() NOT NULL,
	"from" timestamptz DEFAULT now() NOT NULL,
	reason text NOT NULL,
	created_at timestamptz DEFAULT now() NOT NULL,
	updated_at timestamptz DEFAULT now() NOT NULL,
	CONSTRAINT company_user_leaves_company_user_id_to_from_unique UNIQUE (company_user_id, "to", "from"),
	CONSTRAINT company_user_leaves_pkey PRIMARY KEY (id),
	CONSTRAINT company_user_leaves_company_user_id_company_users_id_fk FOREIGN KEY (company_user_id) REFERENCES public.company_users(id)
);