# Scenario de bout en bout (exigence du cahier des charges : "un test de bout en
# bout de la chaine principale du projet")

Chaine testee : MySQL (source) -> Airbyte (replication) -> PostgreSQL (cible) ->
API Flask (consultation). Reprend aussi les points 5 et 6 de l'exercice 15 :
recherche par matricule/service/fonction, et apparition d'une modification source
dans l'API apres synchronisation.

## Prerequis

```bash
docker compose up -d mysql postgres api
# Airbyte configure et synchronise une premiere fois (voir airbyte/README.md),
# ou, a defaut, le repli de developpement :
docker compose --profile dev-sync up -d sync-fallback
```

## Etape 1 — Donnees presentes apres synchronisation initiale

```bash
curl -s http://localhost:5000/api/v1/employes/EMP0001 | jq .
# Attendu : nom = "KABORE", service_code = "DSI", fonction_code = "DEV"
```

## Etape 2 — Recherche par matricule, service, fonction (point 5 de l'exercice 15)

```bash
curl -s "http://localhost:5000/api/v1/employes?matricule=EMP00"      | jq '.total'
curl -s "http://localhost:5000/api/v1/employes?service=FIN"          | jq '.data | length'
curl -s "http://localhost:5000/api/v1/employes?fonction=COMM"        | jq '.data | length'
curl -s "http://localhost:5000/api/v1/employes?service=FIN&nom=sanou" | jq .
```

Resultats attendus : `total` pour le prefixe `EMP00` = 30 (tous les matricules
commencent par ce prefixe dans le jeu de donnees de demonstration) ; `FIN` = 5
employes ; `COMM` = 3 employes ; la combinaison `service=FIN&nom=sanou` retourne
exactement SANOU Alizeta.

## Etape 3 — Modification cote source (point 6 de l'exercice 15)

```bash
docker exec -it rh_mysql_source mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -e \
  "UPDATE rh_source.employes SET nom='KABORE-TRAORE' WHERE matricule='EMP0001';"
```

Interroger immediatement l'API : la valeur ne doit **pas encore** avoir change
(preuve de la latence de synchronisation) :

```bash
curl -s http://localhost:5000/api/v1/employes/EMP0001 | jq '.nom'
# -> encore "KABORE" tant que la synchronisation n'a pas tourne
curl -s http://localhost:5000/api/v1/meta/freshness | jq '.tables.employes'
# -> age_seconds croissant
```

## Etape 4 — Declenchement de la synchronisation

- Airbyte : `Connections > rh_source_to_rh_target > Sync now` dans l'UI, ou
  `POST {airbyte_url}/api/v1/connections/sync` avec le `connectionId`.
- Repli de developpement : `docker compose --profile dev-sync restart sync-fallback`
  (ou attendre le prochain cycle, intervalle 15 s par defaut).

## Etape 5 — Verification de la propagation

```bash
curl -s http://localhost:5000/api/v1/employes/EMP0001 | jq '.nom'
# -> "KABORE-TRAORE"
curl -s http://localhost:5000/api/v1/meta/freshness | jq '.tables.employes.age_seconds'
# -> proche de 0
```

## Resultat attendu (synthese)

| Etape | Attendu |
|---|---|
| Recherche par matricule/service/fonction | Filtres combinables, resultats corrects, pagination respectee |
| Avant synchronisation | API renvoie encore l'ancienne valeur ; `age_seconds` eleve |
| Apres synchronisation | API renvoie la nouvelle valeur ; `age_seconds` proche de 0 |
| Operations d'ecriture (POST/PUT/DELETE) | Refusees (404/405) : l'API est strictement en lecture seule |

Script automatisable equivalent (utilise le repli de synchronisation) :
`tests/test_sync_scenario.py`.
