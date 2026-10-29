# Airbyte — installation et configuration (procedure distincte)

Airbyte figure dans la clause du cahier des charges reservee aux « outils necessitant
une installation particuliere » : sa pile complete (serveur, worker, webapp, Temporal,
MinIO, base interne) n'est pas incluse dans le `docker-compose.yml` racine du projet
pour ne pas alourdir le demarrage des services principaux (MySQL, PostgreSQL, API).
Elle s'installe et se configure a part, avec sa propre procedure reproductible
decrite ici.

## 1. Installation (abctl, methode officielle actuelle)

```bash
# Windows / macOS / Linux, necessite Docker Desktop demarre
curl -LsfS https://get.airbyte.com | bash -
abctl local install
```

Ressources recommandees par Airbyte : 4 CPU / 8 Go RAM minimum pour la pile abctl
(cluster Kubernetes local via `kind`), en plus de ce que consomment deja MySQL,
PostgreSQL et l'API. Sur un poste contraint, installer Airbyte sur une machine/VM
dediee plutot qu'a cote du reste de la pile.

Une fois installe :

```bash
abctl local credentials   # recupere le mot de passe admin genere
```

L'interface est exposee sur `http://localhost:8000` (identifiant `airbyte`, mot de
passe affiche par la commande ci-dessus).

## 2. Configuration manuelle (UI)

1. **Source** — MySQL
   - Host : adresse du conteneur/hote `mysql` du projet (sur le meme reseau Docker,
     ou IP/port exposes selon l'installation d'Airbyte)
   - Port : `3306`, Database : `rh_source`
   - User : `airbyte_reader` / Password : `airbyte_reader_pwd` (cf. `db/mysql/init/01_schema.sql`)
   - Replication method : `Standard`
2. **Destination** — PostgreSQL
   - Host/port/database du conteneur `postgres` du projet, Database : `rh_target`
   - User : `postgres` (ou un role dedie en ecriture), Schema par defaut : `public`
3. **Connexion** `rh_source -> rh_target`
   - Streams `employes`, `services`, `fonctions`
   - Sync mode : **Incremental | Deduped** (type/dedup Airbyte "Destination V2")
   - Cursor field : `updated_at` (present sur les trois tables, cf. schema MySQL)
   - Primary key : `matricule` (employes), `id` (services, fonctions)
   - Destination namespace : `Mirror source structure` desactive, namespace fixe
     a `public` pour que l'API lise `public.employes`, `public.services`,
     `public.fonctions`
   - Frequence : toutes les 5 minutes pour la demonstration (ajustable)

## 3. Configuration reproductible (script)

`configure_airbyte.py` automatise les memes etapes via l'API Config d'Airbyte
(`/api/v1/...`), pour que la connexion puisse etre recreee sans repasser par l'UI :

```bash
pip install -r requirements.txt
python configure_airbyte.py \
  --airbyte-url http://localhost:8000 \
  --mysql-host <hote_mysql_atteignable_depuis_airbyte> \
  --postgres-host <hote_postgres_atteignable_depuis_airbyte>
```

Le script est idempotent au sens ou il recherche d'abord une source/destination/
connexion existante du meme nom avant d'en creer une nouvelle. Les chemins d'API
exacts (`/api/v1/sources/create`, etc.) correspondent a l'API Config stable
d'Airbyte OSS ; verifier `http://localhost:8000/api/v1/openapi.json` si la version
installee a change ces routes.

## 4. Test de bout en bout (sync + fraicheur)

Scenario exact dans `../tests/scenario_bout_en_bout.md`, resume :

1. Lancer une synchronisation manuelle (`Connections > rh_source→rh_target > Sync now`
   dans l'UI, ou `POST /api/v1/connections/sync` avec le `connectionId`).
2. Verifier via `GET /api/v1/employes/EMP0001` (API du projet) que la donnee est
   presente cote PostgreSQL.
3. Modifier une ligne source (`UPDATE rh_source.employes SET nom = ... WHERE matricule = 'EMP0001'`)
   directement dans MySQL.
4. Avant la prochaine synchronisation, interroger l'API : l'ancienne valeur doit
   encore etre renvoyee (preuve de la latence de synchronisation documentee dans
   `GET /api/v1/meta/freshness`).
5. Declencher la synchronisation, reinterroger l'API : la nouvelle valeur doit
   apparaitre, et `age_seconds` de `/api/v1/meta/freshness` doit retomber pres de 0.

## 5. Repli sans Airbyte

Si Airbyte n'est pas disponible (poste limite en ressources, demonstration hors
ligne), `../scripts/sync_mysql_to_postgres.py` (service Docker `sync-fallback`,
profil `dev-sync`) reproduit le meme contrat de donnees (tables PostgreSQL avec
colonnes `_airbyte_raw_id` / `_airbyte_extracted_at` / `_airbyte_meta`) et permet
de dérouler le meme scenario de test. **Ajout, non demande/fourni par l'enonce** :
ce repli n'est pas une exigence du sujet, qui demande explicitement Airbyte ; il a
ete ajoute pour que le projet reste demontrable meme si la pile Airbyte ne peut pas
tourner dans l'environnement de demonstration.
