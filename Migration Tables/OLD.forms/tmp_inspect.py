import os
import pymysql.cursors
import psycopg2

mysql = pymysql.connect(host=os.getenv('MYSQL_HOST','127.0.0.1'), port=int(os.getenv('MYSQL_PORT','3306')), user=os.getenv('MYSQL_USER','root'), password=os.getenv('MYSQL_PASSWORD','root'), db=os.getenv('MYSQL_DB','qitech'), charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor)
pg = psycopg2.connect(host=os.getenv('PG_HOST','qitech-pg-test-17943.postgres.database.azure.com'), port=int(os.getenv('PG_PORT','5432')), user=os.getenv('PG_USER','pgadmin'), password=os.getenv('PG_PASSWORD','2fac05f6ac12e581bc2aeb8bc188deac'), dbname=os.getenv('PG_DB','qi-tech'))

with mysql.cursor() as cur:
    cur.execute("SELECT id, reference_type, reference_id, name FROM be_spoke_form WHERE id BETWEEN 310 AND 318 ORDER BY id")
    print('MYSQL forms:')
    for row in cur.fetchall():
        print(row)

with pg.cursor() as cur:
    cur.execute("SELECT id, external_id, name FROM public.companies ORDER BY id")
    rows = cur.fetchall()
    print('\nPOSTGRES companies:')
    for row in rows:
        print(row)
