Migration script: MySQL `amp` -> Postgres `dmd_actual_medicinal_products`

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

- The script maps columns as follows: `id` -> `external_id`, `VPID` -> `virtual_medicinal_product_id`, `APID` -> `supplier_code`, `NM` -> `name`.
- `DESC` is attempted to be parsed as a small integer for `lic_auth_code`; otherwise left NULL.
- `release_version` is set to `migrated` and `invalid` to `false`.
