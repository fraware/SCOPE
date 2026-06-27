"""Evaluation metrics helpers."""

from __future__ import annotations

from scope.policy import PolicyStore
from scope.quality import analyze_ledger


def compute_metrics(events: list, policy_dir: str = "policy/") -> dict:
    policy = PolicyStore.from_dir(policy_dir)
    return analyze_ledger(events, policy)
