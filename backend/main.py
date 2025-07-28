import logging
import os
from datetime import datetime

import pandas as pd
from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional

from joblib import load
from pydantic import BaseModel



# Créez l'application FastAPI
app = FastAPI()

# Configuration du middleware CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration des répertoires
DATA_DIR = "data/uploaded_files"
CLEAN_DIR = "data/cleaned_files"
MODEL_DIR = "data/saved_models"
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(CLEAN_DIR, exist_ok=True)
os.makedirs(MODEL_DIR, exist_ok=True)
os.makedirs("temp", exist_ok=True)

logging.basicConfig(level=logging.INFO)



