import os
import io
import pandas as pd
import logging
from typing import List, Dict, Any, Optional
from fastapi import UploadFile, HTTPException
from datetime import datetime

from model.extract_data_model import DatasetCreate, DatasetInDB, DatasetUpdate
from crud.extract_data_crud import DatasetCRUD

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
UPLOAD_DIR = "data/uploaded_files"
SAMPLE_SIZE = 10  # Number of rows to include in the data sample


class DataExtractor:
    """
    Class for extracting data from files and loading it into the database.
    """
    def __init__(self, dataset_crud: DatasetCRUD):
        self.dataset_crud = dataset_crud
        os.makedirs(UPLOAD_DIR, exist_ok=True)

    async def extract_from_csv(
        self,
        file: UploadFile,
        name: str,
        description: Optional[str] = None,
        source: Optional[str] = None
    ) -> DatasetInDB:

        # (Optionnel) on peut ne plus sauvegarder le fichier; je le garde si tu veux une trace.
        file_path = os.path.join(UPLOAD_DIR, file.filename)
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)

        try:
            df = pd.read_csv(file_path)
        except Exception as e:
            logger.error(f"Error reading CSV file: {str(e)}")
            raise HTTPException(status_code=400, detail=f"Error reading CSV file: {str(e)}")

        # Convertir NaN -> None pour Mongo
        df = df.where(pd.notnull(df), None)

        columns = df.columns.tolist()
        total_rows = int(len(df))
        data_sample = df.head(SAMPLE_SIZE).to_dict(orient="records")
        rows: List[Dict[str, Any]] = df.to_dict(orient="records")

        payload = DatasetCreate(
            name=name,
            description=description,
            source=source,
            columns=columns,
            data_sample=data_sample,
            total_rows=total_rows,  # sera ajusté après insert_many aussi
        )

        # >>> Crée le dataset et la collection de lignes
        created = await self.dataset_crud.create_dataset_with_rows(payload, rows)

        # (Optionnel) si tu veux garder le chemin du fichier source
        try:
            await self.dataset_crud.update_dataset(
                str(created.id),
                DatasetUpdate(file_path=file_path)
            )
        except Exception as e:
            logger.warning(f"Could not store file_path: {e}")

        logger.info(f"Dataset '{name}' créé avec table '{created.collection_name}' ({total_rows} lignes).")
        return created

    async def extract_from_kaggle(self, dataset_url: str, name: str, description: Optional[str] = None) -> DatasetInDB:
        """
        Placeholder for Kaggle integration.
        """
        raise HTTPException(status_code=501, detail="Kaggle API integration not implemented yet")

    async def process_dataset(self, dataset_id: str, operations: List[Dict[str, Any]]) -> DatasetInDB:
        """
        Process a dataset with a series of operations.
        """
        # 1) Récupérer le dataset
        dataset = await self.dataset_crud.get_dataset(dataset_id)
        if not dataset:
            raise HTTPException(status_code=404, detail="Dataset not found")

        # 2) Charger le fichier associé
        file_path = dataset.file_path
        if not file_path or not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="Dataset file not found")

        try:
            df = pd.read_csv(file_path)
        except Exception as e:
            logger.error(f"Error reading dataset file: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error reading dataset file: {str(e)}")

        # 3) Appliquer les opérations
        for operation in operations:
            op_type = operation.get("type")
            if op_type == "drop_na":
                df = df.dropna(subset=operation.get("columns"))
            elif op_type == "fill_na":
                value = operation.get("value")
                columns = operation.get("columns", None)
                if columns:
                    for col in columns:
                        if col in df.columns:
                            df[col] = df[col].fillna(value)
                else:
                    df = df.fillna(value)
            elif op_type == "drop_columns":
                columns = operation.get("columns", [])
                df = df.drop(columns=[c for c in columns if c in df.columns], errors="ignore")
            elif op_type == "rename_columns":
                rename_dict = operation.get("rename_dict", {})
                df = df.rename(columns=rename_dict)
            else:
                logger.warning(f"Unknown operation type: {op_type}")

        # 4) Sauvegarder le CSV transformé
        processed_file_path = os.path.join(
            UPLOAD_DIR,
            f"processed_{dataset_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.csv"
        )
        df.to_csv(processed_file_path, index=False)

        # 5) Préparer l'update
        columns = df.columns.tolist()
        total_rows = len(df)
        data_sample = df.head(SAMPLE_SIZE).to_dict(orient="records")

        update = DatasetUpdate(
            columns=columns,
            data_sample=data_sample,
            total_rows=total_rows,
            updated_at=datetime.now(),
        )

        # 6) Update via CRUD
        updated_dataset = await self.dataset_crud.update_dataset(dataset_id=dataset_id, dataset_update=update)
        if not updated_dataset:
            raise HTTPException(status_code=404, detail="Dataset not found after processing")

        logger.info(f"Dataset '{dataset.name}' processed with {total_rows} rows and {len(columns)} columns")
        return updated_dataset


