# Script de démo minuté — Groupe 9, Thème 15 (API employés + Airbyte)

Durée cible : 9 minutes de démo + 1 minute de marge. À adapter au temps réellement
alloué par l'enseignant. Basé sur `tests/scenario_bout_en_bout.md` (déjà rédigé et
testé) : ne pas improviser les commandes, les copier depuis ce fichier ou depuis
`tests/scenario_bout_en_bout.md`.

## Préparation (avant le passage, pas devant le jury)

- [ ] `docker compose up -d mysql postgres api` lancé et stable depuis au moins 2 min
      (healthchecks verts : `docker compose ps`).
- [ ] Sync déjà faite une première fois (Airbyte ou `--profile dev-sync up -d sync-fallback`)
      pour que `/employes` réponde déjà avant la démo — évite de perdre du temps live.
- [ ] 3 terminaux ouverts côte à côte, police large (18-20pt mini pour la salle) :
      - **Terminal A** : client HTTP (`curl ... | jq`)
      - **Terminal B** : accès direct MySQL (`docker exec -it rh_mysql_source mysql ...`)
      - **Terminal C** : `watch` sur la fraîcheur (voir étape 5)
- [ ] Collection Postman importée et prête (alternative à `curl` pour le terminal A si
      préférée — plus lisible à l'écran, cf. `api/openapi.yaml` pour reconstruire les
      requêtes si pas de collection `.json` exportée).
- [ ] `jq` installé et testé (sinon les sorties JSON sont illisibles en salle).
- [ ] Plan B prêt : captures PNG de `captures_rapport_png.zip` (dossier parent) et/ou
      une courte vidéo de la chaîne complète, à l'écran immédiatement si Docker/Airbyte
      ne répond pas en salle.
- [ ] Vérifier l'état des données : si EMP0001 a déjà été modifié lors d'un essai
      précédent (nom "KABORE-TRAORE"), remettre `nom='KABORE'` avant de démarrer, sinon
      l'étape 4 ne montre plus rien de nouveau.

## Minutage

### 0:00 – 0:45 — Contexte (1 slide, à l'oral)

Dire, sans lire le slide : "API de consultation des employés. Contrainte du thème :
la base de saisie (MySQL) ne doit jamais être modifiable par l'API. On réplique vers
PostgreSQL avec Airbyte, et l'API ne lit que PostgreSQL." Montrer le schéma
d'architecture (slide existant du pptx).

### 0:45 – 1:30 — Preuve que la stack tourne (Terminal A)

```bash
curl -s http://localhost:5000/api/v1/health | jq .
```

Dire : "API up, connectée à PostgreSQL. La réplication a déjà tourné avant la démo
pour ne pas vous faire attendre les 15 secondes du repli maintenant."

### 1:30 – 3:00 — Recherche, filtres, pagination (Terminal A ou Postman)

Reprendre `tests/scenario_bout_en_bout.md` étape 2 :

```bash
curl -s "http://localhost:5000/api/v1/employes?service=FIN" | jq '.data | length'
curl -s "http://localhost:5000/api/v1/employes?fonction=COMM" | jq '.data | length'
curl -s "http://localhost:5000/api/v1/employes?service=FIN&nom=sanou" | jq .
curl -s "http://localhost:5000/api/v1/employes?page=2&per_page=5" | jq '{page,total,total_pages}'
```

Dire en une phrase ce que chaque résultat prouve (filtre combiné, pagination
cohérente). Ne pas lire le JSON ligne par ligne — le jury le lit à l'écran.

### 3:00 – 3:45 — Lecture seule prouvée (Terminal A)

```bash
for m in POST PUT PATCH DELETE; do
  printf "%-6s <- HTTP %s\n" $m $(curl -s -o /dev/null -w "%{http_code}" -X $m http://localhost:5000/api/v1/employes/EMP0001)
done
```

Dire : "Refusé au niveau HTTP. Et même en se connectant directement à PostgreSQL
avec le compte de l'API — montrer le rôle `api_reader`, droit SELECT uniquement —
une écriture est refusée au niveau base, pas seulement au niveau code." (Optionnel
si le temps presse : sauter la preuve SQL directe, garder juste les 4 curl.)

### 3:45 – 7:00 — Le clou : latence et fraîcheur (Terminal A + B + C)

C'est le point le plus différenciant du projet (API jamais en lecture directe sur
MySQL) : lui donner le plus de temps.

1. **Terminal A** — valeur actuelle :
   ```bash
   curl -s http://localhost:5000/api/v1/employes/EMP0001 | jq '.nom'
   # -> "KABORE"
   ```
2. **Terminal C** — lancer *avant* la modification, pour que la montée de
   `age_seconds` soit visible en continu pendant qu'on parle :
   ```bash
   watch -n 1 'curl -s http://localhost:5000/api/v1/meta/freshness | jq ".tables.employes"'
   ```
3. **Terminal B** — modification côté source :
   ```bash
   docker exec -it rh_mysql_source mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -e \
     "UPDATE rh_source.employes SET nom='KABORE-TRAORE' WHERE matricule='EMP0001';"
   ```
4. **Terminal A** — immédiatement après, sans attendre :
   ```bash
   curl -s http://localhost:5000/api/v1/employes/EMP0001 | jq '.nom'
   # -> encore "KABORE"
   ```
   Dire : "La modification existe déjà en base source. L'API ne le sait pas encore —
   c'est voulu, pas un bug." Pendant ce temps, **Terminal C** montre `age_seconds`
   qui monte : le pointer du doigt.
5. Déclencher la synchronisation :
   - Repli dev : `docker compose --profile dev-sync restart sync-fallback`
     (ou attendre le cycle 15 s si déjà lancé en continu)
   - Airbyte réel : `Sync now` dans l'UI (`http://localhost:8000`)
6. **Terminal A** — reconfirmer :
   ```bash
   curl -s http://localhost:5000/api/v1/employes/EMP0001 | jq '.nom'
   # -> "KABORE-TRAORE"
   ```
   **Terminal C** retombe à `age_seconds` proche de 0 — le montrer explicitement.

### 7:00 – 8:00 — Tests automatisés (Terminal A)

```bash
BASE_URL=http://localhost:5000 pytest tests/test_api.py -v
```

Dire : "13 tests, couvrent filtres, pagination, 404, lecture seule, fraîcheur —
mêmes garanties que ce qu'on vient de montrer en direct, rejouables en CI."

### 8:00 – 8:30 — Limite connue (à l'oral, pas de commande)

Dire : "Limite documentée : le mode Incremental/Deduped d'Airbyte ne propage pas les
suppressions physiques côté source. C'est pourquoi on désactive (`actif=0`) plutôt
que supprimer — visible via `?actif=0`." (Donne une bonne impression de maturité
technique sans rien démontrer de plus en live.)

### 8:30 – 9:00 — Conclusion (1 slide)

Reprendre la synthèse du rapport (tableau §9) : démarrage, chargement, recherche,
avant/après synchro, écritures refusées — tout vérifié.

## Répartition possible entre les 5 membres

- Un membre pilote le Terminal A (parle en même temps qu'il tape — s'entraîner à la
  synchronisation parole/clavier, ne pas taper en silence).
- Un deuxième pilote B et C (UPDATE MySQL + watch fraîcheur) pour détacher la
  manipulation de la parole de l'étape 3:45–7:00, le moment le plus délicat.
- Un troisième tient les slides (contexte, archi, conclusion) et gère le temps
  (chronomètre visible, signal discret à 7:00 si retard).
- Les deux autres répondent aux questions du jury sur les parties qu'ils ont codées
  (Airbyte/configure_airbyte.py, tests, schéma DB) — répartir à l'avance qui répond
  à quoi.

## Si quelque chose casse en salle

1. Ne pas essayer de déboguer Docker devant le jury au-delà de 20-30 secondes.
2. Basculer sur les captures de `captures_rapport_png.zip` (dossier
   `Projet groupe/`) à l'écran, dans l'ordre : Figure05 (filtres), Figure07
   (lecture seule), Figure15 (latence avant/après), Figure12 (tests).
3. Dire explicitement : "Voici le résultat obtenu lors de l'exécution réelle
   documentée dans le rapport" — ne pas prétendre que c'est en direct.
