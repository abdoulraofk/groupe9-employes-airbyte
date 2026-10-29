from datetime import datetime, timezone

from flask import Blueprint, jsonify

from ..db import get_cursor

bp = Blueprint("meta", __name__)


@bp.get("/health")
def health():
    with get_cursor() as cur:
        cur.execute("SELECT 1")
        cur.fetchone()
    return jsonify(status="ok")


@bp.get("/services")
def list_services():
    with get_cursor() as cur:
        cur.execute("SELECT id, code, nom, updated_at FROM services ORDER BY code")
        rows = cur.fetchall()
    return jsonify(data=rows)


@bp.get("/fonctions")
def list_fonctions():
    with get_cursor() as cur:
        cur.execute("SELECT id, code, libelle, updated_at FROM fonctions ORDER BY code")
        rows = cur.fetchall()
    return jsonify(data=rows)


@bp.get("/meta/freshness")
def freshness():
    """Indicateur de fraicheur : derniere extraction Airbyte connue par table.

    Cette API lit PostgreSQL, qui n'est a jour qu'au rythme des synchronisations
    Airbyte (cf. README : limites de fraicheur des donnees). Cet endpoint rend
    cette latence explicite plutot que de la laisser implicite.
    """
    tables = ["employes", "services", "fonctions"]
    result = {}
    now = datetime.now(timezone.utc)
    with get_cursor() as cur:
        for table in tables:
            cur.execute(f'SELECT MAX("_airbyte_extracted_at") AS last_sync FROM {table}')
            row = cur.fetchone()
            last_sync = row["last_sync"]
            age_seconds = (now - last_sync).total_seconds() if last_sync else None
            result[table] = {
                "last_sync_at": last_sync.isoformat() if last_sync else None,
                "age_seconds": age_seconds,
            }
    return jsonify(checked_at=now.isoformat(), tables=result)
