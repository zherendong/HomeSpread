"""Private, durable local files. User data never shares the application bundle."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


def private_directory(path: Path) -> None:
    """Create an application-owned directory and reject redirected final paths."""
    if path.is_symlink():
        raise OSError("Application data directory must not be a symbolic link")
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.name == "posix":
        path.chmod(0o700)


def sync_directory(path: Path) -> None:
    if os.name == "posix":
        fd = os.open(path, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def atomic_private_write(path: Path, data: bytes, *, replace: bool = False) -> None:
    """Publish a fully flushed 0600 file; default refuses an existing destination.

    A same-directory temporary file keeps publication atomic. Hard-link publication
    has create-if-absent semantics, so even a collision cannot replace an old backup.
    """
    fd, name = tempfile.mkstemp(prefix=".writing-", dir=path.parent)
    pending = Path(name)
    published = False
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        if replace:
            if path.is_symlink():
                raise OSError("Refusing to replace a symbolic link")
            os.replace(pending, path)
        else:
            os.link(pending, path)
            published = True
        sync_directory(path.parent)
    except BaseException:
        if published:
            path.unlink(missing_ok=True)
        raise
    finally:
        pending.unlink(missing_ok=True)
