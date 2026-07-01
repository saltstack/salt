"""
Helpers for :mod:`tarfile` across Python versions.

Python 3.12 added optional extraction filters (PEP 706). Passing
``filter='data'`` limits surprising or unsafe features when unpacking
archives from less trusted sources.
"""

from __future__ import annotations

import sys
import tarfile


def extractall(
    tar: tarfile.TarFile,
    path: str = "",
    members=None,
    *,
    numeric_owner: bool = False,
) -> None:
    """
    Like :meth:`tarfile.TarFile.extractall` but use ``filter='data'`` on
    Python 3.12+ when supported.
    """
    if sys.version_info >= (3, 12) and isinstance(tar, tarfile.TarFile):
        tar.extractall(  # nosec B202
            path,
            members,
            numeric_owner=numeric_owner,
            filter="data",
        )
    elif members is not None or numeric_owner:
        tar.extractall(path, members, numeric_owner=numeric_owner)  # nosec B202
    else:
        tar.extractall(path)  # nosec B202


def extract(
    tar: tarfile.TarFile,
    member,
    path: str = "",
    *,
    set_attrs: bool = True,
    numeric_owner: bool = False,
) -> None:
    """
    Like :meth:`tarfile.TarFile.extract` but use ``filter='data'`` on
    Python 3.12+ when supported.
    """
    if sys.version_info >= (3, 12) and isinstance(tar, tarfile.TarFile):
        tar.extract(  # nosec B202
            member,
            path,
            set_attrs=set_attrs,
            numeric_owner=numeric_owner,
            filter="data",
        )
    elif not set_attrs or numeric_owner:
        tar.extract(  # nosec B202
            member,
            path,
            set_attrs=set_attrs,
            numeric_owner=numeric_owner,
        )
    else:
        tar.extract(member, path)  # nosec B202
