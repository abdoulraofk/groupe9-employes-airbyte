"""
Automatisation du scenario de bout en bout decrit dans scenario_bout_en_bout.md,
avec le repli de synchronisation (service docker-compose `sync-fallback`).

    docker compose up -d mysql postgres api
    docker compose --profile dev-sync up -d sync-fallback
    BASE_URL=http://localhost:5000 python tests/test_sync_scenario.py
"""
import os
import sys
import time

import pymysql
import requests

BASE_URL = os.environ.get("BASE_URL", "http://localhost:5000")
API = f"{BASE_URL}/api/v1"

MYSQL_CFG = dict(
    host=os.environ.get("MYSQL_HOST", "localhost"),
    port=int(os.environ.get("MYSQL_PORT", 3306)),
    user="root",
    password=os.environ.get("MYSQL_ROOT_PASSWORD", "root_pwd"),
    database="rh_source",
)

SYNC_INTERVAL = int(os.environ.get("SYNC_INTERVAL", 15))


def get_nom(matricule):
    r = requests.get(f"{API}/employes/{matricule}")
    r.raise_for_status()
    return r.json()["nom"]


def main():
    matricule = "EMP0001"
    nouveau_nom = f"KABORE-TEST-{int(time.time())}"

    avant = get_nom(matricule)
    print(f"Avant modification : {matricule} -> {avant}")

    conn = pymysql.connect(**MYSQL_CFG)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE employes SET nom=%s WHERE matricule=%s",
                (nouveau_nom, matricule),
            )
        conn.commit()
    finally:
        conn.close()
    print(f"Source MySQL modifiee : {matricule} -> {nouveau_nom}")

    immediat = get_nom(matricule)
    print(f"Immediatement apres (avant sync) : {matricule} -> {immediat}")

    print(f"Attente de {SYNC_INTERVAL + 5}s pour laisser la synchronisation tourner...")
    time.sleep(SYNC_INTERVAL + 5)

    apres = get_nom(matricule)
    print(f"Apres synchronisation : {matricule} -> {apres}")

    if apres != nouveau_nom:
        print("ECHEC : la modification source n'est pas apparue dans l'API apres synchronisation.")
        sys.exit(1)

    print("OK : la modification source est bien apparue dans l'API apres synchronisation.")


if __name__ == "__main__":
    main()
