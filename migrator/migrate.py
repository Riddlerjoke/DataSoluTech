import os
import sys
import logging
from datetime import datetime, timezone

import pandas as pd
from pymongo import MongoClient, InsertOne
from pymongo.errors import BulkWriteError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stdout,
)

MONGO_URI = os.getenv(
    "MONGO_URI",
    "mongodb://ingestor:ingestorpass@mongodb:27017/meddb?authSource=admin",
)
DATA_FILE = os.getenv("DATA_FILE", "/app/data/raw/healthcare.csv")
DB_NAME = os.getenv("DB_NAME", "meddb")
COLLECTION = os.getenv("COLLECTION", "patients")
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "5000"))

# ---------- helpers ----------

def parse_date(value):
    if value is None or value == "" or pd.isna(value):
        return None
    try:
        return pd.to_datetime(value, errors="coerce").to_pydatetime()
    except Exception:
        return None

def to_list(val):
    if pd.isna(val) or val is None:
        return []
    return [s.strip() for s in str(val).split(",") if s and s.strip()]

def pick_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    """Return the first column name from candidates that exists in df.columns."""
    for c in candidates:
        if c in df.columns:
            return c
    return None

# canonical → list of aliases we will try in this order
ALIASES = {
    "patient_id":   ["patient_id", "patientid", "patient id", "id"],
    "name":         ["name", "patient_name", "full_name"],
    "age":          ["age", "patient_age"],
    "gender":       ["gender", "sex"],
    "blood_type":   ["blood_type", "blood group", "blood_group", "bloodtype"],
    "diagnosis":    ["diagnosis", "condition", "diagnoses"],
    "admission_date": ["admission_date", "admission", "admitted_date", "date_of_admission"],
    "doctor":       ["doctor", "physician", "attending_doctor"],
    "hospital":     ["hospital", "facility"],
    "insurance":    ["insurance", "payer", "coverage"],
    "billing_amount": ["billing_amount", "billing", "bill", "charges", "amount_billed"],
    "room_number":  ["room_number", "room", "bed"],
    "department":   ["department", "dept"],
    "visit_date":   ["visit_date", "date", "visit", "date_of_visit"],
    "treatment":    ["treatment", "medication", "therapy"],
    "lab_result":   ["lab_result", "lab_results", "test_result", "result"],
    "symptoms":     ["symptoms", "complaints", "chief_complaint"],
}

def run_migration() -> dict:
    logging.info("Connecting to MongoDB…")
    client = MongoClient(MONGO_URI)
    db = client.get_database(DB_NAME)
    col = db[COLLECTION]

    if not os.path.exists(DATA_FILE):
        logging.error("DATA_FILE not found: %s", DATA_FILE)
        return {"inserted": 0, "error": f"Missing file {DATA_FILE}"}

    logging.info("Reading CSV: %s", DATA_FILE)
    df = pd.read_csv(DATA_FILE)

    # Normalize header names
    df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")
    logging.info("Detected columns: %s", list(df.columns))

    # Resolve actual column names by alias
    cols = {k: pick_col(df, [a.replace(" ", "_") for a in v]) for k, v in ALIASES.items()}
    missing_core = [k for k in ("name", "age", "gender") if cols.get(k) is None]
    if missing_core:
        logging.warning("Missing expected key columns (will be null): %s", missing_core)

    # Create _id
    pid_col = cols.get("patient_id")
    if pid_col:
        df["_id"] = df[pid_col].apply(lambda x: f"PAT-{x}")
    else:
        df["_id"] = df.index.map(lambda i: f"PAT-{i}")

    def get(row, key, cast=None):
        colname = cols.get(key)
        val = row.get(colname) if colname else None
        if cast:
            try:
                return cast(val) if val is not None and not pd.isna(val) else None
            except Exception:
                return None
        return None if (val is None or (isinstance(val, float) and pd.isna(val))) else val

    def make_doc(row):
        return {
            "_id": row.get("_id"),
            "name": (str(row.get("name") or "").strip() or None),
            "age": (int(float(row.get("age"))) if pd.notna(row.get("age")) else None),
            "gender": (str(row.get("gender") or "").strip() or None),
            "blood_type": (str(row.get("blood_type") or "").strip() or None),

            # mapping vers ton schéma logique
            "diagnosis": (str(row.get("medical_condition") or "").strip() or None),
            "treatment": (str(row.get("medication") or "").strip() or None),
            "lab_result": (str(row.get("test_results") or "").strip() or None),

            # garde les deux dates (admission/discharge)
            "admission_date": parse_date(row.get("date_of_admission")),
            "discharge_date": parse_date(row.get("discharge_date")),  # nouveau champ

            # si tu veux conserver visit_date dans le MVP, on peut le caler sur la discharge
            "visit_date": parse_date(row.get("discharge_date")),

            # autres champs
            "doctor": (str(row.get("doctor") or "").strip() or None),
            "hospital": (str(row.get("hospital") or "").strip() or None),
            "insurance": (str(row.get("insurance_provider") or "").strip() or None),
            "billing_amount": (float(row.get("billing_amount")) if pd.notna(row.get("billing_amount")) else None),
            "room_number": (str(row.get("room_number") or "").strip() or None),
            "department": (str(row.get("admission_type") or "").strip() or None),
            # Admission Type → department (ou renomme le champ si tu préfères)
            "symptoms": [],  # pas présent dans ce CSV

            "source": "kaggle_healthcare_dataset_v1",
            "createdAt": datetime.now(timezone.utc),
            "updatedAt": datetime.now(timezone.utc),
        }

    logging.info("Preparing bulk operations…")
    ops = [InsertOne(make_doc(r)) for r in df.to_dict(orient="records")]

    inserted = 0
    try:
        for i in range(0, len(ops), BATCH_SIZE):
            batch = ops[i : i + BATCH_SIZE]
            res = col.bulk_write(batch, ordered=False)
            inserted += res.inserted_count
            logging.info("Inserted so far: %s", inserted)
    except BulkWriteError as bwe:
        write_errors = bwe.details.get("writeErrors", [])
        dup_errors = [e for e in write_errors if e.get("code") == 11000]
        logging.warning(
            "Bulk write encountered %d errors (%d duplicates)",
            len(write_errors), len(dup_errors)
        )
        inserted += bwe.details.get("nInserted", 0)
    finally:
        logging.info("Ensuring indexes…")
        col.create_index([("name", 1)])
        col.create_index([("diagnosis", 1)])
        col.create_index([("admission_date", -1)])
        col.create_index([("discharge_date", -1)])
        col.create_index([("gender", 1), ("age", 1)])
        col.create_index([("hospital", 1)])

    summary = {"inserted": inserted}
    logging.info("Done ✅ %s", summary)
    return summary

if __name__ == "__main__":
    result = run_migration()
    if result.get("error"):
        sys.exit(1)
