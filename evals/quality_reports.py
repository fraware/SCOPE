"""Quality report CLI helpers."""

from __future__ import annotations

from scope import ScopeEngine


def generate_report(ledger_path: str, policy_dir: str = "policy/") -> dict:
    engine = ScopeEngine.from_policy_dir(policy_dir, ledger_path=ledger_path)
    return engine.quality_report()
