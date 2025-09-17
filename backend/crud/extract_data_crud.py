# crud/extract_data_crud.py

from typing import List, Optional, Dict, Any
from datetime import datetime
import re

from bson import ObjectId
from pymongo.collection import Collection
from pymongo.results import InsertOneResult, UpdateResult, DeleteResult
from fastapi.concurrency import run_in_threadpool

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
    CRUD operations for datasets in MongoDB (PyMongo sync wrapped in threadpool).
    """

    def __init__(self, collection: Collection):
        """
        Args:
            collection: PyMongo collection storing the dataset metadata documents
                        (chez toi: mongo_access.data_cleaning_db)
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
        meta = dataset.model_dump()
        now = datetime.now()
        meta.setdefault("created_at", now)
        meta.setdefault("updated_at", now)

        result: InsertOneResult = await run_in_threadpool(self.collection.insert_one, meta)

        slug = _slugify(dataset.name)
        suffix = str(result.inserted_id)[:8]
        rows_collection_name = f"ds_{slug}_{suffix}"

        rows_coll = self.collection.database[rows_collection_name]

        if rows:
            # ordered=False pour accélérer et continuer si une ligne pose souci
            await run_in_threadpool(rows_coll.insert_many, rows, False)

        await run_in_threadpool(
            self.collection.update_one,
            {"_id": result.inserted_id},
            {"$set": {
                "collection_name": rows_collection_name,
                "total_rows": len(rows),
                "updated_at": datetime.now()
            }},
        )

        created = await run_in_threadpool(self.collection.find_one, {"_id": result.inserted_id})
        return DatasetInDB(**created)

    async def create_dataset(self, dataset: DatasetCreate) -> DatasetInDB:
        """Create only the metadata document (sans insertion des lignes)."""
        doc = dataset.model_dump()
        now = datetime.now()
        doc.setdefault("created_at", now)
        doc.setdefault("updated_at", now)

        result: InsertOneResult = await run_in_threadpool(self.collection.insert_one, doc)
        created = await run_in_threadpool(self.collection.find_one, {"_id": result.inserted_id})
        return DatasetInDB(**created)

    async def get_dataset(self, dataset_id: str) -> Optional[DatasetInDB]:
        """Get a dataset by ID."""
        try:
            oid = _oid(dataset_id)
        except ValueError:
            return None

        doc = await run_in_threadpool(self.collection.find_one, {"_id": oid})
        return DatasetInDB(**doc) if doc else None

    async def get_datasets(self, skip: int = 0, limit: int = 100) -> List[DatasetInDB]:
        """List datasets with pagination."""
        def _fetch() -> List[Dict[str, Any]]:
            return list(self.collection.find().skip(skip).limit(limit))
        items = await run_in_threadpool(_fetch)
        return [DatasetInDB(**d) for d in items]

    async def update_dataset(self, dataset_id: str, dataset_update: DatasetUpdate) -> Optional[DatasetInDB]:
        """Update a dataset metadata document."""
        try:
            oid = _oid(dataset_id)
        except ValueError:
            return None

        update_data: Dict[str, Any] = dataset_update.model_dump(exclude_none=True)
        update_data.setdefault("updated_at", datetime.now())

        if not update_data:
            return await self.get_dataset(dataset_id)

        def _update() -> UpdateResult:
            return self.collection.update_one({"_id": oid}, {"$set": update_data})

        result: UpdateResult = await run_in_threadpool(_update)
        if result.matched_count == 0:
            return None

        return await self.get_dataset(dataset_id)

    async def delete_dataset(self, dataset_id: str) -> bool:
        """Delete a dataset metadata document."""
        try:
            oid = _oid(dataset_id)
        except ValueError:
            return False

        result: DeleteResult = await run_in_threadpool(self.collection.delete_one, {"_id": oid})
        return result.deleted_count > 0

    async def count_datasets(self) -> int:
        """Count datasets."""
        return await run_in_threadpool(self.collection.count_documents, {})

    async def search_datasets(self, query: str) -> List[DatasetInDB]:
        """Search datasets by name or description."""
        def _search() -> List[Dict[str, Any]]:
            cur = self.collection.find({
                "$or": [
                    {"name": {"$regex": query, "$options": "i"}},
                    {"description": {"$regex": query, "$options": "i"}},
                ]
            })
            return list(cur)
        items = await run_in_threadpool(_search)
        return [DatasetInDB(**it) for it in items]
