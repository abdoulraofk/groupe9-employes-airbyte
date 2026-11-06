#!/usr/bin/env python3
"""
Configuration reproductible de la connexion Airbyte rh_source (MySQL) -> rh_target
(PostgreSQL), via l'API publique d'Airbyte OSS (/api/public/v1/...).

Remplace la configuration manuelle via l'UI decrite dans README.md : ce script est
le mecanisme demande par la clause "installation reproductible" du cahier des
charges pour un outil (Airbyte) qui suit par ailleurs sa propre procedure
d'installation (abctl, cf. README.md).

Idempotent : recherche une source/destination/connexion du meme nom avant d'en
creer une nouvelle, pour pouvoir etre rejoue sans dupliquer la configuration.

Note sur l'API : l'ancienne API Config (/api/v1/...) utilisee par les versions
anciennes d'Airbyte OSS est desormais reservee a l'usage interne du serveur et
refuse les jetons d'application (403 Forbidden). Ce script utilise donc l'API
publique (/api/public/v1/...), authentifiee par un jeton OAuth client_id/
client_secret recupere via `abctl local credentials`.

Usage :
    python configure_airbyte.py --airbyte-url http://localhost:8000 \
        --mysql-host <host> --mysql-port 3306 \
        --postgres-host <host> --postgres-port 5432 \
        --client-id <client_id> --client-secret <client_secret>
"""
import argparse
import sys
import time

import requests

_ACCESS_TOKEN = None

# Connecteurs officiels Airbyte (identifiants stables du catalogue public).
MYSQL_DEFINITION_ID = "435bb9a5-7887-4809-aa58-28c27df0d7ad"
POSTGRES_DEFINITION_ID = "25c5221d-dce2-4163-ade9-739ef790f503"


def get_access_token(base_url, client_id, client_secret):
    resp = requests.post(
        f"{base_url}/api/public/v1/applications/token",
        json={"client_id": client_id, "client_secret": client_secret},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def api(base_url, method, path, payload=None, params=None, timeout=30):
    headers = {"Authorization": f"Bearer {_ACCESS_TOKEN}"}
    resp = requests.request(
        method, f"{base_url}/api/public/v1{path}",
        json=payload, params=params, headers=headers, timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json() if resp.content else None


def get_workspace_id(base_url):
    resp = api(base_url, "GET", "/workspaces")
    workspaces = resp["data"]
    if not workspaces:
        sys.exit("Aucun workspace Airbyte trouve. Terminer l'assistant d'installation dans l'UI d'abord.")
    return workspaces[0]["workspaceId"]


def ensure_source(base_url, workspace_id, args):
    existing = api(base_url, "GET", "/sources", params={"workspaceIds": workspace_id})
    for s in existing["data"]:
        if s["name"] == "rh_source_mysql":
            return s["sourceId"]

    payload = {
        "name": "rh_source_mysql",
        "workspaceId": workspace_id,
        "configuration": {
            "sourceType": "mysql",
            "host": args.mysql_host,
            "port": args.mysql_port,
            "database": args.mysql_db,
            "username": args.mysql_user,
            "password": args.mysql_password,
            "replication_method": {"method": "STANDARD"},
        },
    }
    created = api(base_url, "POST", "/sources", payload)
    return created["sourceId"]


def ensure_destination(base_url, workspace_id, args):
    existing = api(base_url, "GET", "/destinations", params={"workspaceIds": workspace_id})
    for d in existing["data"]:
        if d["name"] == "rh_target_postgres":
            return d["destinationId"]

    payload = {
        "name": "rh_target_postgres",
        "workspaceId": workspace_id,
        "configuration": {
            "destinationType": "postgres",
            "host": args.postgres_host,
            "port": args.postgres_port,
            "database": args.postgres_db,
            "schema": "public",
            "username": args.postgres_user,
            "password": args.postgres_password,
            "ssl_mode": {"mode": "disable"},
        },
    }
    created = api(base_url, "POST", "/destinations", payload)
    return created["destinationId"]


def find_connection(base_url, workspace_id, name):
    existing = api(base_url, "GET", "/connections", params={"workspaceIds": workspace_id})
    for c in existing["data"]:
        if c["name"] == name:
            return c["connectionId"]
    return None


def ensure_connection(base_url, workspace_id, source_id, destination_id):
    """Cree la connexion rh_source -> rh_target (Incremental | Deduped, cursor=updated_at).

    La creation declenche une decouverte de schema reelle contre MySQL (cold start
    du pod connecteur sur le cluster kind d'abctl : jusqu'a plusieurs minutes),
    ce qui depasse souvent le delai de l'ingress nginx local (502 Bad Gateway cote
    client) alors que la connexion est en realite creee cote serveur. On retente
    donc la recherche par nom pendant quelques minutes avant d'abandonner.
    """
    name = "rh_source_to_rh_target"
    existing_id = find_connection(base_url, workspace_id, name)
    if existing_id:
        return existing_id

    payload = {
        "name": name,
        "sourceId": source_id,
        "destinationId": destination_id,
        "namespaceDefinition": "custom_format",
        "namespaceFormat": "public",
        "schedule": {"scheduleType": "manual"},
        "configurations": {
            "streams": [
                {"name": "employes", "syncMode": "incremental_deduped_history",
                 "primaryKey": [["matricule"]], "cursorField": ["updated_at"]},
                {"name": "services", "syncMode": "incremental_deduped_history",
                 "primaryKey": [["id"]], "cursorField": ["updated_at"]},
                {"name": "fonctions", "syncMode": "incremental_deduped_history",
                 "primaryKey": [["id"]], "cursorField": ["updated_at"]},
            ],
        },
    }
    try:
        created = api(base_url, "POST", "/connections", payload, timeout=600)
        return created["connectionId"]
    except requests.exceptions.RequestException as exc:
        print(f"Avertissement : la creation de la connexion a signale une erreur cote "
              f"client ({exc}) ; nouvelle tentative de la retrouver par nom pendant "
              f"5 minutes (le serveur Airbyte continue le traitement en arriere-plan).")
        for _ in range(30):
            time.sleep(10)
            found_id = find_connection(base_url, workspace_id, name)
            if found_id:
                return found_id
        sys.exit("La connexion n'a pas pu etre creee (ni retrouvee apres 5 minutes).")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--airbyte-url", default="http://localhost:8000")
    parser.add_argument("--mysql-host", required=True)
    parser.add_argument("--mysql-port", type=int, default=3306)
    parser.add_argument("--mysql-db", default="rh_source")
    parser.add_argument("--mysql-user", default="airbyte_reader")
    parser.add_argument("--mysql-password", default="airbyte_reader_pwd")
    parser.add_argument("--postgres-host", required=True)
    parser.add_argument("--postgres-port", type=int, default=5432)
    parser.add_argument("--postgres-db", default="rh_target")
    parser.add_argument("--postgres-user", default="postgres")
    parser.add_argument("--postgres-password", default="postgres_pwd")
    parser.add_argument("--client-id", required=True, help="cf. `abctl local credentials`")
    parser.add_argument("--client-secret", required=True, help="cf. `abctl local credentials`")
    args = parser.parse_args()

    base_url = args.airbyte_url.rstrip("/")

    global _ACCESS_TOKEN
    _ACCESS_TOKEN = get_access_token(base_url, args.client_id, args.client_secret)

    workspace_id = get_workspace_id(base_url)
    print(f"Workspace : {workspace_id}")

    source_id = ensure_source(base_url, workspace_id, args)
    print(f"Source MySQL : {source_id}")

    destination_id = ensure_destination(base_url, workspace_id, args)
    print(f"Destination PostgreSQL : {destination_id}")

    connection_id = ensure_connection(base_url, workspace_id, source_id, destination_id)
    print(f"Connexion rh_source -> rh_target : {connection_id}")
    print("Configuration terminee. Schedule = manuel : declencher une synchronisation "
          "depuis l'UI, ou via POST /api/public/v1/jobs "
          '{"connectionId": "...", "jobType": "sync"}.')


if __name__ == "__main__":
    main()
