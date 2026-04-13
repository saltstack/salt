"""
Test the win_runas util
"""

import os
import shutil
import uuid
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


@pytest.fixture(scope="function")
def _public_temp_subdir():
    """
    Directory under %SystemRoot%\\Temp that the runas test user can access.

    tempfile.TemporaryDirectory() lives under the current user's profile; the
    alternate account used by win_runas often cannot cd there. If cd fails,
    ``dir /b`` runs in a large directory, fills the stdout pipe, and the child
    blocks while win_runas waits on the process before reading stdout (deadlock).
    """
    base = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "Temp")
    path = os.path.join(base, f"salt_runas_cd_{uuid.uuid4().hex}")
    os.makedirs(path, exist_ok=False)
    yield path
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


def test_runas_cd_ampersand_dir(user, _public_temp_subdir):
    """
    ``cd /d ... & dir`` must run both parts in the same cmd /c line under runas
    (regression for CreateProcessWithTokenW command-line parsing).
    """
    tmpdir = _public_temp_subdir
    marker = "salt_runas_cd_dir_marker.txt"
    marker_path = os.path.join(tmpdir, marker)
    with open(marker_path, "w", encoding="utf-8") as f:
        f.write("x")
    inner = f'cd /d "{tmpdir}" & dir /b'
    result = win_runas.runas(
        cmd=salt.platform.win.prepend_cmd("cmd", inner),
        username=user.username,
        password=user.password,
    )
    assert result["retcode"] == 0, result
    lines = [line.strip() for line in result["stdout"].splitlines() if line.strip()]
    assert marker in lines, (result["stdout"], lines)


def test_runas_unpriv_cd_ampersand_dir(user, _public_temp_subdir):
    tmpdir = _public_temp_subdir
    marker = "salt_runas_cd_dir_marker_unpriv.txt"
    marker_path = os.path.join(tmpdir, marker)
    with open(marker_path, "w", encoding="utf-8") as f:
        f.write("x")
    inner = f'cd /d "{tmpdir}" & dir /b'
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
