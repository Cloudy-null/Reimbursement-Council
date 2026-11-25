"""The claim export's JSON Schema on disk, and checking an export against it.

The schema file is generated from the ClaimExport model (write-schema command) and committed,
so a claims system can use it without our code. A test fails if the file and the model drift.
"""

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from reimbursement_council.core.models.export import ClaimExport

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schemas" / "claim-export.schema.json"


def generated_schema() -> dict[str, Any]:
    schema = ClaimExport.model_json_schema()
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", **schema}


def write_schema(path: Path = SCHEMA_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(generated_schema(), indent=2) + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")  # same bytes on Windows and Linux


def load_schema(path: Path = SCHEMA_PATH) -> dict[str, Any]:
    schema: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return schema


def schema_errors(data: Any, schema: dict[str, Any] | None = None) -> list[str]:
    """Every place the data breaks the schema, as 'path: message'. Empty means valid."""
    validator = Draft202012Validator(schema or load_schema())
    return [
        f"{'/'.join(str(p) for p in error.absolute_path) or '(root)'}: {error.message}"
        for error in sorted(validator.iter_errors(data), key=lambda e: list(e.absolute_path))
    ]
