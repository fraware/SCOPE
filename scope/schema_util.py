"""JSON Schema loading and validation helpers."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import jsonschema
from referencing import Registry, Resource

_PACKAGE_ROOT = Path(__file__).resolve().parent.parent
_SCHEMAS_DIR = _PACKAGE_ROOT / "schemas"


def load_schema(name: str) -> dict[str, Any]:
    path = _SCHEMAS_DIR / name
    with path.open(encoding="utf-8") as fh:
        data: dict[str, Any] = json.load(fh)
        return data


@lru_cache(maxsize=1)
def _schema_registry() -> Registry:
    registry = Registry()
    for path in sorted(_SCHEMAS_DIR.glob("*.json")):
        with path.open(encoding="utf-8") as fh:
            contents = json.load(fh)
        resource = Resource.from_contents(contents)
        registry = registry.with_resource(path.name, resource)
        schema_id = contents.get("$id")
        if schema_id:
            registry = registry.with_resource(schema_id, resource)
    return registry


def validate_artifact(instance: dict[str, Any], schema_name: str) -> None:
    schema = load_schema(schema_name)
    validator = jsonschema.Draft202012Validator(schema, registry=_schema_registry())
    validator.validate(instance)
