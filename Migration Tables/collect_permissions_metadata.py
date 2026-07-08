#!/usr/bin/env python3
"""
Collect metadata required for migrating old QI-Tech permissions
(MySQL) to new permission system (PostgreSQL).

Output:
permission_metadata/
    mysql/
    postgres/
    report.json
"""

import os
import json
import csv
import logging
import sys
from pathlib import Path

try:
    import pymysql
    import pymysql.cursors
    import psycopg2
    import psycopg2.extras
except Exception as e:
    logging.error("Missing dependency: %s", e)
    logging.error("Install: pip install pymysql psycopg2-binary")
    sys.exit(1)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)


# =====================================================
# DATABASE CONFIGURATION
# =====================================================

MYSQL_HOST = os.getenv("MYSQL_HOST", "127.0.0.1")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "root")
MYSQL_DB = os.getenv("MYSQL_DB", "qitech")


PG_HOST = os.getenv(
    "PG_HOST",
    "qitech-pg-test-17943.postgres.database.azure.com"
)

PG_PORT = int(os.getenv("PG_PORT", "5432"))

PG_USER = os.getenv(
    "PG_USER",
    "pgadmin"
)

PG_PASSWORD = os.getenv(
    "PG_PASSWORD",
    "2fac05f6ac12e581bc2aeb8bc188deac"
)

PG_DB = os.getenv(
    "PG_DB",
    "qi-tech"
)


OUTPUT = Path("permission_metadata")


# =====================================================
# HELPERS
# =====================================================

def json_serializer(obj):

    if hasattr(obj, "isoformat"):
        return obj.isoformat()

    return str(obj)



def save_json(path, data):

    path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with open(
        path,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            data,
            f,
            indent=2,
            default=json_serializer
        )



def save_csv(path, rows):

    if not rows:
        return

    path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with open(
        path,
        "w",
        newline="",
        encoding="utf-8"
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=rows[0].keys()
        )

        writer.writeheader()
        writer.writerows(rows)



# =====================================================
# MYSQL
# =====================================================

def mysql_tables(conn):

    with conn.cursor() as cur:

        cur.execute("""
            SELECT TABLE_NAME
            FROM information_schema.tables
            WHERE table_schema=%s
        """, (MYSQL_DB,))


        rows = cur.fetchall()


        return [
            row["TABLE_NAME"]
            for row in rows
        ]



def mysql_create_table(conn, table):

    with conn.cursor() as cur:

        cur.execute(
            f"SHOW CREATE TABLE `{table}`"
        )

        row = cur.fetchone()


        values = list(row.values())

        if len(values) > 1:
            return values[1]

        return ""



def mysql_columns(conn):

    with conn.cursor() as cur:

        cur.execute("""
            SELECT
                TABLE_NAME,
                COLUMN_NAME,
                DATA_TYPE
            FROM information_schema.columns
            WHERE table_schema=%s
            ORDER BY TABLE_NAME
        """, (MYSQL_DB,))


        return cur.fetchall()



def mysql_sample(conn, table):

    try:

        with conn.cursor() as cur:

            cur.execute(
                f"SELECT * FROM `{table}` LIMIT 20"
            )

            return cur.fetchall()

    except Exception as e:

        logging.warning(
            "Could not sample table %s : %s",
            table,
            e
        )

        return []



def collect_mysql(conn):

    logging.info(
        "Collecting MySQL metadata"
    )


    base = OUTPUT / "mysql"


    tables = mysql_tables(conn)


    save_json(
        base / "tables.json",
        tables
    )


    create_sql = {}


    for table in tables:

        try:

            create_sql[table] = mysql_create_table(
                conn,
                table
            )

        except Exception as e:

            logging.warning(
                "Failed CREATE TABLE %s : %s",
                table,
                e
            )


    save_json(
        base / "create_tables.json",
        create_sql
    )


    save_json(
        base / "columns.json",
        mysql_columns(conn)
    )


    keywords = [
        "user",
        "access",
        "permission",
        "role",
        "profile",
        "report",
        "chart"
    ]


    related_tables = [
        table
        for table in tables
        if any(
            k in table.lower()
            for k in keywords
        )
    ]


    save_json(
        base / "permission_related_tables.json",
        related_tables
    )


    for table in related_tables:

        save_csv(
            base / f"{table}.csv",
            mysql_sample(conn, table)
        )


    logging.info(
        "MySQL collected %s tables",
        len(tables)
    )



# =====================================================
# POSTGRES
# =====================================================

def pg_tables(conn):

    with conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    ) as cur:


        cur.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema='public'
        """)


        return [
            row["table_name"]
            for row in cur.fetchall()
        ]



def pg_columns(conn):

    with conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    ) as cur:


        cur.execute("""
            SELECT
                table_name,
                column_name,
                data_type
            FROM information_schema.columns
            WHERE table_schema='public'
            ORDER BY table_name
        """)


        return cur.fetchall()



def pg_sample(conn, table):

    try:

        with conn.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor
        ) as cur:


            cur.execute(
                f'SELECT * FROM public."{table}" LIMIT 20'
            )


            return cur.fetchall()


    except Exception as e:

        logging.warning(
            "Could not sample PG table %s : %s",
            table,
            e
        )

        return []



def pg_foreign_keys(conn):

    with conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    ) as cur:


        cur.execute("""
            SELECT
                tc.table_name,
                kcu.column_name,
                ccu.table_name AS foreign_table,
                ccu.column_name AS foreign_column

            FROM information_schema.table_constraints tc

            JOIN information_schema.key_column_usage kcu
            ON tc.constraint_name=kcu.constraint_name

            JOIN information_schema.constraint_column_usage ccu
            ON ccu.constraint_name=tc.constraint_name

            WHERE tc.constraint_type='FOREIGN KEY'
        """)


        return cur.fetchall()



def collect_postgres(conn):

    logging.info(
        "Collecting PostgreSQL metadata"
    )


    base = OUTPUT / "postgres"


    tables = pg_tables(conn)


    save_json(
        base / "tables.json",
        tables
    )


    save_json(
        base / "columns.json",
        pg_columns(conn)
    )


    save_json(
        base / "foreign_keys.json",
        pg_foreign_keys(conn)
    )


    required_tables = [
        "permissions",
        "permission_assignments",
        "roles",
        "company_roles",
        "company_users",
        "users",
        "companies"
    ]


    for table in required_tables:

        if table in tables:

            save_csv(
                base / f"{table}.csv",
                pg_sample(conn, table)
            )


    logging.info(
        "Postgres collected %s tables",
        len(tables)
    )



# =====================================================
# MAIN
# =====================================================

def main():

    OUTPUT.mkdir(
        exist_ok=True
    )


    logging.info(
        "Connecting MySQL"
    )


    mysql_conn = pymysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        db=MYSQL_DB,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor
    )



    logging.info(
        "Connecting PostgreSQL"
    )


    pg_conn = psycopg2.connect(
        host=PG_HOST,
        port=PG_PORT,
        user=PG_USER,
        password=PG_PASSWORD,
        dbname=PG_DB
    )


    try:

        collect_mysql(mysql_conn)

        collect_postgres(pg_conn)


        save_json(
            OUTPUT / "report.json",
            {
                "mysql_database": MYSQL_DB,
                "postgres_database": PG_DB,
                "status": "completed"
            }
        )


        logging.info(
            "Metadata collection completed successfully"
        )


    finally:

        mysql_conn.close()
        pg_conn.close()



if __name__ == "__main__":

    main()