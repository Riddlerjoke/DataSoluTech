from typing import List, Optional, Dict, Any, Annotated
from datetime import datetime

from pydantic import BaseModel, Field
from pydantic.functional_validators import BeforeValidator, AfterValidator
from pydantic.functional_serializers import PlainSerializer
from pydantic.json_schema import WithJsonSchema

from bson import ObjectId


# --- ObjectId alias compatible Pydantic v2 & OpenAPI ---
# - OpenAPI voit un "string" (pattern hex 24)
# - validation -> conversion en ObjectId
# - sérialisation JSON -> string

def _validate_hex24(v):
    if isinstance(v, ObjectId):
        return v
    if isinstance(v, str) and ObjectId.is_valid(v):
        return v
    raise ValueError("Invalid ObjectId")

def _to_object_id(v):
    if isinstance(v, ObjectId):
        return v
    if isinstance(v, str) and ObjectId.is_valid(v):
        return ObjectId(v)
    raise ValueError("Invalid ObjectId")

PyObjectId = Annotated[
    ObjectId,  # <- le modèle stocke bien un ObjectId
    BeforeValidator(_to_object_id),                                # accepte str hex24 ou ObjectId
    PlainSerializer(lambda v: str(v), return_type=str),            # JSON = string
    WithJsonSchema(                                                # OpenAPI = string pattern
        {"type": "string", "pattern": "^[0-9a-f]{24}$", "example": "64b1e0d9a3c4b5f6a7d8e9f0"},
        mode="both",
    ),
]


# --- Models ---

class DatasetBase(BaseModel):
    """Base model for dataset with common attributes."""
    name: str = Field(..., description="Name of the dataset")
    description: Optional[str] = Field(None, description="Description of the dataset")
    source: Optional[str] = Field(None, description="Source of the dataset (e.g., Kaggle)")
    created_at: datetime = Field(default_factory=datetime.now, description="Creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.now, description="Last update timestamp")

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
    }


class DatasetCreate(DatasetBase):
    """Model for creating a new dataset."""
    columns: List[str] = Field(..., description="List of column names in the dataset")
    data_sample: List[Dict[str, Any]] = Field(..., description="Sample of the dataset data")
    total_rows: int = Field(..., description="Total number of rows in the dataset")


class DatasetInDB(DatasetBase):
    """Model for a dataset stored in the database."""
    id: PyObjectId = Field(default_factory=ObjectId, alias="_id")
    columns: List[str] = Field(..., description="List of column names in the dataset")
    data_sample: List[Dict[str, Any]] = Field(..., description="Sample of the dataset data")
    total_rows: int = Field(..., description="Total number of rows in the dataset")
    file_path: Optional[str] = Field(None, description="Path to the dataset file")
    collection_name: Optional[str] = Field(None, description="Name of the collection for the dataset rows")


class DatasetUpdate(BaseModel):
    """Model for updating an existing dataset."""
    name: Optional[str] = None
    description: Optional[str] = None
    columns: Optional[List[str]] = None
    data_sample: Optional[List[Dict[str, Any]]] = None
    total_rows: Optional[int] = None
    file_path: Optional[str] = None
    collection_name: Optional[str] = None
    updated_at: datetime = Field(default_factory=datetime.now)


class DatasetResponse(DatasetBase):
    """Model for dataset response."""
    id: PyObjectId = Field(..., alias="_id")
    columns: List[str]
    data_sample: List[Dict[str, Any]]
    total_rows: int
    file_path: Optional[str] = None
    collection_name: Optional[str] = None

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
    }


class DatasetList(BaseModel):
    """Model for a list of datasets."""
    datasets: List[DatasetResponse]
    total: int
