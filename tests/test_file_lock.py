"""Tests for file locking."""

from __future__ import annotations

import tempfile
from pathlib import Path

from scope.file_lock import FileLock


def test_file_lock_acquire_release() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        lock_path = Path(tmp) / "test.lock"
        lock = FileLock(lock_path)
        lock.acquire()
        assert lock_path.exists()
        lock.release()
        assert not lock_path.exists()
