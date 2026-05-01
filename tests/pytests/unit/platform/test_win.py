import base64

import pytest

import salt.utils.platform

if salt.utils.platform.is_windows():
    from salt.platform import win

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.skip_unless_on_windows,
]


@pytest.mark.parametrize(
    "command, expected",
    [
        ("whoami", "cmd.exe /c whoami"),
        ("cmd /c hostname", "cmd.exe /c cmd /c hostname"),
        ("echo foo", "cmd.exe /c echo foo"),
        ('cmd /c "echo foo"', 'cmd.exe /c cmd /c "echo foo"'),
        ("icacls 'C:\\Program Files'", "cmd.exe /c icacls 'C:\\Program Files'"),
        (
            "icacls 'C:\\Program Files' && echo 1",
            "cmd.exe /c icacls 'C:\\Program Files' && echo 1",
        ),
        (
            ["secedit", "/export", "/cfg", "C:\\A Path\\with\\a\\space"],
            'cmd.exe /c secedit /export /cfg "C:\\A Path\\with\\a\\space"',
        ),
        (
            ["C:\\a space\\a space.bat", "foo foo", "bar bar"],
            'cmd.exe /c "C:\\a space\\a space.bat" "foo foo" "bar bar"',
        ),
        (
            '''echo "&<>[]|{}^=;!'+,`~ "''',
            '''cmd.exe /c echo "&<>[]|{}^=;!'+,`~ "''',
        ),
    ],
)
def test_prepend_cmd(command, expected):
    """
    Test that the command is prepended with "cmd /c" and quoted
    """
    win_shell = "cmd.exe"
    result = win.prepend_cmd(win_shell, command)
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
    result = win.prepend_cmd(win_shell, command)

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
