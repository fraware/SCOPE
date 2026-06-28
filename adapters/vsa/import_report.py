"""Import VSA ScientificReport JSON into SCOPE review artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast


def import_vsa_report(path_or_data: str | Path | dict[str, Any]) -> dict[str, Any]:
    """Load VSA ScientificReport and extract review-relevant summary fields."""
    if isinstance(path_or_data, dict):
        report = path_or_data
    else:
        path = Path(path_or_data)
        with path.open(encoding="utf-8") as fh:
            report = cast(dict[str, Any], json.load(fh))

    evidence = report.get("evidence_summary") or {}
    claims = report.get("claims") or []
    validation = report.get("validation_results") or report.get("validation") or {}

    claim_warnings: list[str] = []
    for claim in claims:
        if not isinstance(claim, dict):
            continue
        status = claim.get("status") or claim.get("validation_status")
        if status in ("unsupported", "weak", "failed", "warning"):
            claim_warnings.append(
                f"{claim.get('claim_id', 'claim')}: "
                f"{claim.get('text', claim.get('summary', status))}"
            )

    validation_results: list[dict[str, Any]] = []
    if isinstance(validation, dict):
        for key, value in validation.items():
            validation_results.append({"check": key, "result": value})
    elif isinstance(validation, list):
        validation_results = [v for v in validation if isinstance(v, dict)]

    return {
        "source": "vsa_scientific_report",
        "report_id": report.get("report_id") or report.get("id"),
        "report_version": report.get("report_version"),
        "evidence_summary": {
            "overall_state": evidence.get("overall_state") or evidence.get("evidence_state"),
            "confidence": evidence.get("confidence"),
            "supporting_artifacts": evidence.get("supporting_artifacts") or [],
        },
        "claim_warnings": claim_warnings,
        "validation_results": validation_results,
    }
