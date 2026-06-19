Migration script: MySQL `qitech.dmd_suppliers` -> Postgres `public.dmd_lookup_suppliers`

Usage

- Set connection environment variables or edit defaults in `migration.py`:

  - `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_DB`
  - `PG_HOST`, `PG_PORT`, `PG_USER`, `PG_PASSWORD`, `PG_DB`

- Install dependencies:

```bash
pip install pymysql psycopg2-binary
```

- Dry-run (no inserts):

```bash
python migration.py --dry-run
```

- Run migration:

```bash
python migration.py
```

Notes

- The script migrates the following fields:
  - `cd` -> `id`
  - `desc` -> `description`
  - `created_at` -> `created_at`
  - `updated_at` -> `updated_at`
- `cd` is used as the target key value instead of preserving the source numeric `id`.
- `cd_prev` and `cd_date` are not migrated because the target table does not define equivalent columns.
- If a source row has NULL `created_at` or `updated_at`, the script uses the current timestamp instead of NULL.
