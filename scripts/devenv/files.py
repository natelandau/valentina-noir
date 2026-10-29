"""File helpers shared by the dev tooling."""

import os
from pathlib import Path


def write_private(path: Path, text: str) -> None:
    """Write a file readable only by its owner, for files that hold raw keys.

    The file is replaced atomically, so readers and an interrupted write never see a partial
    file.

    Args:
        path: Destination. Parent directories are created.
        text: File contents.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        # Create with 0600 up front so the secret is never briefly world-readable
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            # A rename publishes only bytes already on disk, so a crash cannot leave an empty file
            handle.flush()
            os.fsync(handle.fileno())
        # os.open keeps the mode of a leftover temp file that already exists
        tmp.chmod(0o600)
        tmp.replace(path)
    finally:
        tmp.unlink(missing_ok=True)
