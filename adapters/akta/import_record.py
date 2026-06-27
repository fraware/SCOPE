"""Import AKTA records."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_akta_record(path: str | Path) -> dict[str, Any]:
    with Path(path).open(encoding="utf-8") as fh:
        return json.load(fh)
