# 🏥 Migration d’un dataset Santé → MongoDB (MVP)

Ce dépôt propose un **MVP simple et reproductible** pour migrer un **jeu de données de santé synthétique** (issu de Kaggle) vers une base de données **MongoDB**, en utilisant **Docker**.  
L’objectif est de mettre en place une **chaîne d’ingestion robuste** sans développer d’API ni d’interface UI, pour garder le projet clair et stable.

---

## 🚀 Fonctionnalités

- 🐳 MongoDB **conteneurisé avec authentification activée**
- 🔐 Création automatique des utilisateurs et rôles (`ingestor`, `analyst`, `adminuser`) au démarrage
- 📊 Un job de migration (conteneur `migrator`) qui :
  - Lit un fichier CSV
  - Nettoie et normalise les données
  - Insère les documents dans la base `meddb`
  - Crée des index utiles
- 📜 Documentation incluse :
  - Schéma de la base
  - Rôles et accès
  - Commandes MongoDB de base
- ☁️ Base prête à être déployée sur AWS

---

## 🧰 Prérequis

- [Docker](https://www.docker.com/)  
- [Docker Compose](https://docs.docker.com/compose/)  
- Quelques notions de ligne de commande

---

## ⚙️ Installation et configuration

1. **Cloner le dépôt**
```bash
git clone https://github.com/your-username/healthcare-mongo-mvp.git
cd healthcare-mongo-mvp
```

2. **Configurer les variables d’environnement**
```bash
cp .env.example .env
```

3. **Démarrer MongoDB (avec création des rôles)**
```bash
docker compose up -d mongodb
```

✅ Cette commande :
- Lance le conteneur MongoDB  
- Exécute automatiquement `init-mongo.js` pour créer les utilisateurs  
- Active l’authentification

4. **Lancer la migration des données**
```bash
docker compose run --rm migrator
```

📝 Cette étape :
- Lit `/data/raw/healthcare_dataset.csv`
- Normalise les noms de colonnes
- Insère les documents nettoyés dans `meddb.patients`
- Crée les index

---

## 📦 Commandes Docker utiles

- Voir les conteneurs actifs :
```bash
docker ps
```

- Stopper les conteneurs :
```bash
docker compose down
```

- Rebuild du conteneur migrator après modification du script :
```bash
docker compose build migrator
```

- Redémarrer MongoDB proprement :
```bash
docker compose down -v
docker compose up -d mongodb
```

---

## 🧑‍💻 Connexion à MongoDB (ligne de commande)

Pour ouvrir un shell MongoDB dans le conteneur :

```bash
docker compose exec mongodb mongosh "mongodb://analyst:analystpass@localhost:27017/meddb?authSource=admin"
```

> ℹ️ Les identifiants (`analyst`, `ingestor`, `adminuser`) sont définis dans `init-mongo.js` ou dans `.env`.  
> `analyst` dispose d’un accès **lecture seule**, tandis que `ingestor` et `adminuser` ont plus de privilèges.

---

## 🧭 Commandes MongoDB de base

### Afficher les bases de données :
```javascript
show dbs
```

### Utiliser la base de données :
```javascript
use meddb
```

### Voir les collections :
```javascript
show collections
```

### Compter le nombre de documents :
```javascript
db.patients.countDocuments()
```

### Rechercher un patient par nom (insensible à la casse) :
```javascript
db.patients.findOne({ name: { $regex: "^paul hendersOn$", $options: "i" } })
```

### Obtenir un échantillon de données :
```javascript
db.patients.find().limit(5).pretty()
```

---

## 🧾 Schéma de la base de données (simplifié)

```json
{
  "_id": "PAT-123",
  "name": "John Doe",
  "age": 45,
  "gender": "Male",
  "blood_type": "O+",
  "diagnosis": "Hypertension",
  "treatment": "Paracetamol",
  "lab_result": "Inconclusive",
  "admission_date": "2020-05-15T00:00:00Z",
  "discharge_date": "2020-06-08T00:00:00Z",
  "visit_date": "2020-06-08T00:00:00Z",
  "doctor": "Stephanie Kramer",
  "hospital": "Wilson Group",
  "insurance": "Medicare",
  "billing_amount": 33211.29,
  "room_number": "109",
  "department": "Emergency",
  "createdAt": "2025-10-27T15:10:03Z",
  "updatedAt": "2025-10-27T15:10:03Z",
  "source": "kaggle_healthcare_dataset_v1"
}
```

---

## 👤 Utilisateurs & rôles

| Utilisateur     | Rôle MongoDB                 | Permissions                            |
|------------------|------------------------------|-----------------------------------------|
| `analyst`        | `read`                       | Lecture seule                          |
| `ingestor`       | `readWrite`                  | Lecture + écriture (migration)         |
| `adminuser`      | `userAdminAnyDatabase`       | Administration complète                |

📝 Ces utilisateurs sont créés automatiquement à l’initialisation grâce au fichier `init-mongo.js`.

---

## ☁️ Déploiement futur sur AWS (optionnel)

- Utiliser Amazon DocumentDB ou une instance MongoDB auto-hébergée  
- Sauvegarder les données sur Amazon S3  
- Gérer les conteneurs avec Amazon ECS  
- Sécuriser les identifiants avec AWS Secrets Manager

---

## 🧹 Nettoyage

```bash
docker compose down -v
```

Cette commande **arrête et supprime** tous les conteneurs, volumes et réseaux liés au projet.

---

## 📚 Références

- [Documentation MongoDB](https://www.mongodb.com/docs/)  
- [Documentation Docker](https://docs.docker.com/)  
- [Kaggle](https://www.kaggle.com/)  
- [Amazon DocumentDB](https://aws.amazon.com/documentdb/)

---

✨ **Principe MVP** : faire simple, stable et reproductible.  
Une fois le pipeline d’ingestion maîtrisé, il est facile d’y ajouter une API (par exemple avec FastAPI) ou une interface (par exemple avec Streamlit).