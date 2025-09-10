# Project MongoDocker

## Contexte
- Ce projet fournit une API de traitement et de préparation de données (CSV) basée sur FastAPI.
- Les jeux de données sont ingérés (upload CSV), inspectés (échantillon, colonnes, nombre de lignes), stockés et versionnés dans MongoDB.
- L’application est conteneurisée avec Docker (un service FastAPI et un service MongoDB) pour un démarrage simple et reproductible.

## Architecture (vue d’ensemble)
- Backend: FastAPI (dossier backend/)
  - Endpoints REST sous /api/v1
  - Chargement de CSV, extraction de méta‑données, opérations simples de nettoyage (drop_na, fill_na, drop_columns, rename_columns)
  - Persistance des métadonnées (datasets) et des lignes en collections MongoDB
- Base de données: MongoDB
  - Authentification via variables d’environnement (root/password définis dans .env)
  - Volumes Docker pour la persistance
- Fichiers/Volumes côté backend:
  - backend/data/uploaded_files: fichiers CSV téléversés et fichiers transformés
  - backend/data/cleaned_files: fichiers nettoyés via l’endpoint /clean

### Pré‑requis
- Option 1 (recommandée): Docker et Docker Compose
- Option 2 (exécution locale): Python 3.12+, pip, et un MongoDB accessible (par ex. le service MongoDB du docker-compose)

### Configuration
1) Dupliquer le fichier .env.exemple à la racine en .env puis renseigner au minimum:
   - MONGO_USERNAME
   - MONGO_PASSWORD
   - MONGO_DATABASE (nom de la base logique; par défaut côté code: data_cleaning_db)
   - MONGO_HOST (par défaut: mongodb quand vous utilisez docker-compose)
   - MONGO_PORT (par défaut: 27017)

### Exemple .env (développement rapide)
- MONGO_USERNAME=root
- MONGO_PASSWORD=example
- MONGO_DATABASE=data_cleaning_db
- MONGO_HOST=mongodb
- MONGO_PORT=27017
- NODE_ENV=dev

## Démarrer avec Docker (recommandé)
1) Depuis la racine du projet, avec votre .env prêt:
   - docker compose up -d --build
2) Accès:
   - API: http://localhost:8000
   - Documentation interactive (Swagger): http://localhost:8000/docs
   - Le service MongoDB écoute sur le port 27017 (exposé en local).
3) Arrêt:
   - docker compose down

### Exécution locale (sans le conteneur FastAPI)
Vous pouvez utiliser Docker uniquement pour MongoDB, puis démarrer FastAPI localement.
1) Démarrer MongoDB via docker-compose:
   - docker compose up -d mongodb
2) Configurer l’environnement Python:
   - cd backend
   - python -m venv .venv
   - .venv\Scripts\activate (Windows) ou source .venv/bin/activate (macOS/Linux)
   - pip install -r requirements.txt
3) Lancer l’API en développement:
   - uvicorn main:app --reload --host 0.0.0.0 --port 8000
4) Ouvrir http://localhost:8000/docs

## Principaux endpoints (résumé)
- GET /
  - Vérification de vie: {"message": "Bienvenue dans l'API de traitement de données."}

- POST /api/v1/datasets/
  - Crée un dataset à partir d’un fichier CSV (multipart/form-data)
  - Champs: file (CSV), name (str), description (str, optionnel), source (str, optionnel)
  - Retourne les métadonnées du dataset et crée une collection dédiée pour les lignes

- GET /api/v1/datasets/
  - Liste paginée des datasets (query: skip, limit)

- GET /api/v1/datasets/{dataset_id}
  - Détail d’un dataset

- PUT /api/v1/datasets/{dataset_id}
  - Mise à jour partielle des métadonnées d’un dataset

- DELETE /api/v1/datasets/{dataset_id}
  - Supprime un dataset

- POST /api/v1/datasets/{dataset_id}/process
  - Applique des opérations simples sur le CSV d’origine et met à jour les métadonnées (colonnes, total_rows, échantillon)
  - Body JSON (exemples d’opérations):
    [
      {"type": "drop_na", "columns": ["col1", "col2"]},
      {"type": "fill_na", "value": 0, "columns": ["age"]},
      {"type": "drop_columns", "columns": ["to_remove"]},
      {"type": "rename_columns", "rename_dict": {"old": "new"}}
    ]

- POST /upload/
  - Dépose un fichier CSV brut dans backend/data/uploaded_files (utile pour tests simples)

- POST /clean/
  - Nettoie un CSV (dropna simple) et l’enregistre dans backend/data/cleaned_files

### Notes sur la base de données
- Hôte MongoDB en Docker: mongodb (réseau interne docker-compose). Depuis l’API, la connexion utilise: mongodb://<user>:<password>@mongodb:27017
- Collections créées automatiquement au démarrage si absentes:
  - users_db (des "superadmins" peuvent être chargés depuis backend/connector/auth_roles.json)
  - data_cleaning_db (stocke les datasets)

## Structure du projet (extrait)
- docker-compose.yml: orchestre MongoDB et l’API
- backend/
  - main.py: définition des routes FastAPI
  - app/extract_data.py: logique d’extraction et de traitement
  - crud/extract_data_crud.py: accès aux données (PyMongo)
  - model/extract_data_model.py: schémas Pydantic
  - connector/connectorBDD.py: connexion MongoDB et initialisation
  - core/config.py: configuration (variables d’environnement)
  - Dockerfileapi: image de l’API

### Dépannage
- Erreur d’authentification MongoDB
  - Vérifiez MONGO_USERNAME/MONGO_PASSWORD/MONGO_DATABASE dans .env.
  - Supprimez le volume Mongo si vous avez changé les identifiants après un premier démarrage: docker compose down -v puis docker compose up -d
- L’API ne répond pas sur localhost:8000
  - Vérifiez que le service fastapi est up: docker compose ps
  - Consultez les logs: docker compose logs -f fastapi
- Impossible de lire le CSV
  - Assurez-vous que le fichier est bien au format .csv et encodé correctement (UTF-8 conseillé).

Licence
- Projet à usage interne/éducatif.
