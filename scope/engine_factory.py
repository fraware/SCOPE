"""Per-request engine factory for REST multi-tenant operation."""

from __future__ import annotations

import os
from pathlib import Path

from scope import ScopeEngine, create_session_store


class EngineFactory:
    """Create ScopeEngine instances from request headers or environment defaults."""

    def __init__(
        self,
        *,
        default_policy_dir: str | Path | None = None,
        default_ledger_path: str | Path | None = None,
        default_session_store: str = "memory",
        default_session_dir: str | Path | None = None,
    ) -> None:
        self.default_policy_dir = (
            Path(default_policy_dir)
            if default_policy_dir
            else Path(__file__).resolve().parents[1] / "policy"
        )
        self.default_ledger_path = Path(default_ledger_path) if default_ledger_path else None
        self.default_session_store = default_session_store
        self.default_session_dir = default_session_dir
        self._engines: dict[tuple[str, str, str, str, str], ScopeEngine] = {}

    def _resolve_config(
        self, headers: dict[str, str]
    ) -> tuple[Path, str | None, str, str, str | None]:
        policy_header = headers.get("x-scope-policy-dir") or headers.get("X-Scope-Policy-Dir")
        ledger_header = headers.get("x-scope-ledger-path") or headers.get("X-Scope-Ledger-Path")
        tenant_header = headers.get("x-scope-tenant-id") or headers.get("X-Scope-Tenant-Id")
        policy_dir = Path(policy_header) if policy_header else self._env_policy_dir()
        ledger_path = ledger_header or self._env_ledger_path()
        store_type = os.environ.get("SCOPE_SESSION_STORE", self.default_session_store)
        session_dir = str(os.environ.get("SCOPE_SESSION_DIR") or self.default_session_dir or "")
        tenant_id = tenant_header or os.environ.get("SCOPE_TENANT_ID")
        return policy_dir, ledger_path, store_type, session_dir, tenant_id

    def from_headers(self, headers: dict[str, str]) -> ScopeEngine:
        policy_dir, ledger_path, store_type, session_dir, tenant_id = self._resolve_config(headers)
        cache_key = (
            str(policy_dir),
            str(ledger_path or ""),
            store_type,
            session_dir,
            str(tenant_id or ""),
        )
        cached = self._engines.get(cache_key)
        if cached is not None:
            return cached
        session_store = create_session_store(store_type, session_dir or None)
        engine = ScopeEngine.from_policy_dir(
            policy_dir,
            ledger_path=ledger_path,
            session_store=session_store,
        )
        self._engines[cache_key] = engine
        engine._tenant_id = tenant_id  # type: ignore[attr-defined]
        return engine

    def clear_cache(self) -> None:
        self._engines.clear()

    def _env_policy_dir(self) -> Path:
        raw = os.environ.get("SCOPE_POLICY_DIR")
        return Path(raw) if raw else self.default_policy_dir

    def _env_ledger_path(self) -> str | None:
        return os.environ.get("SCOPE_LEDGER_PATH") or (
            str(self.default_ledger_path) if self.default_ledger_path else None
        )

    def default_engine(self) -> ScopeEngine:
        return self.from_headers({})
