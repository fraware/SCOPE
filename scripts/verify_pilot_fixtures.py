#!/usr/bin/env python3
"""Offline verification of examples/pilot fixture pack (SCOPE-4)."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
PILOT = ROOT / "examples" / "pilot"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def file_sha256(path: Path) -> str:
    data = path.read_bytes()
    if path.suffix.lower() == ".json":
        data = data.replace(b"\r\n", b"\n")
    digest = hashlib.sha256()
    digest.update(data)
    return f"sha256:{digest.hexdigest()}"
def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _verify_checksums(
    scenario_dir: Path,
    expected: dict[str, Any],
    errors: list[str],
) -> None:
    for rel_path, expected_hash in (expected.get("checksums") or {}).items():
        artifact = scenario_dir / rel_path
        if not artifact.is_file():
            errors.append(f"{scenario_dir.name}: missing checksum target {rel_path}")
            continue
        actual = file_sha256(artifact)
        if actual != expected_hash:
            errors.append(
                f"{scenario_dir.name}: checksum mismatch for {rel_path} "
                f"(expected {expected_hash}, got {actual})"
            )


def _verify_summary(scenario_dir: Path, expected: dict[str, Any], errors: list[str]) -> None:
    summary_spec = expected.get("summary")
    if not summary_spec:
        return
    summary_path = scenario_dir / "summary.json"
    if not summary_path.is_file():
        errors.append(f"{scenario_dir.name}: summary.json required but missing")
        return
    summary = _load_json(summary_path)
    status = summary_spec.get("status")
    if status and summary.get("status") != status:
        errors.append(
            f"{scenario_dir.name}: summary.status expected {status!r}, "
            f"got {summary.get('status')!r}"
        )
    for key, value in summary_spec.items():
        if key == "status":
            continue
        if summary.get(key) != value:
            errors.append(
                f"{scenario_dir.name}: summary.{key} expected {value!r}, "
                f"got {summary.get(key)!r}"
            )
    from scope.akta_review import validate_summary_artifact

    try:
        validate_summary_artifact(summary)
    except Exception as exc:
        errors.append(f"{scenario_dir.name}: summary schema validation failed: {exc}")


def _verify_quality_snippet(
    scenario_dir: Path,
    expected: dict[str, Any],
    errors: list[str],
) -> None:
    snippet_spec = expected.get("quality_report_snippet")
    if not snippet_spec:
        return
    snippet_path = scenario_dir / "quality_report_snippet.json"
    if not snippet_path.is_file():
        errors.append(f"{scenario_dir.name}: quality_report_snippet.json missing")
        return
    snippet = _load_json(snippet_path)
    for key, value in snippet_spec.items():
        if snippet.get(key) != value:
            errors.append(
                f"{scenario_dir.name}: quality_report_snippet.{key} expected "
                f"{value!r}, got {snippet.get(key)!r}"
            )


def _verify_queue_states(
    scenario_dir: Path,
    expected: dict[str, Any],
    errors: list[str],
) -> None:
    from scope.schema_util import validate_artifact

    for rel_path, queue_spec in (expected.get("queue_states") or {}).items():
        queue_path = scenario_dir / rel_path
        if not queue_path.is_file():
            errors.append(f"{scenario_dir.name}: queue artifact missing {rel_path}")
            continue
        queue = _load_json(queue_path)
        validate_artifact(queue, "scope_review_queue.schema.json")
        for key, value in queue_spec.items():
            if queue.get(key) != value:
                errors.append(
                    f"{scenario_dir.name}: {rel_path}.{key} expected {value!r}, "
                    f"got {queue.get(key)!r}"
                )


def _verify_artifacts(
    scenario_dir: Path,
    manifest: dict[str, Any],
    expected: dict[str, Any],
    errors: list[str],
) -> None:
    from scope.schema_util import validate_artifact

    forbidden = set(expected.get("forbidden_files") or [])
    for rel in forbidden:
        if (scenario_dir / rel).exists():
            errors.append(f"{scenario_dir.name}: forbidden artifact present: {rel}")

    for entry in manifest.get("artifacts") or []:
        rel_path = entry["path"]
        artifact_path = scenario_dir / rel_path
        if not artifact_path.is_file():
            errors.append(f"{scenario_dir.name}: missing artifact {rel_path}")
            continue
        schema = entry.get("schema")
        if schema and rel_path.endswith(".json"):
            try:
                validate_artifact(_load_json(artifact_path), schema)
            except Exception as exc:
                errors.append(
                    f"{scenario_dir.name}: schema validation failed for {rel_path}: {exc}"
                )


def verify_scenario(scenario_dir: Path) -> list[str]:
    errors: list[str] = []
    manifest_path = scenario_dir / "manifest.json"
    expected_path = scenario_dir / "expected_verification.json"
    if not manifest_path.is_file():
        return [f"{scenario_dir.name}: missing manifest.json"]
    if not expected_path.is_file():
        return [f"{scenario_dir.name}: missing expected_verification.json"]

    manifest = _load_json(manifest_path)
    expected = _load_json(expected_path)

    if manifest.get("scenario") != scenario_dir.name:
        errors.append(
            f"{scenario_dir.name}: manifest.scenario mismatch "
            f"({manifest.get('scenario')!r})"
        )

    _verify_artifacts(scenario_dir, manifest, expected, errors)
    _verify_checksums(scenario_dir, expected, errors)
    _verify_summary(scenario_dir, expected, errors)
    _verify_quality_snippet(scenario_dir, expected, errors)
    _verify_queue_states(scenario_dir, expected, errors)
    return errors


def main() -> int:
    if not PILOT.is_dir():
        print(f"pilot directory not found: {PILOT}", file=sys.stderr)
        return 1

    scenario_dirs = sorted(
        path for path in PILOT.iterdir() if path.is_dir() and (path / "manifest.json").exists()
    )
    if not scenario_dirs:
        print("no pilot scenarios with manifest.json found", file=sys.stderr)
        return 1

    all_errors: list[str] = []
    passed = 0
    for scenario_dir in scenario_dirs:
        errors = verify_scenario(scenario_dir)
        if errors:
            all_errors.extend(errors)
        else:
            passed += 1
            print(f"OK  {scenario_dir.name}")

    if all_errors:
        print(f"\n{len(all_errors)} verification error(s):", file=sys.stderr)
        for err in all_errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    print(f"\nAll {passed} pilot fixture(s) verified.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
