"""Optional live validation against sibling PF-Core and PCS repositories."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

PF_CORE_REPO_ENV = "PF_CORE_REPO_PATH"
PCS_CORE_REPO_ENV = "PCS_CORE_REPO_PATH"
AKTA_REPO_ENV = "AKTA_REPO_PATH"

PF_VALIDATOR_CANDIDATES = (
    "scripts/validate_scope_obligation.py",
    "tools/validate_scope_obligation.py",
    "tests/fixtures/validate_scope_obligation.py",
)

PCS_VALIDATOR_CANDIDATES = (
    "scripts/validate_scope_artifact.py",
    "tools/validate_scope_artifact.py",
    "tests/fixtures/validate_scope_artifact.py",
)


def repo_path(env_var: str) -> Path | None:
    raw = os.environ.get(env_var)
    if not raw:
        return None
    path = Path(raw)
    if not path.is_dir():
        return None
    return path


def pf_core_repo_path() -> Path | None:
    return repo_path(PF_CORE_REPO_ENV)


def pcs_core_repo_path() -> Path | None:
    return repo_path(PCS_CORE_REPO_ENV)


def _find_validator(repo: Path, candidates: tuple[str, ...]) -> Path | None:
    for relative in candidates:
        candidate = repo / relative
        if candidate.is_file():
            return candidate
    return None


def _run_validator(script: Path, args: list[str]) -> tuple[bool, str]:
    completed = subprocess.run(
        [sys.executable, str(script), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode == 0:
        return True, completed.stdout.strip() or "Live validation passed."
    detail = (completed.stderr or completed.stdout or "validator failed").strip()
    return False, detail


def validate_pf_export_live(
    pf_obligation: dict[str, Any],
    grant: dict[str, Any],
    *,
    tmp_dir: Path | None = None,
) -> tuple[bool, str]:
    repo = pf_core_repo_path()
    if repo is None:
        return False, f"Skipped: {PF_CORE_REPO_ENV} not set or path missing"
    validator = _find_validator(repo, PF_VALIDATOR_CANDIDATES)
    if validator is None:
        return False, f"Skipped: no PF validator found under {repo}"
    work = tmp_dir or Path(".scope/live_validation")
    work.mkdir(parents=True, exist_ok=True)
    pf_path = work / "pf_obligation.json"
    grant_path = work / "scope_grant.json"
    pf_path.write_text(json.dumps(pf_obligation, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    grant_path.write_text(json.dumps(grant, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    ok, message = _run_validator(validator, [str(pf_path), str(grant_path)])
    prefix = "PF live validation"
    return ok, f"{prefix}: {message}" if message else prefix


def validate_pcs_export_live(out_dir: str | Path) -> tuple[bool, str]:
    repo = pcs_core_repo_path()
    if repo is None:
        return False, f"Skipped: {PCS_CORE_REPO_ENV} not set or path missing"
    validator = _find_validator(repo, PCS_VALIDATOR_CANDIDATES)
    if validator is None:
        return False, f"Skipped: no PCS validator found under {repo}"
    ok, message = _run_validator(validator, [str(out_dir)])
    prefix = "PCS live validation"
    return ok, f"{prefix}: {message}" if message else prefix
