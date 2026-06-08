import base64
import ctypes
import subprocess

import pytest

import salt.utils.platform
from tests.support.mock import patch

if salt.utils.platform.is_windows():
    from salt.platform import win

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.skip_unless_on_windows,
]


@pytest.mark.parametrize(
    "command, expected",
    [
        ("whoami", 'cmd.exe /c "whoami"'),
        ("cmd /c hostname", 'cmd.exe /c "cmd /c hostname"'),
        ("echo foo", 'cmd.exe /c "echo foo"'),
        ('cmd /c "echo foo"', 'cmd.exe /c "cmd /c ""echo foo"""'),
        ("icacls 'C:\\Program Files'", "cmd.exe /c \"icacls 'C:\\Program Files'\""),
        (
            "icacls 'C:\\Program Files' && echo 1",
            "cmd.exe /c \"icacls 'C:\\Program Files' && echo 1\"",
        ),
        (
            ["secedit", "/export", "/cfg", "C:\\A Path\\with\\a\\space"],
            'cmd.exe /c "secedit /export /cfg ""C:\\A Path\\with\\a\\space"""',
        ),
        (
            ["C:\\a space\\a space.bat", "foo foo", "bar bar"],
            'cmd.exe /c """C:\\a space\\a space.bat"" ""foo foo"" ""bar bar"""',
        ),
        (
            '''echo "&<>[]|{}^=;!'+,`~ "''',
            'cmd.exe /c "echo ""&<>[]|{}^=;!\'+,`~ """',
        ),
    ],
)
def test_prepend_cmd(command, expected):
    """
    Test that the command is prepended with ``cmd /c`` and the payload is quoted
    for ``CreateProcess`` / ``CreateProcessWithTokenW`` command-line parsing.
    """
    win_shell = "cmd.exe"
    result = win.prepend_cmd(win_shell, command, quote_c_payload=True)
    assert result == expected


@pytest.mark.parametrize(
    "command, expected_block_content",
    [
        # LF line endings
        (
            "powershell -Command {\n    Write-Host 'test'\n}\n",
            "     Write-Host 'test' ",
        ),
        # CRLF line endings
        (
            "powershell -Command {\r\n    Write-Host 'test'\r\n}\r\n",
            "     Write-Host 'test' ",
        ),
        # Flags before -Command
        (
            "powershell -NoProfile -ExecutionPolicy Bypass -Command {\n    Write-Host 'test'\n}\n",
            "     Write-Host 'test' ",
        ),
    ],
)
def test_prepend_cmd_powershell_block_encoded(command, expected_block_content):
    """
    Multiline PowerShell -Command { } blocks must be converted to -EncodedCommand
    so that the script block executes (rather than being returned as a ScriptBlock
    object) when PowerShell's stdout is piped to a subprocess.
    """
    win_shell = "cmd.exe"
    result = win.prepend_cmd(win_shell, command, quote_c_payload=False)

    prefix = "cmd.exe /c "
    assert result.startswith(prefix)
    inner = result[len(prefix) :]

    # The -EncodedCommand flag must be present and -Command must not be
    assert "-EncodedCommand " in inner
    assert "-Command" not in inner

    # Decode and verify the script block content
    encoded = inner.split("-EncodedCommand ", 1)[1].strip()
    decoded = base64.b64decode(encoded).decode("utf-16-le")
    assert decoded == expected_block_content


def test_prepend_cmd_unquoted_payload():
    """
    Subprocess / ``TimedProc`` path: no outer ``_cmd_exe_cswitch_quoted_argument`` wrap.
    """
    # ``python_shell``-style: raw /c tail (``echo`` with internal quotes must not
    # be re-wrapped by ``list2cmdline``).
    assert win.prepend_cmd("cmd.exe", "echo foo", quote_c_payload=False) == (
        "cmd.exe /c echo foo"
    )
    # ``runas`` + no ``python_shell``: one path with spaces is one token.
    spaced_path = r"C:\a b\x.bat"
    assert win.prepend_cmd(
        "cmd.exe",
        spaced_path,
        quote_c_payload=False,
        msvc_quote_bare_path_string=True,
    ) == "cmd.exe /c " + subprocess.list2cmdline([spaced_path])

    result = win.prepend_cmd("cmd.exe", ["whoami.exe", "/all"], quote_c_payload=False)
    expected = "cmd.exe /c whoami.exe /all"
    assert result == expected

    # ``|``/``&`` must not be passed as one list2cmdline token (breaks pipes).
    compound = r'C:\x\p.bat | find /c /v ""'
    assert win.prepend_cmd("cmd.exe", compound, quote_c_payload=False) == (
        f"cmd.exe /c {compound}"
    )


def test_create_process_with_token_w_raises_real_error():
    """
    When the underlying advapi32 call fails, CreateProcessWithTokenW must raise
    OSError with the code from ctypes.get_last_error() (the ctypes-saved slot),
    not from win32api.GetLastError() (the live Windows slot, which may already
    be 0 by the time Python reads it).

    Regression: github.com/saltstack/salt/issues/57848
    """
    ERROR_ACCESS_DENIED = 5

    def _fake_advapi32_call(*args, **kwargs):
        ctypes.set_last_error(ERROR_ACCESS_DENIED)
        return 0  # FALSE — failure

    with patch.object(
        win.advapi32, "CreateProcessWithTokenW", side_effect=_fake_advapi32_call
    ):
        with pytest.raises(OSError) as exc_info:
            win.CreateProcessWithTokenW(token=1, commandline="whoami")

    assert exc_info.value.winerror == ERROR_ACCESS_DENIED
