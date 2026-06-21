-- public.users definition

-- Drop table

-- DROP TABLE public.users;

CREATE TABLE public.users (
	id uuid DEFAULT gen_random_uuid() NOT NULL,
	external_id int8 NULL,
	first_name text NOT NULL,
	middle_name text NULL,
	surname text NOT NULL,
	date_of_birth date NULL,
	email text NOT NULL,
	is_email_hidden bool DEFAULT false NOT NULL,
	email_verified_at timestamptz NULL,
	password_hash text NULL,
	password_reset_at timestamptz NULL,
	phone_number text NULL,
	is_phone_number_hidden bool DEFAULT false NOT NULL,
	photo text NULL,
	"status" public."status" DEFAULT 'active'::status NOT NULL,
	status_comment text NULL,
	role_id uuid NOT NULL,
	created_at timestamptz DEFAULT now() NOT NULL,
	updated_at timestamptz DEFAULT now() NOT NULL,
	deleted_at timestamptz NULL,
	pseudonymized_at timestamptz NULL,
	CONSTRAINT users_email_unique UNIQUE (email),
	CONSTRAINT users_pkey PRIMARY KEY (id)
);


-- public.users foreign keys

ALTER TABLE public.users ADD CONSTRAINT users_role_id_roles_id_fk FOREIGN KEY (role_id) REFERENCES public.roles(id);