#!/usr/bin/env python3
"""
Repli de synchronisation MySQL -> PostgreSQL, utilise a deux fins :

1. Developpement/CI : permet de tester l'API sans attendre le demarrage complet
   d'Airbyte (pile lourde, voir airbyte/README.md).
2. Reference de schema : reproduit le schema que produit Airbyte Destination V2
   (colonnes _airbyte_raw_id / _airbyte_extracted_at / _airbyte_meta + colonnes
   metier), afin que l'API lise exactement la meme forme de table, qu'elle vienne
   d'Airbyte ou de ce script.

Mode "full refresh + dedup" par cle primaire (matricule / id), comme le mode
"Append + Deduped" d'Airbyte. Appele periodiquement, il materialise donc le
meme comportement de synchronisation incrementale que la connexion Airbyte
configuree dans airbyte/configure_airbyte.py (cursor = updated_at).

Usage :
    python sync_mysql_to_postgres.py [--once] [--interval 30]
"""
import argparse
import os
import time
import uuid
from datetime import datetime, timezone

import pymysql
import psycopg2
import psycopg2.extras

MYSQL_CFG = dict(
    host=os.environ.get("MYSQL_HOST", "localhost"),
    port=int(os.environ.get("MYSQL_PORT", 3306)),
    user=os.environ.get("MYSQL_USER", "airbyte_reader"),
    password=os.environ.get("MYSQL_PASSWORD", "airbyte_reader_pwd"),
    database=os.environ.get("MYSQL_DB", "rh_source"),
    cursorclass=pymysql.cursors.DictCursor,
)

PG_CFG = dict(
    host=os.environ.get("PG_HOST", "localhost"),
    port=int(os.environ.get("PG_PORT", 5432)),
    user=os.environ.get("PG_USER", "postgres"),
    password=os.environ.get("PG_PASSWORD", "postgres_pwd"),
    dbname=os.environ.get("PG_DB", "rh_target"),
)

TABLES = {
    "services": ("id", ["id", "code", "nom", "updated_at"]),
    "fonctions": ("id", ["id", "code", "libelle", "updated_at"]),
    "employes": (
        "matricule",
        ["matricule", "nom", "prenom", "email", "service_id", "fonction_id",
         "date_embauche", "actif", "updated_at"],
    ),
}

PG_TYPES = {
    "id": "INTEGER", "matricule": "VARCHAR(12)", "code": "VARCHAR(10)",
    "nom": "VARCHAR(100)", "libelle": "VARCHAR(100)", "prenom": "VARCHAR(80)",
    "email": "VARCHAR(150)", "service_id": "INTEGER", "fonction_id": "INTEGER",
    "date_embauche": "DATE", "actif": "BOOLEAN", "updated_at": "TIMESTAMP",
}


def ensure_table(pg_cur, table, pk, columns):
    cols_sql = ", ".join(f'"{c}" {PG_TYPES[c]}' for c in columns)
    pg_cur.execute(f"""
        CREATE TABLE IF NOT EXISTS "{table}" (
            {cols_sql},
            "_airbyte_raw_id" UUID NOT NULL,
            "_airbyte_extracted_at" TIMESTAMPTZ NOT NULL,
            "_airbyte_meta" JSONB NOT NULL,
            PRIMARY KEY ("{pk}")
        )
    """)


def sync_table(my_cur, pg_cur, table, pk, columns):
    my_cur.execute(f"SELECT {', '.join(columns)} FROM {table}")
    rows = my_cur.fetchall()
    extracted_at = datetime.now(timezone.utc)

    col_list = ", ".join(f'"{c}"' for c in columns)
    placeholders = ", ".join(["%s"] * len(columns))
    update_set = ", ".join(f'"{c}" = EXCLUDED."{c}"' for c in columns if c != pk)

    for row in rows:
        values = [bool(row[c]) if c == "actif" else row[c] for c in columns]
        values += [str(uuid.uuid4()), extracted_at, psycopg2.extras.Json({})]
        pg_cur.execute(f"""
            INSERT INTO "{table}" ({col_list}, "_airbyte_raw_id", "_airbyte_extracted_at", "_airbyte_meta")
            VALUES ({placeholders}, %s, %s, %s)
            ON CONFLICT ("{pk}") DO UPDATE SET
                {update_set},
                "_airbyte_raw_id" = EXCLUDED."_airbyte_raw_id",
                "_airbyte_extracted_at" = EXCLUDED."_airbyte_extracted_at"
        """, values)
    return len(rows)


def run_once():
    my_conn = pymysql.connect(**MYSQL_CFG)
    pg_conn = psycopg2.connect(**PG_CFG)
    pg_conn.autocommit = False
    try:
        with my_conn.cursor() as my_cur, pg_conn.cursor() as pg_cur:
            total = 0
            for table, (pk, columns) in TABLES.items():
                ensure_table(pg_cur, table, pk, columns)
                total += sync_table(my_cur, pg_cur, table, pk, columns)
        pg_conn.commit()
        print(f"[{datetime.now().isoformat(timespec='seconds')}] sync OK, {total} lignes traitees")
    except Exception:
        pg_conn.rollback()
        raise
    finally:
        my_conn.close()
        pg_conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="une seule passe puis quitte")
    parser.add_argument("--interval", type=int, default=30, help="secondes entre deux passes")
    args = parser.parse_args()

    if args.once:
        run_once()
    else:
        while True:
            run_once()
            time.sleep(args.interval)
