"""Tests for public-key-only reviewer registry (v0.5.1)."""

from __future__ import annotations

import shutil
from pathlib import Path

import yaml

from scope.key_registry import migrate_reviewer_registry, register_reviewer_key
from scope.signing import Ed25519Signer

ROOT = Path(__file__).resolve().parent.parent


def test_register_stores_public_key_only(tmp_path):
    policy_copy = tmp_path / "policy"
    shutil.copytree(ROOT / "policy", policy_copy)
    key = tmp_path / "reviewer.pem"
    pub = tmp_path / "reviewer.pub"
    Ed25519Signer.generate_keypair(key, pub)

    register_reviewer_key(policy_copy, "rev1", pub)
    registry = yaml.safe_load((policy_copy / "reviewer_key_registry.yaml").read_text())
    entry = registry["reviewers"]["rev1"]
    assert "public_key_ref" in entry
    assert "public_key_file" in entry
    assert "private_key_file" not in entry
    assert "private_key_path" not in entry


def test_key_register_cli_public_only(tmp_path):
    from click.testing import CliRunner

    from scope.cli import main

    policy_copy = tmp_path / "policy"
    shutil.copytree(ROOT / "policy", policy_copy)
    key = tmp_path / "reviewer.pem"
    pub = tmp_path / "reviewer.pub"
    Ed25519Signer.generate_keypair(key, pub)

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "key",
            "register",
            "--reviewer-id",
            "rev1",
            "--public-key",
            str(pub),
            "--policy",
            str(policy_copy),
        ],
    )
    assert result.exit_code == 0, result.output
    registry = yaml.safe_load((policy_copy / "reviewer_key_registry.yaml").read_text())
    assert "private_key_file" not in registry["reviewers"]["rev1"]


def test_migrate_registry_strips_private_key_fields(tmp_path):
    policy_copy = tmp_path / "policy"
    shutil.copytree(ROOT / "policy", policy_copy)
    registry_path = policy_copy / "reviewer_key_registry.yaml"
    registry = yaml.safe_load(registry_path.read_text())
    registry["reviewers"]["legacy_rev"] = {
        "public_key_ref": "sha256:deadbeef",
        "private_key_file": "keys/legacy.pem",
        "private_key_path": "/tmp/legacy.pem",
    }
    registry_path.write_text(yaml.safe_dump(registry, sort_keys=False), encoding="utf-8")

    result = migrate_reviewer_registry(policy_copy)
    assert result["removed_private_key_fields"] == 2
    assert result["changed"] is True

    cleaned = yaml.safe_load(registry_path.read_text())
    entry = cleaned["reviewers"]["legacy_rev"]
    assert "private_key_file" not in entry
    assert "private_key_path" not in entry
    assert entry["public_key_ref"] == "sha256:deadbeef"


def test_migrate_registry_cli(tmp_path):
    from click.testing import CliRunner

    from scope.cli import main

    policy_copy = tmp_path / "policy"
    shutil.copytree(ROOT / "policy", policy_copy)
    registry_path = policy_copy / "reviewer_key_registry.yaml"
    registry = yaml.safe_load(registry_path.read_text())
    registry["reviewers"]["legacy_rev"] = {
        "public_key_ref": "sha256:deadbeef",
        "private_key_file": "keys/legacy.pem",
    }
    registry_path.write_text(yaml.safe_dump(registry, sort_keys=False), encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["key", "migrate-registry", "--policy", str(policy_copy)],
    )
    assert result.exit_code == 0, result.output
    cleaned = yaml.safe_load(registry_path.read_text())
    assert "private_key_file" not in cleaned["reviewers"]["legacy_rev"]
