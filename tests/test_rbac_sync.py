"""Tests for RBAC sync."""

from __future__ import annotations

from pathlib import Path

import yaml

from scope.rbac_sync import build_org_rbac_from_snapshot, sync_rbac

ROOT = Path(__file__).resolve().parent.parent


def test_sync_scim_snapshot(tmp_path: Path) -> None:
    out = sync_rbac(
        source="scim",
        file_path=ROOT / "policy" / "scim_snapshot.yaml",
        policy_dir=tmp_path,
    )
    data = yaml.safe_load(out.read_text(encoding="utf-8"))
    assert "genomics_lab" in data["org_units"]
    assert "ds1" in data["org_units"]["genomics_lab"]["members"]


def test_delegation_expiry_filtered() -> None:
    snapshot = {
        "users": [{"id": "u1", "roles": ["domain_scientist"], "org_unit": "lab"}],
        "delegations": [
            {
                "delegate_reviewer_id": "u1",
                "role": "domain_scientist",
                "granted_to": "u2",
                "valid_until": "2000-01-01T00:00:00Z",
            }
        ],
    }
    org = build_org_rbac_from_snapshot(snapshot)
    assert org["delegations"] == []
