# Airbyte — installation et configuration (procedure distincte)

Airbyte figure dans la clause du cahier des charges reservee aux « outils necessitant
une installation particuliere » : sa pile complete (serveur, worker, webapp, Temporal,
MinIO, base interne) n'est pas incluse dans le `docker-compose.yml` racine du projet
pour ne pas alourdir le demarrage des services principaux (MySQL, PostgreSQL, API).
Elle s'installe et se configure a part, avec sa propre procedure reproductible
decrite ici.

## 1. Installation (abctl, methode officielle actuelle)

```bash
# macOS / Linux / WSL2, necessite Docker Desktop demarre
curl -LsfS https://get.airbyte.com | bash -
abctl local install
```

Sur Windows **hors WSL2** (ex. Git Bash/PowerShell natif), le script `get.airbyte.com`
refuse l'installation ("Unsupported, use WSL2"). `abctl` fournit neanmoins un binaire
Windows natif sur ses releases GitHub ; installation manuelle :

```powershell
$dest = "$HOME\scoop\apps\abctl"   # ou tout autre dossier
New-Item -ItemType Directory -Force -Path $dest | Out-Null
Invoke-WebRequest -Uri "https://github.com/airbytehq/abctl/releases/latest/download/abctl-v0.30.4-windows-amd64.zip" -OutFile "$dest\abctl.zip"
Expand-Archive -Path "$dest\abctl.zip" -DestinationPath $dest -Force
& "$dest\abctl-v0.30.4-windows-amd64\abctl.exe" local install
```

(Adapter le numero de version si une plus recente est sortie ; verifier sur
https://github.com/airbytehq/abctl/releases.)

Ressources recommandees par Airbyte : 4 CPU / 8 Go RAM minimum pour la pile abctl
(cluster Kubernetes local via `kind`), en plus de ce que consomment deja MySQL,
PostgreSQL et l'API. Sur un poste contraint, installer Airbyte sur une machine/VM
dediee plutot qu'a cote du reste de la pile. L'installation complete (telechargement
des images + Helm charts) prend typiquement 30-40 minutes la premiere fois.

Une fois installe :

```bash
abctl local credentials   # recupere le mot de passe admin genere
```

L'interface est exposee sur `http://localhost:8000`. `abctl local credentials`
affiche egalement un `Client-Id`/`Client-Secret` : c'est ce couple (pas le mot de
passe UI) qui sert a authentifier les appels API du script de la section 3.

Sur un hyperviseur Docker Desktop (Windows/macOS), le cluster `kind` d'Airbyte peut
atteindre MySQL/PostgreSQL exposes sur l'hote via le nom special `host.docker.internal`
(verifie : les pods connecteurs resolvent et joignent cette adresse, meme si le port
mappe en local, 3306/5432, est utilise). Pas besoin de mettre les conteneurs du
projet sur le meme reseau Docker que le cluster `kind`.

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
   - Frequence : **manuelle** dans cette version d'Airbyte (voir note section 3) ;
     declencher `Sync now` pour chaque test

## 3. Configuration reproductible (script)

`configure_airbyte.py` automatise les memes etapes via l'**API publique**
d'Airbyte (`/api/public/v1/...`), pour que la connexion puisse etre recreee sans
repasser par l'UI :

```bash
pip install -r requirements.txt
python configure_airbyte.py \
  --airbyte-url http://localhost:8000 \
  --mysql-host <hote_mysql_atteignable_depuis_airbyte> \
  --postgres-host <hote_postgres_atteignable_depuis_airbyte> \
  --client-id <client_id_abctl> \
  --client-secret <client_secret_abctl>
```

`--client-id`/`--client-secret` sont affiches par `abctl local credentials`. **Note
importante** : l'ancienne API Config (`/api/v1/...`, utilisee par les versions
anciennes d'Airbyte OSS et par la documentation historique) est desormais reservee
a l'usage interne du serveur web et repond `403 Forbidden` a tout jeton
d'application — meme valide. Le script utilise donc l'API publique
(`/api/public/v1/...`), qui a un schema different (ex. `configuration.sourceType`
au lieu de `sourceDefinitionId`, pas d'etape separee de `discover_schema`).

Deux limitations de cette API publique a connaitre :
- **Pas de planification "toutes les N minutes"** : seuls `manual` et `cron` sont
  acceptes, et un cron ne peut pas s'executer plus d'une fois par heure. Le script
  cree donc la connexion en `schedule: manual` ; declencher les syncs via l'UI ou
  `POST /api/public/v1/jobs {"connectionId": "...", "jobType": "sync"}`.
- **La creation de la connexion declenche une vraie decouverte de schema** contre
  MySQL (demarrage a froid du pod connecteur sur le cluster `kind` local :
  jusqu'a 2-3 minutes la premiere fois), ce qui depasse souvent le delai de
  l'ingress nginx local et renvoie un `502 Bad Gateway` **au client** alors que la
  connexion est bel et bien creee cote serveur. Le script detecte ce cas et
  retente une recherche par nom pendant 5 minutes avant d'abandonner ; si on le
  relance malgre un 502 affiche, il retrouvera la connexion deja creee (idempotent).

Le script est idempotent : il recherche d'abord une source/destination/connexion
existante du meme nom avant d'en creer une nouvelle.

## 4. Test de bout en bout (sync + fraicheur)

Scenario exact dans `../tests/scenario_bout_en_bout.md`, resume :

1. Lancer une synchronisation manuelle (`Connections > rh_source→rh_target > Sync now`
   dans l'UI, ou `POST /api/public/v1/jobs` avec `{"connectionId": "...", "jobType": "sync"}`).
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
