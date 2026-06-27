"""Import AKTA review triggers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_review_trigger(path: str | Path) -> dict[str, Any]:
    with Path(path).open(encoding="utf-8") as fh:
        trigger = json.load(fh)
    if trigger.get("akta_admissibility") not in ("review_required", "authorization_required"):
        raise ValueError("AKTA trigger must require review or authorization")
    return trigger


def load_akta_record(path: str | Path) -> dict[str, Any]:
    with Path(path).open(encoding="utf-8") as fh:
        return json.load(fh)
