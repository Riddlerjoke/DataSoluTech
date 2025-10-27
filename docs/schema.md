
## `docs/schema.md`
```markdown
# MongoDB Schema (MVP)


## Collection: `patients`
Each CSV row becomes one document.


### Example document
```json
{
"_id": "PAT-000123",
"name": "Jane Doe",
"gender": "Female",
"age": 51,
"symptoms": ["headache", "fatigue"],
"diagnosis": "Hypertension",
"treatment": "Lisinopril",
"visit_date": "2024-09-18T10:00:00.000Z",
"source": "kaggle_healthcare_dataset_v1",
"createdAt": "2025-10-27T09:00:00.000Z",
"updatedAt": "2025-10-27T09:00:00.000Z"
}