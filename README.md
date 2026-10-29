# Groupe 9 (SI) — API REST de consultation des employes avec Airbyte

Projet "Developpement a base de composant et services web" (2026), these n° 15 :
**API REST de consultation des employes**, technologies imposees **Airbyte** et
**Flask/Django**.

Membres : NANA Gerard, KUELA Abdoul Raof, KERE Wend-panga Georges Fabrice,
KIEKIETA Mohamed, SAWADOGO Ibrahim — filiere Securite informatique (SI), Groupe 9.

## 1. Objectif et perimetre (exercice 15)

1. API de consultation des employes dont les donnees sont repliquees depuis MySQL
   vers PostgreSQL.
2. Tables `employes`, `services`, `fonctions`.
3. Airbyte replique les tables necessaires (MySQL -> PostgreSQL).
4. API Flask **en lecture seule**, avec filtres et pagination.
5. Recherche par matricule, service et fonction.
6. Verification qu'une modification cote source apparait dans l'API apres
   synchronisation.
7. Documentation des limites de fraicheur des donnees.

## 2. Architecture

```
            (ecriture RH, hors perimetre)
                      |
                      v
   +-------------+         +-----------+         +----------------+        +--------+
   |   MySQL     |  Airbyte |PostgreSQL |  SQL    |   API Flask    |  HTTP  | client |
   | rh_source   | -------> | rh_target | <------ | (lecture seule)| <----- | Postman|
   | (source RH) | replic.  | (entrepot |         | /api/v1/...    |        | curl...|
   +-------------+          | consult.) |         +----------------+        +--------+
                             +-----------+
```

- **MySQL** (`rh_source`) : base source "metier RH", seule source ecrivable.
  Tables `services`, `fonctions`, `employes` avec une colonne `updated_at`
  (cursor Airbyte) sur chacune.
- **Airbyte** : connexion `rh_source -> rh_target` en mode *Incremental | Deduped*
  (cursor `updated_at`, cle primaire `matricule`/`id`), destination namespace fixe
  a `public`. Installation et configuration documentees separement dans
  [`airbyte/README.md`](airbyte/README.md) (clause "outils necessitant une
  installation particuliere" du cahier des charges).
- **PostgreSQL** (`rh_target`) : entrepot de consultation alimente uniquement par
  Airbyte. Tables finales = memes noms/colonnes que la source, plus les colonnes
  techniques Airbyte (`_airbyte_raw_id`, `_airbyte_extracted_at`, `_airbyte_meta`).
- **API Flask** (`api/`) : lecture seule sur PostgreSQL via un role dedie
  `api_reader` (GRANT SELECT uniquement). Aucune route d'ecriture n'existe.

## 3. Prerequis

- Docker 24+ et Docker Compose v2 (`docker compose version`)
- Pour la configuration Airbyte : voir [`airbyte/README.md`](airbyte/README.md)
  (installation separee, ressources recommandees 4 CPU / 8 Go RAM)
- Optionnel (developpement local hors conteneur) : Python 3.12

## 4. Installation et demarrage

```bash
git clone <url-du-depot> groupe9-employes-airbyte
cd groupe9-employes-airbyte
cp .env.example .env

# Services principaux : source MySQL, cible PostgreSQL, API
docker compose up -d --build mysql postgres api

# Verifier que l'API repond (avant toute synchronisation, PostgreSQL est vide
# sauf via le repli de developpement ci-dessous)
curl http://localhost:5000/api/v1/health
```

MySQL expose `localhost:3306` (RH source), PostgreSQL `localhost:5432` (cible),
l'API `localhost:5000`.

### 4.1 Peupler la cible

Deux options, documentees pour rester reproductibles sur une machine neuve :

- **Airbyte (solution officielle du theme)** : suivre
  [`airbyte/README.md`](airbyte/README.md) (installation `abctl`, puis
  `python airbyte/configure_airbyte.py ...` ou configuration manuelle via l'UI).
- **Repli de developpement**, sans la pile Airbyte complete :
  ```bash
  docker compose --profile dev-sync up -d sync-fallback
  ```
  Ce service (`scripts/sync_mysql_to_postgres.py`) recopie MySQL vers PostgreSQL
  toutes les 15 secondes, en reproduisant exactement le schema qu'Airbyte
  produirait (memes colonnes techniques). **Ajout, non demande/fourni par
  l'enonce** : ne remplace pas Airbyte dans la livraison finale, sert a demontrer
  et tester la chaine quand la pile Airbyte n'est pas disponible dans
  l'environnement de demonstration.

## 5. API — reference

Contrat complet : [`api/openapi.yaml`](api/openapi.yaml) (OpenAPI 3.0).

Base : `http://localhost:5000/api/v1`

| Methode | Route | Description |
|---|---|---|
| GET | `/health` | Etat de l'API et de la connexion PostgreSQL |
| GET | `/employes` | Liste paginee, filtres `matricule`, `service`, `fonction`, `nom`, `actif` |
| GET | `/employes/<matricule>` | Fiche d'un employe (404 si absent) |
| GET | `/services` | Liste des services |
| GET | `/fonctions` | Liste des fonctions |
| GET | `/meta/freshness` | Date de derniere synchronisation connue et age (secondes) par table |

Pagination : `page` (defaut 1), `per_page` (defaut 20, max 100). Reponse :
`{ "data": [...], "page": 1, "per_page": 20, "total": 30, "total_pages": 2 }`.

Exemples :

```bash
curl "http://localhost:5000/api/v1/employes?service=DSI&page=1&per_page=10"
curl "http://localhost:5000/api/v1/employes?fonction=DEV&nom=kabore"
curl "http://localhost:5000/api/v1/employes/EMP0001"
curl "http://localhost:5000/api/v1/meta/freshness"
```

L'API n'expose **aucune** route de creation/modification/suppression
(exigence du theme 15 : "API ... en lecture seule").

## 6. Tests et resultats attendus

- `tests/test_api.py` (pytest) : sante, pagination, filtres matricule/service/
  fonction/nom/actif, 404, absence de routes d'ecriture, freshness. Voir le
  fichier pour les valeurs attendues (jeu de donnees de demonstration :
  30 employes, 5 services, 6 fonctions, cf. `db/mysql/init/02_seed.sql`).
- `tests/scenario_bout_en_bout.md` : scenario manuel complet MySQL -> Airbyte ->
  PostgreSQL -> API, avec resultats attendus a chaque etape (test obligatoire du
  cahier des charges : "un test de bout en bout de la chaine principale").
- `tests/test_sync_scenario.py` : version automatisee du meme scenario, utilisable
  avec le repli de synchronisation.

```bash
pip install -r tests/requirements.txt
BASE_URL=http://localhost:5000 pytest tests/test_api.py -v
BASE_URL=http://localhost:5000 python tests/test_sync_scenario.py
```

## 7. Limites de fraicheur des donnees (point 7 de l'exercice 15)

- L'API lit exclusivement PostgreSQL : elle ne voit jamais MySQL en direct. Toute
  ecriture dans `rh_source` n'apparait dans l'API qu'**apres** le prochain cycle
  de synchronisation Airbyte (frequence configuree : 5 minutes en demonstration,
  ou declenchement manuel).
- `GET /api/v1/meta/freshness` rend cette latence explicite : il renvoie, par
  table, l'horodatage de derniere extraction Airbyte (`_airbyte_extracted_at`) et
  l'age en secondes depuis cet instant. Un `age_seconds` eleve signale des
  donnees potentiellement perimees.
- En mode *Incremental | Deduped* avec cursor `updated_at`, une suppression
  physique cote MySQL n'est **pas** propagee automatiquement vers PostgreSQL
  (Airbyte ne detecte que les lignes creees/modifiees via le cursor, pas les
  suppressions, sauf activation d'une detection dediee). A documenter comme
  limite connue si une desactivation de compte (`actif = 0`) est preferee a une
  suppression physique — c'est le choix fait ici (`employes.actif`).
- Pendant une synchronisation en cours, les lectures API restent coherentes
  (PostgreSQL applique les upserts par transaction), mais peuvent melanger des
  lignes d'avant et d'apres synchronisation entre deux requetes successives.

## 8. Structure du depot

```
.
├── README.md
├── docker-compose.yml            # mysql, postgres, api, sync-fallback (profil dev-sync)
├── .env.example
├── db/
│   ├── mysql/init/                # schema + donnees de demonstration (source)
│   └── postgres/init/             # role applicatif en lecture seule (cible)
├── api/                            # API Flask (lecture seule)
├── airbyte/                        # installation/configuration Airbyte (procedure distincte)
├── scripts/                        # repli de synchronisation pour le developpement/tests
├── tests/                          # pytest + scenario de bout en bout
└── presentation/                   # support PowerPoint
```

## 9. Choix techniques notables (ajouts non demandes par l'enonce)

- Compte MySQL dedie `airbyte_reader` en lecture seule pour l'extraction, et role
  PostgreSQL `api_reader` en lecture seule pour l'API (principe du moindre
  privilege, non impose par l'enonce mais cause directe pour que l'API soit
  reellement non modifiante au niveau base, pas seulement au niveau code).
- Colonne `actif` sur `employes` plutot qu'une suppression physique, pour que la
  strategie de desactivation soit explicite et testable (cf. section 7).
- `scripts/sync_mysql_to_postgres.py` et le profil `dev-sync` : repli de
  demonstration/test en l'absence d'un environnement Airbyte disponible (voir
  `airbyte/README.md` section 5).
