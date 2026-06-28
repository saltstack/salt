import ctypes
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


def _invoke_conv_with_message(msg_style, password=b"sekret"):
    """
    Drive ``_authenticate``'s conversation callback with a single message of
    the requested style and return the populated ``PamResponse`` array along
    with the conv's return code.

    The conv is created inside ``_authenticate`` as a closure, so we capture
    the ``PamConv`` argument that ``_authenticate`` passes to ``PAM_START``
    and invoke its ``.conv`` callback directly with a fake messages array.
    """
    captured = {}

    def fake_pam_start(service, username, conv_ptr, handle_ptr):
        # conv_ptr is a POINTER(PamConv); keep the conv callback alive on the
        # PamConv structure it points at by stashing a reference.
        captured["conv"] = conv_ptr.contents.conv
        return 0

    def fake_pam_authenticate(handle, flags):
        conv = captured["conv"]

        # Build a single PamMessage of the requested style.
        msg = salt.auth.pam.PamMessage()
        msg.msg_style = msg_style
        msg.msg = (
            b"Username: "
            if msg_style == salt.auth.pam.PAM_PROMPT_ECHO_ON
            else b"Password: "
        )

        # messages is POINTER(POINTER(PamMessage)) — a length-1 array of
        # PamMessage pointers.
        MsgArray = ctypes.POINTER(salt.auth.pam.PamMessage) * 1
        msg_array = MsgArray(ctypes.pointer(msg))
        messages = ctypes.cast(
            msg_array, ctypes.POINTER(ctypes.POINTER(salt.auth.pam.PamMessage))
        )

        # p_response is POINTER(POINTER(PamResponse)) — a length-1 array of
        # PamResponse pointers that the conv populates via CALLOC.
        RespArray = ctypes.POINTER(salt.auth.pam.PamResponse) * 1
        resp_array = RespArray()
        p_response = ctypes.cast(
            resp_array, ctypes.POINTER(ctypes.POINTER(salt.auth.pam.PamResponse))
        )

        rc = conv(1, messages, p_response, None)
        captured["rc"] = rc
        captured["resp"] = p_response[0][0] if p_response[0] else None
        # Return PAM_AUTH_ERR (7) if the conv failed to fill a response slot
        # for a prompt that needed one, so that ``_authenticate`` returns
        # False — mirroring how real PAM handles a NULL response from the
        # conversation function.
        if captured["resp"] is None or captured["resp"].resp in (None, b""):
            return 7
        return 0

    with patch("salt.auth.pam.PAM_START", side_effect=fake_pam_start), patch(
        "salt.auth.pam.PAM_AUTHENTICATE", side_effect=fake_pam_authenticate
    ), patch("salt.auth.pam.PAM_ACCT_MGMT", return_value=0), patch(
        "salt.auth.pam.PAM_END", return_value=0
    ):
        result = salt.auth.pam._authenticate(
            username="fnord",
            password=password.decode() if isinstance(password, bytes) else password,
            service="login",
            encoding="utf-8",
        )

    return result, captured


def test_my_conv_handles_pam_prompt_echo_on_69304():
    """
    Regression test for issue #69304.

    Some PAM modules (e.g. ``pam_unix.so`` in certain configurations) send a
    ``PAM_PROMPT_ECHO_ON`` message during the conversation — typically a
    username re-prompt. Salt's conversation callback used to only populate a
    response for ``PAM_PROMPT_ECHO_OFF`` and left the ECHO_ON response slot
    NULL, which caused ``pam_authenticate`` to return non-zero with no
    diagnostic and salt-api to respond with 401.

    Assert that ``my_conv`` answers a ``PAM_PROMPT_ECHO_ON`` prompt with the
    username (echoed input), so that authentication does not silently fail
    in that case.
    """
    result, captured = _invoke_conv_with_message(
        salt.auth.pam.PAM_PROMPT_ECHO_ON, password=b"sekret"
    )

    # The conv itself should still return PAM_SUCCESS.
    assert captured["rc"] == 0
    # The response slot for the ECHO_ON prompt must be populated with the
    # username. Prior to the fix the conv left it as the CALLOC-zeroed NULL
    # pointer.
    assert captured["resp"] is not None
    assert captured["resp"].resp == b"fnord"
    # And _authenticate should therefore return True overall.
    assert result is True


def test_my_conv_handles_pam_prompt_echo_off():
    """
    Sanity check that the existing ECHO_OFF (password) path still answers
    with the password. Guards against the fix accidentally regressing the
    password-prompt path.
    """
    result, captured = _invoke_conv_with_message(
        salt.auth.pam.PAM_PROMPT_ECHO_OFF, password=b"sekret"
    )

    assert captured["rc"] == 0
    assert captured["resp"] is not None
    assert captured["resp"].resp == b"sekret"
    assert result is True
