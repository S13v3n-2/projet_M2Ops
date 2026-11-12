# projet_M2Ops

Réalisation d'une pipeline de gazette matinale automatisée

[`Document de cadrage du projet`](./docs/cadrage.md)

[Fichier `sources.csv`](./sources.csv)

## Contribution

1. Création d'un environnement virtuel `python`

```bash
python -m venv .venv
```

2. Activation de l'environnement virtuel

Linux:

`source .venv/bin/activate`

Windows:

`.\.venv\Scripts\activate`

3. Installation des dépendances

```bash
pip install -e ".[dev]"
```

4. Configuration de l'environnement

Copier `.env.example` vers `.env` (ignoré par git) et renseigner au minimum `AWS_ACCESS_KEY_ID` et `AWS_SECRET_ACCESS_KEY` (clés du data lake RustFS). Le même fichier sert aux scripts python en local et à `docker compose`.

5. Lancement des services

Un seul `docker-compose.yml` à la racine :

| Service | Rôle | Accès |
|---|---|---|
| `rustfs` | data lake S3, couche bronze | API `http://localhost:9000`, console `http://localhost:9001` |
| `db` | PostgreSQL des données, couches silver et gold | `localhost:5432` |
| `adminer` | interface web de la base `db` | `http://localhost:8081` (système PostgreSQL, serveur `db`) |
| `kestra` et `kestra-db` | orchestrateur et sa base | `http://localhost:8080` |

Les profils actifs se règlent avec `COMPOSE_PROFILES` dans `.env` : `local` pour `rustfs`, `dev` pour `adminer`. `db`, `kestra` et `kestra-db` démarrent toujours. En prod avec un S3 cloud, on retire le profil `local` et on renseigne `KESTRA_S3_ENDPOINT_URL`.

```bash
docker compose up -d
```

6. Application des migrations Alembic

```bash
alembic upgrade head
```

7. Import des sources depuis `sources.csv`

```bash
python -m la_gazette_des_sorciers.database.import_sources
```

Le script réalise un upsert sur `id` : les sources existantes sont mises à jour (`name`, `type`, `region`, `url_flux`, `conditions`, `notes`), les nouvelles sont créées actives. Il peut être relancé sans risque. Un autre fichier CSV peut être passé en argument.

8. Lancement de la pipeline

```bash
python -m la_gazette_des_sorciers.main
```

La collecte bronze se lance avec les commandes de la section suivante.

## Collecte bronze et stockage S3

La collecte utilise une seule destination, choisie par `S3_ENABLED` :

- `true` : `collecte_xml` écrit les XML et leurs métadonnées directement dans
  le bucket ; `collecte_json` y lit ces objets, les convertit et y écrit les JSON.
  Aucun fichier n'est créé dans `DATA_DIR` par ces collecteurs.
- `false` : les deux collecteurs lisent et écrivent uniquement dans `DATA_DIR`.

Le module `stockage_s3` sert à transférer vers S3 des fichiers collectés en
mode local lors d'une exécution précédente. Il n'est pas nécessaire en mode S3.

1. Le mode S3 est activé dans `.env` avec `S3_ENABLED=true` (valeur de `.env.example`).
   Avec `S3_ENABLED=false`, tout reste sur disque dans `DATA_DIR`.
   `S3_ENDPOINT_URL` doit viser l'API S3 (`http://127.0.0.1:9000`), et non la console web.
   Les chemins relatifs de `.env`, comme `./sources.csv` et `./data`, sont résolus
   depuis le dossier contenant `.env`, même si les scripts sont lancés ailleurs.

2. Démarrer RustFS, qui utilise les clés `AWS_ACCESS_KEY_ID` et `AWS_SECRET_ACCESS_KEY` de `.env` :

```bash
docker compose up -d rustfs
```

3. Depuis la racine du projet, avec Python 3.12 et les dépendances installées :

```powershell
python -m la_gazette_des_sorciers.collecte_xml
python -m la_gazette_des_sorciers.collecte_json
```

La première commande lit `SOURCES_FILE` et crée les XML et leurs métadonnées.
La deuxième les convertit en JSON depuis la destination choisie. En mode S3,
le bucket `S3_BUCKET` est créé s'il manque. En cas d'erreur S3, la collecte
échoue et ne bascule pas automatiquement vers `DATA_DIR`.

Pour transférer plus tard les fichiers d'une collecte locale vers S3 :

```powershell
python -m la_gazette_des_sorciers.stockage_s3
```

Pour ne renvoyer qu'une journée UTC, ajouter `--date AAAA-MM-JJ`. Relancer le
dépôt sur les mêmes fichiers remplace les objets aux mêmes clés.

Les clés S3 suivent les mêmes chemins relatifs qu'en mode local, par exemple
`xml/2026-10-21/flux.xml`, `xml/2026-10-21/flux.json` et
`json/2026-10-21/flux.json`. Les métadonnées contiennent `filepath` en mode
local et `s3_key` en mode S3 pour retrouver le XML à convertir.

## Nettoyage

```bash
python -m la_gazette_des_sorciers.nettoyage_rss [--date AAAA-MM-JJ]
```

Le nettoyage traite les JSON bruts d'un jour de collecte (aujourd'hui en UTC par défaut) :

- `S3_ENABLED=true` : il lit les objets `json/<jour>/*.json` du bucket RustFS. Aucun JSON propre n'est écrit sur disque, les articles et les rejets vont dans PostgreSQL et le rapport de qualité est déposé sous `rapports/qualite-<jour>.md` dans le bucket.
- `S3_ENABLED=false` : il lit `DATA_DIR/json/<jour>/`, écrit les JSON propres dans `DATA_DIR/clean/<jour>/` et le rapport dans `RAPPORTS_DIR` (`rapports/` par défaut, ignoré par git).

La colonne `fichier_brut` des tables `articles_propres` et `rejets` vaut `s3_key` (mode S3) ou `filepath` (mode disque). Les migrations doivent être appliquées avant (voir plus bas).

## Docker

1. Construction de l'image Docker

```bash
docker build -t la_gazette_des_sorciers .
```

2. Lancement du conteneur Docker

```bash
docker run --rm la_gazette_des_sorciers
```

## Pipeline Kestra

Kestra lance chaque étape dans un conteneur de l'image `gazette:local` :
`collecte` (flux RSS -> XML et JSON bruts dans le bucket RustFS) puis `nettoyage` (-> articles et rejets dans PostgreSQL, rapport sous `rapports/` dans le bucket).

Le flow `gazette_clear_article` se déclenche tout seul à la fin réussie de `gazette_download_article` (déclencheur `Flow` avec `dependsOn`). Il n'y a plus de flow `gazette_push_article` : l'insertion en base est faite par le nettoyage.

Les tâches rejoignent le réseau docker `gazette` et reçoivent `DATABASE_URL` et les variables `S3_*` depuis le conteneur Kestra. Dans ce réseau, la base est `db:5432` et le data lake `http://rustfs:9000`.

```bash
cp .env.example .env                    # puis renseigner les clés S3 et DATA_DIR_HOST
docker compose --profile build build    # image gazette:local
docker compose up -d                    # tous les services, Kestra sur http://localhost:8080
curl -u admin@kestra.io:Admin1234 -X POST -H 'Content-Type: application/x-yaml'      --data-binary @kestra/flows/gazette_download_article.yml http://localhost:8080/api/v1/main/flows   # déploie un flow
```

Appliquer les migrations avant la première exécution, puis importer les sources :

```bash
docker compose run --rm migrate         # alembic upgrade head dans l'image gazette:local, une fois db prête
```

Déployer les deux flows (`gazette_download_article` et `gazette_clear_article`). Le flow `gazette/gazette_download_article` se lance depuis l'interface (Execute) ou par son déclencheur planifié, le nettoyage suit automatiquement.

## Tests et CI

Les tests sont séparés en niveaux avec des marqueurs pytest. Un simple `pytest` ne lance que les tests unitaires.

| Niveau | Marqueur | Prérequis | Commande |
|---|---|---|---|
| Unitaires | `unit` (automatique) | aucun | `pytest` |
| Intégration | `integration` | PostgreSQL et S3 qui tournent (`.env`) | `pytest -m integration` |
| E2E | `e2e` | stack démarrée et une collecte déjà lancée | `pytest -m e2e` |

Les tests d'intégration utilisent un bucket jetable et appliquent les migrations Alembic. `test_nettoyage_reel` dépose un JSON dans le bucket, lance le nettoyage et vérifie les lignes en base et le rapport sous `rapports/`. Les tests e2e vérifient que le bucket du jour contient au moins `E2E_MIN_SOURCES` sources (8 par défaut) et que la base enregistre les collectes réussies.

Les workflows GitHub Actions (`.github/workflows/`) :

| Workflow | Déclencheur | Contenu |
|---|---|---|
| `ci.yml` | chaque push | ruff, tests unitaires, puis construction et publication de l'image sur ghcr.io (branche `main` seulement) |
| `integration.yml` | pull request vers `develop` ou `main` | tests d'intégration avec PostgreSQL et RustFS en services, identifiants jetables |
| `nightly.yml` | tous les jours à 2h (UTC) et à la demande | stack docker compose (db, rustfs), migrations, import des sources, collecte avec l'image `gazette`, puis tests e2e |

### Détection de secrets

Le workflow `secrets.yml` lance gitleaks sur tout l'historique git : à chaque push, à chaque pull request vers `develop` ou `main`, et chaque lundi à 3h (UTC). Il échoue si une clé, un mot de passe ou un token est trouvé. Les valeurs factices autorisées (`.env.example`, identifiants jetables de la CI) sont listées dans `.gitleaks.toml`.

Un secret publié doit être considéré comme compromis : il faut le révoquer ou le changer, le retirer du code ne suffit pas car il reste dans l'historique.

## Pour aller plus loin

1. Génération du requirements.txt

```bash
pip-compile pyproject.toml -o requirements.txt
pip-compile pyproject.toml --extra=dev -o requirements-dev.txt
```

2. Création d'une migration

Après avoir modifié les modèles de la base de données dans `db_models.py` :

```bash
alembic revision --autogenerate -m "Nom de la migration"
```