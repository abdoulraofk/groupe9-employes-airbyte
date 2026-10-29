#!/usr/bin/env python3
"""
Configuration reproductible de la connexion Airbyte rh_source (MySQL) -> rh_target
(PostgreSQL), via l'API Config d'Airbyte OSS (/api/v1/...).

Remplace la configuration manuelle via l'UI decrite dans README.md : ce script est
le mecanisme demande par la clause "installation reproductible" du cahier des
charges pour un outil (Airbyte) qui suit par ailleurs sa propre procedure
d'installation (abctl, cf. README.md).

Idempotent : recherche une source/destination/connexion du meme nom avant d'en
creer une nouvelle, pour pouvoir etre rejoue sans dupliquer la configuration.

Usage :
    python configure_airbyte.py --airbyte-url http://localhost:8000 \
        --mysql-host <host> --mysql-port 3306 \
        --postgres-host <host> --postgres-port 5432
"""
import argparse
import sys

import requests


def api_post(base_url, path, payload):
    resp = requests.post(f"{base_url}/api/v1{path}", json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()


def find_by_name(base_url, list_path, workspace_id, name, key="name"):
    resp = api_post(base_url, list_path, {"workspaceId": workspace_id})
    for item in resp.get(list_path.rsplit("/", 1)[-1] + "s", []) or resp.get("sources", []) or resp.get("destinations", []):
        if item.get(key) == name:
            return item
    return None


def get_workspace_id(base_url):
    resp = api_post(base_url, "/workspaces/list", {})
    workspaces = resp["workspaces"]
    if not workspaces:
        sys.exit("Aucun workspace Airbyte trouve. Terminer l'assistant d'installation dans l'UI d'abord.")
    return workspaces[0]["workspaceId"]


def get_source_definition_id(base_url, name_contains):
    resp = api_post(base_url, "/source_definitions/list", {})
    for d in resp["sourceDefinitions"]:
        if name_contains.lower() in d["name"].lower():
            return d["sourceDefinitionId"]
    sys.exit(f"Definition de source introuvable pour '{name_contains}'")


def get_destination_definition_id(base_url, name_contains):
    resp = api_post(base_url, "/destination_definitions/list", {})
    for d in resp["destinationDefinitions"]:
        if name_contains.lower() in d["name"].lower():
            return d["destinationDefinitionId"]
    sys.exit(f"Definition de destination introuvable pour '{name_contains}'")


def ensure_source(base_url, workspace_id, args):
    existing = api_post(base_url, "/sources/list", {"workspaceId": workspace_id})
    for s in existing.get("sources", []):
        if s["name"] == "rh_source_mysql":
            return s["sourceId"]

    definition_id = get_source_definition_id(base_url, "MySQL")
    payload = {
        "workspaceId": workspace_id,
        "name": "rh_source_mysql",
        "sourceDefinitionId": definition_id,
        "connectionConfiguration": {
            "host": args.mysql_host,
            "port": args.mysql_port,
            "database": args.mysql_db,
            "username": args.mysql_user,
            "password": args.mysql_password,
            "replication_method": {"method": "STANDARD"},
            "ssl": False,
        },
    }
    created = api_post(base_url, "/sources/create", payload)
    return created["sourceId"]


def ensure_destination(base_url, workspace_id, args):
    existing = api_post(base_url, "/destinations/list", {"workspaceId": workspace_id})
    for d in existing.get("destinations", []):
        if d["name"] == "rh_target_postgres":
            return d["destinationId"]

    definition_id = get_destination_definition_id(base_url, "Postgres")
    payload = {
        "workspaceId": workspace_id,
        "name": "rh_target_postgres",
        "destinationDefinitionId": definition_id,
        "connectionConfiguration": {
            "host": args.postgres_host,
            "port": args.postgres_port,
            "database": args.postgres_db,
            "schema": "public",
            "username": args.postgres_user,
            "password": args.postgres_password,
            "ssl": False,
        },
    }
    created = api_post(base_url, "/destinations/create", payload)
    return created["destinationId"]


def discover_streams(base_url, source_id):
    resp = api_post(base_url, "/sources/discover_schema", {"sourceId": source_id})
    return resp["catalog"]


def build_configured_catalog(catalog):
    """Active employes/services/fonctions en Incremental|Deduped, cursor=updated_at."""
    pk_by_stream = {
        "employes": [["matricule"]],
        "services": [["id"]],
        "fonctions": [["id"]],
    }
    streams = []
    for s in catalog["streams"]:
        name = s["stream"]["name"]
        if name not in pk_by_stream:
            continue
        s["config"]["syncMode"] = "incremental"
        s["config"]["destinationSyncMode"] = "append_dedup"
        s["config"]["cursorField"] = ["updated_at"]
        s["config"]["primaryKey"] = pk_by_stream[name]
        s["config"]["selected"] = True
        streams.append(s)
    return {"streams": streams}


def ensure_connection(base_url, source_id, destination_id, catalog):
    existing = api_post(base_url, "/connections/list", {"sourceId": source_id})
    for c in existing.get("connections", []):
        if c["name"] == "rh_source_to_rh_target":
            return c["connectionId"]

    payload = {
        "sourceId": source_id,
        "destinationId": destination_id,
        "name": "rh_source_to_rh_target",
        "namespaceDefinition": "customformat",
        "namespaceFormat": "public",
        "status": "active",
        "scheduleType": "basic",
        "scheduleData": {"basicSchedule": {"units": 5, "timeUnit": "minutes"}},
        "syncCatalog": build_configured_catalog(catalog),
    }
    created = api_post(base_url, "/connections/create", payload)
    return created["connectionId"]


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
    args = parser.parse_args()

    base_url = args.airbyte_url.rstrip("/")
    workspace_id = get_workspace_id(base_url)
    print(f"Workspace : {workspace_id}")

    source_id = ensure_source(base_url, workspace_id, args)
    print(f"Source MySQL : {source_id}")

    destination_id = ensure_destination(base_url, workspace_id, args)
    print(f"Destination PostgreSQL : {destination_id}")

    catalog = discover_streams(base_url, source_id)
    connection_id = ensure_connection(base_url, source_id, destination_id, catalog)
    print(f"Connexion rh_source -> rh_target : {connection_id}")
    print("Configuration terminee. Declencher une synchronisation manuelle depuis "
          "l'UI ou via POST /api/v1/connections/sync pour le premier chargement.")


if __name__ == "__main__":
    main()
