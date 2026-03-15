from __future__ import annotations

import hashlib
import pathlib
from typing import cast


def cast_to_pathlib_path(value: str | pathlib.Path) -> pathlib.Path:
    """
    Cast passed in string to an instance of `pathlib.Path`.
    """
    if isinstance(value, pathlib.Path):
        return value
    return pathlib.Path(str(value))


def file_digest(path: pathlib.Path) -> bytes:
    """
    Return a SHA256 digest of a file.
    """
    with path.open("rb") as rfh:
        try:
            digest = hashlib.file_digest(rfh, "sha256")  # type: ignore[attr-defined]
        except AttributeError:
            # Python < 3.11
            buf = bytearray(2**18)  # Reusable buffer to reduce allocations.
            view = memoryview(buf)
            digest = hashlib.sha256()
            while True:
                size = rfh.readinto(buf)
                if size == 0:
                    break  # EOF
                digest.update(view[:size])
    return cast(bytes, digest.digest())
