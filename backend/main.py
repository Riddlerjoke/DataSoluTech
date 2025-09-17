import logging
import os
from typing import List, Optional, Dict, Any

import pandas as pd
from fastapi import FastAPI, UploadFile, File, HTTPException, Form, Depends, Query, Body
from fastapi.middleware.cors import CORSMiddleware

from connector.connectorBDD import MongoAccess
from model.extract_data_model import DatasetUpdate, DatasetResponse, DatasetList
from crud.extract_data_crud import DatasetCRUD
# ⚠️ Si ton fichier est à la racine du projet:
from app.extract_data import DataExtractor
# ⚠️ Si ton fichier est dans un package "app/": from app.extract_data import DataExtractor
from core.config import settings

# ----------------- App FastAPI -----------------

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------- Dossiers -----------------

DATA_DIR = "data/uploaded_files"
CLEAN_DIR = "data/cleaned_files"
MODEL_DIR = "data/saved_models"
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(CLEAN_DIR, exist_ok=True)
os.makedirs(MODEL_DIR, exist_ok=True)
os.makedirs("temp", exist_ok=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ----------------- Mongo (PyMongo) -----------------

mongo_access = MongoAccess()
mongo_access.initialize_db()

def _get_datasets_collection():
    # ⚠️ ICI: data_cleaning_db EST DÉJÀ UNE Collection PyMongo
    return mongo_access.data_cleaning_db

# ----------------- Dependencies -----------------

def get_dataset_crud() -> DatasetCRUD:
    return DatasetCRUD(_get_datasets_collection())

def get_data_extractor(dataset_crud: DatasetCRUD = Depends(get_dataset_crud)) -> DataExtractor:
    return DataExtractor(dataset_crud)

# ----------------- Routes -----------------

@app.get("/")
async def root():
    return {"message": "Bienvenue dans l'API de traitement de données."}

@app.post("/api/v1/datasets/", response_model=DatasetResponse, status_code=201)
async def create_dataset(
    file: UploadFile = File(...),
    name: str = Form(...),
    description: Optional[str] = Form(None),
    source: Optional[str] = Form(None),
    data_extractor: DataExtractor = Depends(get_data_extractor),
):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Le fichier doit être au format CSV.")
    try:
        dataset = await data_extractor.extract_from_csv(file, name, description, source)
        return dataset
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating dataset: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error creating dataset: {str(e)}")

@app.get("/api/v1/datasets/", response_model=DatasetList)
async def get_datasets(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    dataset_crud: DatasetCRUD = Depends(get_dataset_crud),
):
    datasets = await dataset_crud.get_datasets(skip, limit)
    total = await dataset_crud.count_datasets()
    return {"datasets": datasets, "total": total}

@app.get("/api/v1/datasets/{dataset_id}", response_model=DatasetResponse)
async def get_dataset(
    dataset_id: str,
    dataset_crud: DatasetCRUD = Depends(get_dataset_crud),
):
    dataset = await dataset_crud.get_dataset(dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return dataset

@app.put("/api/v1/datasets/{dataset_id}", response_model=DatasetResponse)
async def update_dataset(
    dataset_id: str,
    dataset_update: DatasetUpdate,
    dataset_crud: DatasetCRUD = Depends(get_dataset_crud),
):
    dataset = await dataset_crud.update_dataset(dataset_id, dataset_update)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return dataset

@app.delete("/api/v1/datasets/{dataset_id}", status_code=200)
async def delete_dataset(
    dataset_id: str,
    dataset_crud: DatasetCRUD = Depends(get_dataset_crud),
):
    deleted = await dataset_crud.delete_dataset(dataset_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return None

@app.post("/api/v1/datasets/{dataset_id}/process", response_model=DatasetResponse)
async def process_dataset(
    dataset_id: str,
    operations: List[Dict[str, Any]] = Body(...),
    data_extractor: DataExtractor = Depends(get_data_extractor),
):
    try:
        dataset = await data_extractor.process_dataset(dataset_id, operations)
        return dataset
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing dataset: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing dataset: {str(e)}")

@app.post("/upload/")
async def upload_file(file: UploadFile = File(...)):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Le fichier doit être au format CSV.")

    file_path = os.path.join(DATA_DIR, file.filename)
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    logging.info(f"Fichier {file.filename} téléchargé avec succès.")
    return {"filename": file.filename, "file_path": file_path}

@app.post("/clean/")
async def clean_data(file_path: str = Form(...)):
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Le fichier spécifié n'existe pas.")

    try:
        df = pd.read_csv(file_path)
        df_cleaned = df.dropna()
        clean_file_path = os.path.join(CLEAN_DIR, os.path.basename(file_path))
        df_cleaned.to_csv(clean_file_path, index=False)
        logging.info(f"Fichier nettoyé enregistré à {clean_file_path}.")
        return {"cleaned_file_path": clean_file_path}
    except Exception as e:
        logging.error(f"Erreur lors du nettoyage des données : {str(e)}")
        raise HTTPException(status_code=500, detail="Erreur lors du nettoyage des données.")
