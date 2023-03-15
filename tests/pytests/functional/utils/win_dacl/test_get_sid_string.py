"""
tests.pytests.unit.utils.win_dacl.test_get_sid_string
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Test the get_sid_string function in the win_dacl utility module
"""
import pytest

import salt.utils.win_dacl

# Third-party libs
try:
    import pywintypes

    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.skip_unless_on_windows,
    pytest.mark.skipif(not HAS_WIN32, reason="Requires Win32 libraries"),
]


@pytest.mark.parametrize(
    "principal,expected",
    [
        ("Administrators", "S-1-5-32-544"),  # Normal
        ("adMiniStrAtorS", "S-1-5-32-544"),  # Mixed Case
        ("S-1-5-32-544", "S-1-5-32-544"),  # String SID
        (None, "S-1-0-0"),  # None SID
    ],
)
def test_get_sid_string(principal, expected):
    """
    Validate getting a sid string from a valid pysid object
    """
    sid_obj = salt.utils.win_dacl.get_sid(principal)
    assert isinstance(sid_obj, pywintypes.SIDType)
    assert salt.utils.win_dacl.get_sid_string(sid_obj) == expected
