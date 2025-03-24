import pytest

from salt.platform import win

pytestmark = [
    pytest.mark.windows_whitelisted,
]


@pytest.mark.parametrize(
    "command, expected",
    [
        ("whoami", "whoami"),
        ("hostname", "hostname"),
        ("cmd /c hostname", "cmd /c hostname"),
        ("echo foo", 'cmd /c "echo foo"'),
        ('cmd /c "echo foo"', 'cmd /c "echo foo"'),
        ("whoami && echo foo", 'cmd /c "whoami && echo foo"'),
        ("whoami || echo foo", 'cmd /c "whoami || echo foo"'),
    ],
)
def test_prepend_cmd(command, expected):
    """
    Test that the command is prepended with "cmd /c" where appropriate
    """
    result = win.prepend_cmd(command)
    assert result == expected
