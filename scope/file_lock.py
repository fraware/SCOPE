"""Cross-platform advisory file locks for queue and session artifacts."""

from __future__ import annotations

import os
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_STALE_SECONDS = 300


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class FileLockError(OSError):
    """Raised when a lock cannot be acquired."""


class FileLock:
    """PID-based lock file with stale-lock recovery."""

    def __init__(
        self,
        path: str | Path,
        *,
        stale_seconds: int = DEFAULT_STALE_SECONDS,
    ) -> None:
        self.path = Path(path)
        self.stale_seconds = stale_seconds

    def _is_stale(self, content: str) -> bool:
        lines = content.strip().splitlines()
        if len(lines) < 2:
            return True
        try:
            ts = datetime.fromisoformat(lines[1].replace("Z", "+00:00"))
        except ValueError:
            return True
        age = (datetime.now(timezone.utc) - ts).total_seconds()
        return age > self.stale_seconds

    def _pid_alive(self, pid: int) -> bool:
        if pid <= 0:
            return False
        if os.name == "nt":
            try:
                import ctypes

                PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
                handle = ctypes.windll.kernel32.OpenProcess(
                    PROCESS_QUERY_LIMITED_INFORMATION, False, pid
                )
                if handle:
                    ctypes.windll.kernel32.CloseHandle(handle)
                    return True
                return False
            except Exception:
                return False
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False

    def acquire(self, *, timeout: float = 10.0, poll_interval: float = 0.05) -> None:
        deadline = time.monotonic() + timeout
        while True:
            try:
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                with os.fdopen(fd, "w", encoding="utf-8") as fh:
                    fh.write(f"{os.getpid()}\n{_utc_now_iso()}\n")
                return
            except FileExistsError:
                try:
                    existing = self.path.read_text(encoding="utf-8")
                except OSError:
                    existing = ""
                if existing:
                    first_line = existing.splitlines()[0] if existing.splitlines() else "0"
                    try:
                        holder_pid = int(first_line)
                    except ValueError:
                        holder_pid = 0
                    if not self._pid_alive(holder_pid) or self._is_stale(existing):
                        try:
                            self.path.unlink(missing_ok=True)
                        except OSError:
                            pass
                        continue
                if time.monotonic() >= deadline:
                    raise FileLockError(f"Could not acquire lock: {self.path}") from None
                time.sleep(poll_interval)

    def release(self) -> None:
        try:
            if self.path.exists():
                content = self.path.read_text(encoding="utf-8")
                first_line = content.splitlines()[0] if content.splitlines() else "0"
                if int(first_line) == os.getpid():
                    self.path.unlink(missing_ok=True)
        except (OSError, ValueError):
            pass

    @contextmanager
    def hold(self, *, timeout: float = 10.0) -> Iterator[None]:
        self.acquire(timeout=timeout)
        try:
            yield
        finally:
            self.release()


def lock_path_for(artifact_path: str | Path) -> Path:
    return Path(str(artifact_path) + ".lock")
