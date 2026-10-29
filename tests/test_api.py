"""
Tests de l'API de consultation des employes (resultats attendus, exercice 15).

Prerequis : la pile docker-compose principale est demarree et synchronisee au
moins une fois (Airbyte ou `docker compose --profile dev-sync up -d sync-fallback`).

    BASE_URL=http://localhost:5000 pytest -v
"""
import os

import pytest
import requests

BASE_URL = os.environ.get("BASE_URL", "http://localhost:5000")
API = f"{BASE_URL}/api/v1"


def test_health():
    r = requests.get(f"{API}/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_liste_employes_defaut():
    r = requests.get(f"{API}/employes")
    assert r.status_code == 200
    body = r.json()
    assert body["page"] == 1
    assert body["per_page"] == 20
    assert body["total"] >= 30
    assert len(body["data"]) <= 20


def test_pagination():
    r1 = requests.get(f"{API}/employes", params={"page": 1, "per_page": 5})
    r2 = requests.get(f"{API}/employes", params={"page": 2, "per_page": 5})
    assert r1.status_code == r2.status_code == 200
    data1 = r1.json()["data"]
    data2 = r2.json()["data"]
    assert len(data1) == 5
    ids1 = {e["matricule"] for e in data1}
    ids2 = {e["matricule"] for e in data2}
    assert ids1.isdisjoint(ids2)


def test_pagination_bornes_invalides():
    assert requests.get(f"{API}/employes", params={"per_page": 0}).status_code == 400
    assert requests.get(f"{API}/employes", params={"per_page": 1000}).status_code == 400
    assert requests.get(f"{API}/employes", params={"page": 0}).status_code == 400


def test_recherche_par_matricule():
    r = requests.get(f"{API}/employes", params={"matricule": "EMP0001"})
    assert r.status_code == 200
    data = r.json()["data"]
    assert len(data) == 1
    assert data[0]["matricule"] == "EMP0001"

    r2 = requests.get(f"{API}/employes/EMP0001")
    assert r2.status_code == 200
    assert r2.json()["nom"] == "KABORE"


def test_employe_inexistant_404():
    r = requests.get(f"{API}/employes/EMP9999")
    assert r.status_code == 404


def test_recherche_par_service():
    r = requests.get(f"{API}/employes", params={"service": "dsi"})
    assert r.status_code == 200
    data = r.json()["data"]
    assert data
    assert all(e["service_code"] == "DSI" for e in data)


def test_recherche_par_fonction():
    r = requests.get(f"{API}/employes", params={"fonction": "dev"})
    assert r.status_code == 200
    data = r.json()["data"]
    assert data
    assert all(e["fonction_code"] == "DEV" for e in data)


def test_combinaison_filtres_et_nom():
    r = requests.get(f"{API}/employes", params={"service": "fin", "nom": "sanou"})
    assert r.status_code == 200
    data = r.json()["data"]
    assert len(data) == 1
    assert data[0]["nom"] == "SANOU"


def test_filtre_actif():
    r = requests.get(f"{API}/employes", params={"actif": "0"})
    assert r.status_code == 200
    data = r.json()["data"]
    assert data
    assert all(e["actif"] is False for e in data)


def test_lecture_seule_pas_de_mutation():
    """L'API n'expose aucune route d'ecriture (exercice 15 : API en lecture seule)."""
    for method in (requests.post, requests.put, requests.delete, requests.patch):
        r = method(f"{API}/employes/EMP0001")
        assert r.status_code in (404, 405)


def test_services_et_fonctions():
    r = requests.get(f"{API}/services")
    assert r.status_code == 200
    assert len(r.json()["data"]) == 5

    r = requests.get(f"{API}/fonctions")
    assert r.status_code == 200
    assert len(r.json()["data"]) == 6


def test_freshness_expose_un_age():
    r = requests.get(f"{API}/meta/freshness")
    assert r.status_code == 200
    body = r.json()
    for table in ("employes", "services", "fonctions"):
        assert table in body["tables"]
        assert body["tables"][table]["last_sync_at"] is not None
