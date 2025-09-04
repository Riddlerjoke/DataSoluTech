import json
import os

from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.errors import OperationFailure
from passlib.context import CryptContext

from core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class MongoAccess:
    _instance = None

    def __new__(cls):
        """
        Modèle Singleton pour garantir qu’une seule instance de la classe est créée.

        Returns:
            MongoAccess: L'instance de la classe.
        """
        if cls._instance is None:
            cls._instance = super(MongoAccess, cls).__new__(cls)
            user = settings.MONGO_DB_USERNAME
            pw = settings.MONGO_DB_PASSWORD
            db_name = settings.MONGO_DB_NAME
            try:
                print(
                    f"Connexion à la base de données '{db_name}' en cours...")
                print(
                    f"URL de connexion : mongodb://{user}:{pw}@mongodb:27017")
                cls._instance.client = MongoClient(
                    f"mongodb://{user}:{pw}@mongodb:27017")
                cls._instance.db = cls._instance.client[db_name]
                # Test de connexion
                cls._instance.client.admin.command('ping')
                print("Connexion à MongoDB réussie.")
            except OperationFailure as e:
                print(
                    f"Erreur d'authentification à MongoDB : {e.details['errmsg']}")
            except Exception as e:
                print(f"Erreur lors de la connexion à MongoDB : {str(e)}")
        return cls._instance

    @property
    def users_collection(self) -> Collection:
        return self.db["users_db"]

    @property
    def data_cleaning_db(self) -> Collection:
        return self.db["data_cleaning_db"]

    def initialize_db(self):
        """
        Initialise la base de données en créant les collections nécessaires si elles n'existent pas.

        Cette méthode vérifie si les collections requises existent déjà dans la base de données.
        Si une collection n'existe pas, elle est créée. Pour la collection 'documentation_db',
        les documents sont insérés après la création. Pour la collection 'users_db', les superadmins
        sont créés après la création de la collection.
        """
        required_collections = ['users_db', "data_cleaning_db"]
        existing_collections = self.db.list_collection_names()

        for collection_name in required_collections:
            if collection_name not in existing_collections:
                self.db.create_collection(collection_name)
                print(f"Collection '{collection_name}' créée.")
                if collection_name == "documentation_db":
                    self.populate_documentation_collection()
                    print(
                        f"Collection '{collection_name}' créée et documents insérés avec succès.")
                elif collection_name == "users_db":
                    self.create_superadmin()
                    print(
                        f"Collection '{collection_name}' créée et superadmins créés avec succès.")
            else:
                print(f"Collection '{collection_name}' existe déjà.")

    def create_superadmin(self):
        """
        Crée les superadmins dans la base de données.
        """
        json_path = os.path.join(os.path.dirname(__file__), 'auth_roles.json')
        with open(json_path) as file:
            superadmins = json.load(file)
        for superadmin in superadmins:
            hashed_password = pwd_context.hash(superadmin['password'])
            superadmin['hashed_password'] = hashed_password
            del superadmin['password']
            self.users_collection.insert_one(superadmin)
        print("Superadmins créés avec succès.")

    def get_db_access(self):
        """
        Renvoie l'instance de la base de données.
        """
        return self.db