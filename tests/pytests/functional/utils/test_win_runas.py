"""
Test the win_runas util
"""

import os
import shutil
import subprocess
import uuid
from pathlib import Path
from random import randint

import pytest

import salt.modules.win_useradd as win_useradd
import salt.utils.win_runas as win_runas

try:
    import salt.platform.win

    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.skip_unless_on_windows,
    pytest.mark.skipif(HAS_WIN32 is False, reason="Win32 Libraries not available"),
]


@pytest.fixture
def user():
    with pytest.helpers.create_account() as account:
        yield account


@pytest.fixture
def int_user():
    with pytest.helpers.create_account() as account:
        int_name = randint(10000, 99999)
        win_useradd.rename(account.username, int_name)
        account.username = int_name
        yield account


@pytest.fixture
def runas_accessible_dir(user):
    """
    Directory under %SystemRoot%\\Temp with ACLs for ``user`` (pytest's
    ``tmp_path`` is often in another account's profile, so ``cd`` as that user
    would fail for compound ``cd ... & dir`` tests).
    """
    root = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "Temp")
    path = os.path.join(root, f"salt-runas-cd-{uuid.uuid4().hex}")
    os.mkdir(path)
    machine = os.environ.get("COMPUTERNAME", ".")
    grantee = f"{machine}\\{user.username}"
    proc = subprocess.run(
        ["icacls", path, "/grant", f"{grantee}:(OI)(CI)F"],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        try:
            os.rmdir(path)
        except OSError:
            pass
        pytest.fail(
            f"icacls failed to grant {grantee} on {path}: {proc.stdout} {proc.stderr}"
        )
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


@pytest.mark.parametrize(
    "cmd, expected",
    [
        ("hostname && whoami", "username"),
        ("hostname & echo foo", "foo"),
        ("hostname & python --version", "Python"),
    ],
)
def test_compound_runas(user, cmd, expected):
    if expected == "username":
        expected = user.username
    result = win_runas.runas(
        cmd=salt.platform.win.prepend_cmd("cmd", cmd),
        username=user.username,
        password=user.password,
    )
    assert expected in result["stdout"]


@pytest.mark.parametrize(
    "cmd, expected",
    [
        ("hostname && whoami", "username"),
        ("hostname & echo foo", "foo"),
        ("hostname & python --version", "Python"),
    ],
)
def test_compound_runas_unpriv(user, cmd, expected):
    if expected == "username":
        expected = user.username
    result = win_runas.runas_unpriv(
        cmd=salt.platform.win.prepend_cmd("cmd", cmd),
        username=user.username,
        password=user.password,
    )
    assert expected in result["stdout"]


def test_runas_cd_ampersand_dir(user, runas_accessible_dir):
    # ``cd /d ... & dir`` on one cmd /c line (CreateProcessWithTokenW command line)
    marker = "salt_runas_cd_dir_marker.txt"
    Path(runas_accessible_dir, marker).write_text("x", encoding="utf-8")
    inner = f'cd /d "{runas_accessible_dir}" & dir /b'
    result = win_runas.runas(
        cmd=salt.platform.win.prepend_cmd("cmd", inner),
        username=user.username,
        password=user.password,
    )
    assert result["retcode"] == 0, result
    lines = [line.strip() for line in result["stdout"].splitlines() if line.strip()]
    assert marker in lines, (result["stdout"], lines)


def test_runas_unpriv_cd_ampersand_dir(user, runas_accessible_dir):
    marker = "salt_runas_cd_dir_marker_unpriv.txt"
    Path(runas_accessible_dir, marker).write_text("x", encoding="utf-8")
    inner = f'cd /d "{runas_accessible_dir}" & dir /b'
    result = win_runas.runas_unpriv(
        cmd=salt.platform.win.prepend_cmd("cmd", inner),
        username=user.username,
        password=user.password,
    )
    assert result["retcode"] == 0, result
    lines = [line.strip() for line in result["stdout"].splitlines() if line.strip()]
    assert marker in lines, (result["stdout"], lines)


def test_runas_str_user(user):
    result = win_runas.runas(
        cmd="whoami", username=user.username, password=user.password
    )
    assert user.username in result["stdout"]


def test_runas_int_user(int_user):
    result = win_runas.runas(
        cmd="whoami", username=int(int_user.username), password=int_user.password
    )
    assert str(int_user.username) in result["stdout"]


def test_runas_unpriv_str_user(user):
    result = win_runas.runas_unpriv(
        cmd="whoami", username=user.username, password=user.password
    )
    assert user.username in result["stdout"]


def test_runas_unpriv_int_user(int_user):
    result = win_runas.runas_unpriv(
        cmd="whoami", username=int(int_user.username), password=int_user.password
    )
    assert str(int_user.username) in result["stdout"]
