import tempfile

import pytest

import salt.auth.pam
from tests.support.mock import patch

pytestmark = [
    pytest.mark.skip_on_windows,
]


@pytest.fixture
def configure_loader_modules():
    return {salt.auth.pam: {}}


@pytest.fixture
def mock_pam():
    with patch("salt.auth.pam.CALLOC", autospec=True), patch(
        "salt.auth.pam.pointer", autospec=True
    ), patch("salt.auth.pam.PamHandle", autospec=True), patch(
        "salt.auth.pam.PAM_START", autospec=True, return_value=0
    ), patch(
        "salt.auth.pam.PAM_AUTHENTICATE", autospec=True, return_value=0
    ), patch(
        "salt.auth.pam.PAM_END", autospec=True
    ):
        yield


def test_cve_if_pam_acct_mgmt_returns_nonzero_authenticate_should_be_false(mock_pam):
    with patch("salt.auth.pam.PAM_ACCT_MGMT", autospec=True, return_value=42):
        assert (
            salt.auth.pam._authenticate(
                username="fnord", password="fnord", service="login", encoding="utf-8"
            )
            is False
        )


def test_if_pam_acct_mgmt_returns_zero_authenticate_should_be_true(mock_pam):
    with patch("salt.auth.pam.PAM_ACCT_MGMT", autospec=True, return_value=0):
        assert (
            salt.auth.pam._authenticate(
                username="fnord", password="fnord", service="login", encoding="utf-8"
            )
            is True
        )


def test_if_sys_executable_is_used_to_call_pam_auth(mock_pam):
    class Ret:
        returncode = 0

    # Python 3.14 made pathlib.Path.exists() call os.path.exists internally,
    # so a global os.path.exists patch returning False also breaks the
    # ``pyexe.exists()`` guard inside ``authenticate()``. Narrow the patch to
    # only short-circuit the ``/usr/bin/python3`` lookup.
    import os

    real_exists = os.path.exists

    def fake_exists(path):
        if str(path) == "/usr/bin/python3":
            return False
        return real_exists(path)

    with patch(
        "salt.auth.pam.subprocess.run", return_value=Ret
    ) as run_mock, tempfile.NamedTemporaryFile() as f, patch(
        "salt.auth.pam.sys.executable", f.name
    ), patch(
        "os.path.exists", side_effect=fake_exists
    ):
        assert salt.auth.pam.auth(
            username="fnord", password="fnord", service="login", encoding="utf-8"
        )
        assert f.name in run_mock.call_args_list[0][0][0]


def test_bundled_install_uses_sys_executable_not_system_python_69303(mock_pam):
    """
    Regression test for #69303.

    When Salt is running from a relenv/onedir bundle, ``authenticate()`` must
    launch the PAM helper subprocess with ``sys.executable`` (Salt's bundled
    interpreter), not the system ``/usr/bin/python3``. The system Python on
    an onedir-only install does not have ``salt`` or ``python-pam``
    available, so the subprocess exits 1 and every login attempt returns
    401.
    """
    import os
    import sys

    import salt.utils.package

    class Ret:
        returncode = 0

    real_exists = os.path.exists

    # Pretend ``/usr/bin/python3`` exists (so the old heuristic would have
    # picked it) but assert we picked ``sys.executable`` anyway because
    # ``salt.utils.package.bundled()`` reports we are running from a relenv
    # onedir build.
    def fake_exists(path):
        if str(path) == "/usr/bin/python3":
            return True
        return real_exists(path)

    # Force ``bundled()`` to report we are running from an onedir/relenv
    # install. ``hasattr(sys, "RELENV")`` is the canonical relenv probe;
    # setting it for the duration of the test is the simplest knob.
    had_relenv = hasattr(sys, "RELENV")
    saved_relenv = getattr(sys, "RELENV", None)
    sys.RELENV = "/opt/saltstack/salt"
    try:
        assert salt.utils.package.bundled() is True
        with patch(
            "salt.auth.pam.subprocess.run", return_value=Ret
        ) as run_mock, tempfile.NamedTemporaryFile() as f, patch(
            "salt.auth.pam.sys.executable", f.name
        ), patch(
            "os.path.exists", side_effect=fake_exists
        ):
            assert salt.auth.pam.auth(
                username="fnord",
                password="fnord",
                service="login",
                encoding="utf-8",
            )
            called_cmd = run_mock.call_args_list[0][0][0]
            assert f.name in called_cmd, (
                f"Expected bundled Python {f.name!r} in subprocess argv, "
                f"got {called_cmd!r}. __find_pyexe() incorrectly preferred "
                "the system Python on a relenv/onedir install (regression "
                "of #69303)."
            )
            assert "/usr/bin/python3" not in called_cmd
    finally:
        if had_relenv:
            sys.RELENV = saved_relenv
        else:
            del sys.RELENV
