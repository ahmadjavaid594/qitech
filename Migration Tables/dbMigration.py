#!/usr/bin/env python3
"""Migrate legacy form data from MySQL to Postgres form tables."""
import json
import logging
import os
import sys
import uuid
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

try:
    import pymysql.cursors
    import psycopg2
    import psycopg2.extras
except Exception as e:  # pragma: no cover - import guard
    logging.error("Missing Python dependency: %s", e)
    logging.error("Install dependencies: pip install pymysql psycopg2-binary")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

MYSQL_HOST = os.getenv("MYSQL_HOST", "127.0.0.1")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "root")
MYSQL_DB = os.getenv("MYSQL_DB", "qitech")

PG_HOST = os.getenv("PG_HOST", "qitech-pg-test-17943.postgres.database.azure.com")
PG_PORT = int(os.getenv("PG_PORT", "5432"))
PG_USER = os.getenv("PG_USER", "pgadmin")
PG_PASSWORD = os.getenv("PG_PASSWORD", "2fac05f6ac12e581bc2aeb8bc188deac")
PG_DB = os.getenv("PG_DB", "qi-tech")
