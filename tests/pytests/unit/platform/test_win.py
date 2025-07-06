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
        ("whoami", 'cmd.exe /c "whoami"'),
        ("cmd /c hostname", 'cmd.exe /c "cmd /c hostname"'),
        ("echo foo", 'cmd.exe /c "echo foo"'),
        ('cmd /c "echo foo"', 'cmd.exe /c "cmd /c "echo foo""'),
        ("icacls 'C:\\Program Files'", 'cmd.exe /c "icacls \'C:\\Program Files\'"'),
        (
            "icacls 'C:\\Program Files' && echo 1",
            'cmd.exe /c "icacls \'C:\\Program Files\' && echo 1"',
        ),
        (
            ["secedit", "/export", "/cfg", "C:\\A Path\\with\\a\\space"],
            'cmd.exe /c "secedit /export /cfg "C:\\A Path\\with\\a\\space""',
        ),
        (
            ["C:\\a space\\a space.bat", "foo foo", "bar bar"],
            'cmd.exe /c ""C:\\a space\\a space.bat" "foo foo" "bar bar""',
        ),
        (
            ''' echo "&<>[]|{}^=;!'+,`~ " ''',
            '''cmd.exe /c " echo "&<>[]|{}^=;!'+,`~ " "''',
        ),
    ],
)
def test_prepend_cmd(command, expected):
    """
    Test that the command is prepended with "cmd /c" and quoted
    """
    win_shell = 'cmd.exe'
    result = win.prepend_cmd(win_shell, command)
    assert result == expected
