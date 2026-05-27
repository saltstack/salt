"""
Fixtures for cmd functional tests only (narrow blast radius vs package conftest).

``cmd.run`` / ``cmd.script`` with ``runas`` must execute scripts from a directory
that the alternate account can traverse and read. The package ``state_tree``
fixture lives under pytest's basetemp (e.g. ``/tmp/pytest-of-...`` on Linux),
which is typically owned by the user running pytest and not traversable by
another local user, so ``PermissionError`` can occur when the minion runs the
command as ``runas``.

``state_tree_for_runas`` yields a separate directory for the lifetime of the
module: on Windows, under ``C:\\Windows\\Temp`` with ``icacls`` grants for
``BUILTIN\\Users``; on POSIX, under ``tempfile.gettempdir()`` with mode ``0o755``
so other accounts can enter the directory and execute scripts placed there.
Tests that do not use ``runas`` should keep using ``state_tree`` only.
"""

from __future__ import annotations

import pathlib
import shutil
import subprocess
import tempfile
import uuid

import pytest

import salt.utils.platform


def _windows_runas_accessible_dir() -> pathlib.Path:
    """
    Create a throwaway directory under ``C:\\Windows\\Temp`` for ``runas`` tests.

    The package ``state_tree`` lives under the minion/pytest temp layout; other
    local accounts (including the account created for ``runas``) may not have
    traverse/read rights there. ``C:\\Windows\\Temp`` plus an ``icacls`` grant
    for ``BUILTIN\\Users`` with (OI)(CI)(RX) ensures the runas user can reach and
    execute scripts placed under this directory without loosening the whole
    machine temp.
    """
    d = pathlib.Path(r"C:\Windows\Temp") / f"salt-cmd-runas-{uuid.uuid4().hex}"
    d.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "icacls",
            str(d),
            "/grant",
            "*S-1-5-32-545:(OI)(CI)(RX)",  # BUILTIN\Users; inherit
        ],
        check=True,
    )
    return d


def _posix_runas_accessible_dir() -> pathlib.Path:
    """
    Create a throwaway directory outside pytest's tree for ``runas`` tests.

    Pytest's ``state_tree`` / ``tmp_path_factory`` paths are not suitable when
    the minion executes a file as another local user: the runas user must be
    able to traverse each path component. A directory under the system temp with
    ``0o755`` allows that without opening the whole tree to world-writable
    access.
    """
    path = pathlib.Path(tempfile.gettempdir()) / f"salt-cmd-runas-{uuid.uuid4().hex}"
    path.mkdir(parents=True)
    path.chmod(0o755)
    return path


@pytest.fixture(scope="module")
def state_tree_for_runas(state_tree):
    """
    Writable tree root for cmd tests that pass ``runas=``.

    Depends on ``state_tree`` so the rest of the functional cmd stack is
    initialized in the same order as before, but the yielded path is **not**
    the package ``state_tree`` path on POSIX (or Windows): it is a dedicated
    directory where an alternate local account can read and execute files for the
    module. Destroyed in ``finally`` after the module finishes.

    Use case: ``cmd.run`` / ``cmd.script`` with ``runas`` and scripts created
    via ``pytest.helpers.temp_file(..., state_tree_for_runas)``.
    """
    if salt.utils.platform.is_windows():
        path = _windows_runas_accessible_dir()
    else:
        path = _posix_runas_accessible_dir()
    try:
        yield path
    finally:
        shutil.rmtree(str(path), ignore_errors=True)
