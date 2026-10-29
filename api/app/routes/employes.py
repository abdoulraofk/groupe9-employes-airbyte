from flask import Blueprint, abort, jsonify, request

from ..db import get_cursor

bp = Blueprint("employes", __name__)

MAX_PER_PAGE = 100

BASE_SELECT = """
    SELECT e.matricule, e.nom, e.prenom, e.email,
           e.date_embauche, e.actif, e.updated_at,
           s.code AS service_code, s.nom AS service_nom,
           f.code AS fonction_code, f.libelle AS fonction_libelle
    FROM employes e
    JOIN services s  ON s.id = e.service_id
    JOIN fonctions f ON f.id = e.fonction_id
"""


def _pagination_params():
    try:
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 20))
    except ValueError:
        abort(400, description="page et per_page doivent etre des entiers")
    if page < 1:
        abort(400, description="page doit etre >= 1")
    if per_page < 1 or per_page > MAX_PER_PAGE:
        abort(400, description=f"per_page doit etre compris entre 1 et {MAX_PER_PAGE}")
    return page, per_page


@bp.get("/employes")
def list_employes():
    """Liste en lecture seule des employes, avec filtres et pagination.

    Filtres : matricule (prefixe), service (code), fonction (code),
    nom (sous-chaine, insensible a la casse), actif (0/1).
    """
    page, per_page = _pagination_params()

    where = []
    params = []

    matricule = request.args.get("matricule")
    if matricule:
        where.append("e.matricule ILIKE %s")
        params.append(f"{matricule}%")

    service = request.args.get("service")
    if service:
        where.append("s.code = %s")
        params.append(service.upper())

    fonction = request.args.get("fonction")
    if fonction:
        where.append("f.code = %s")
        params.append(fonction.upper())

    nom = request.args.get("nom")
    if nom:
        where.append("(e.nom ILIKE %s OR e.prenom ILIKE %s)")
        params.extend([f"%{nom}%", f"%{nom}%"])

    actif = request.args.get("actif")
    if actif is not None:
        if actif not in ("0", "1"):
            abort(400, description="actif doit valoir 0 ou 1")
        where.append("e.actif = %s")
        params.append(actif == "1")

    where_sql = f"WHERE {' AND '.join(where)}" if where else ""

    with get_cursor() as cur:
        cur.execute(f"SELECT COUNT(*) AS total FROM employes e "
                     f"JOIN services s ON s.id = e.service_id "
                     f"JOIN fonctions f ON f.id = e.fonction_id {where_sql}", params)
        total = cur.fetchone()["total"]

        cur.execute(
            f"{BASE_SELECT} {where_sql} ORDER BY e.matricule "
            f"LIMIT %s OFFSET %s",
            params + [per_page, (page - 1) * per_page],
        )
        rows = cur.fetchall()

    total_pages = (total + per_page - 1) // per_page if total else 0
    return jsonify(
        data=rows,
        page=page,
        per_page=per_page,
        total=total,
        total_pages=total_pages,
    )


@bp.get("/employes/<matricule>")
def get_employe(matricule):
    with get_cursor() as cur:
        cur.execute(f"{BASE_SELECT} WHERE e.matricule = %s", [matricule])
        row = cur.fetchone()
    if row is None:
        abort(404)
    return jsonify(row)
