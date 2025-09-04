from typing import List, Optional, Dict, Any
from datetime import datetime
import re
from fastapi.concurrency import run_in_threadpool


from bson import ObjectId
from bson.errors import InvalidId
from motor.motor_asyncio import AsyncIOMotorCollection
from pymongo.results import InsertOneResult, UpdateResult, DeleteResult

from model.extract_data_model import DatasetCreate, DatasetUpdate, DatasetInDB


def _oid(s: str) -> ObjectId:
    """Convertit une str hex 24 en ObjectId, ou lève ValueError."""
    if isinstance(s, ObjectId):
        return s
    if isinstance(s, str) and ObjectId.is_valid(s):
        return ObjectId(s)
    raise ValueError("Invalid ObjectId")


def _slugify(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s or "dataset"


class DatasetCRUD:
    """
    CRUD operations for datasets in MongoDB.
    """

    def __init__(self, collection: AsyncIOMotorCollection):
        """
        Initialize with MongoDB collection.

        Args:
            collection: MongoDB (Motor) collection for datasets
        """
        self.collection = collection

    async def create_dataset_with_rows(
            self,
            dataset: DatasetCreate,
            rows: List[Dict[str, Any]],
    ) -> DatasetInDB:
        """
        Crée le dataset (métadonnées) ET la collection Mongo pour les lignes du CSV.
        """
        # 1) Insérer les métadonnées
        meta = dataset.model_dump()
        now = datetime.now()
        meta.setdefault("created_at", now)
        meta.setdefault("updated_at", now)

        result: InsertOneResult = await run_in_threadpool(self.collection.insert_one, meta)

        # 2) Générer un nom de collection unique pour les rows
        slug = _slugify(dataset.name)
        suffix = str(result.inserted_id)[:8]
        rows_collection_name = f"ds_{slug}_{suffix}"

        # 3) Insérer toutes les lignes dans cette nouvelle collection
        rows_coll = self.collection.database[rows_collection_name]

        # insert_many peut être coûteux => ordered=False et ignore si rows vide
        if rows:
            await run_in_threadpool(rows_coll.insert_many, rows, False)

        # 4) Mettre à jour le dataset avec collection_name et total_rows exact
        await run_in_threadpool(
            self.collection.update_one,
            {"_id": result.inserted_id},
            {"$set": {"collection_name": rows_collection_name, "total_rows": len(rows), "updated_at": datetime.now()}},
        )

        # 5) Relire et retourner
        created = await run_in_threadpool(self.collection.find_one, {"_id": result.inserted_id})
        return DatasetInDB(**created)

    async def create_dataset(self, dataset: DatasetCreate) -> DatasetInDB:
        """
        Create a new dataset in the database.

        Args:
            dataset: Dataset to create

        Returns:
            Created dataset
        """
        # Pydantic v2: model_dump()
        doc = dataset.model_dump()
        # S'assurer d'un updated_at cohérent au moment de l'insert si besoin
        now = datetime.now()
        doc.setdefault("created_at", now)
        doc.setdefault("updated_at", now)

        result: InsertOneResult = await self.collection.insert_one(doc)
        created_dataset = await self.collection.find_one({"_id": result.inserted_id})
        return DatasetInDB(**created_dataset)

    async def get_dataset(self, dataset_id: str) -> Optional[DatasetInDB]:
        """
        Get a dataset by ID.

        Args:
            dataset_id: ID of the dataset

        Returns:
            Dataset if found, None otherwise
        """
        try:
            oid = _oid(dataset_id)
        except ValueError:
            return None

        dataset = await self.collection.find_one({"_id": oid})
        if dataset:
            return DatasetInDB(**dataset)
        return None

    async def get_datasets(self, skip: int = 0, limit: int = 100) -> List[DatasetInDB]:
        """
        Get a list of datasets.

        Args:
            skip: Number of datasets to skip
            limit: Maximum number of datasets to return

        Returns:
            List of datasets
        """
        datasets: List[DatasetInDB] = []
        cursor = self.collection.find().skip(skip).limit(limit)
        async for dataset in cursor:
            datasets.append(DatasetInDB(**dataset))
        return datasets

    async def update_dataset(self, dataset_id: str, dataset_update: DatasetUpdate) -> Optional[DatasetInDB]:
        """
        Update a dataset.

        Args:
            dataset_id: ID of the dataset to update
            dataset_update: Dataset update data

        Returns:
            Updated dataset if found, None otherwise
        """
        try:
            oid = _oid(dataset_id)
        except ValueError:
            return None

        # Pydantic v2: model_dump(exclude_none=True)
        update_data: Dict[str, Any] = dataset_update.model_dump(exclude_none=True)

        # Si l'appelant n'a pas fourni updated_at, on le force
        update_data.setdefault("updated_at", datetime.now())

        if not update_data:
            # Pas de données => renvoyer l'existant si présent
            return await self.get_dataset(dataset_id)

        result: UpdateResult = await self.collection.update_one(
            {"_id": oid},
            {"$set": update_data}
        )

        if result.matched_count == 0:
            # Aucun document avec cet _id
            return None

        # Même si modified_count == 0 (aucun champ changé), on relit l'objet
        return await self.get_dataset(dataset_id)

    async def delete_dataset(self, dataset_id: str) -> bool:
        """
        Delete a dataset.

        Args:
            dataset_id: ID of the dataset to delete

        Returns:
            True if the dataset was deleted, False otherwise
        """
        try:
            oid = _oid(dataset_id)
        except ValueError:
            return False

        result: DeleteResult = await self.collection.delete_one({"_id": oid})
        return result.deleted_count > 0

    async def count_datasets(self) -> int:
        """
        Count the number of datasets.

        Returns:
            Number of datasets
        """
        return await self.collection.count_documents({})

    async def search_datasets(self, query: str) -> List[DatasetInDB]:
        """
        Search for datasets by name or description.

        Args:
            query: Search query

        Returns:
            List of matching datasets
        """
        datasets: List[DatasetInDB] = []
        cursor = self.collection.find({
            "$or": [
                {"name": {"$regex": query, "$options": "i"}},
                {"description": {"$regex": query, "$options": "i"}}
            ]
        })
        async for dataset in cursor:
            datasets.append(DatasetInDB(**dataset))
        return datasets
