"""Import AKTA records (flat or nested format)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from adapters.akta.field_extraction import extract_record_fields


def load_akta_record(path: str | Path) -> dict[str, Any]:
    with Path(path).open(encoding="utf-8") as fh:
        return json.load(fh)


def normalize_akta_record(record: dict[str, Any]) -> dict[str, Any]:
    """Return flat view of nested AKTA record for inspection."""
    return extract_record_fields(record)
