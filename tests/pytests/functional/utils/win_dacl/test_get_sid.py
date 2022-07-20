"""
tests.pytests.unit.utils.win_dacl.test_get_sid
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Test the get_sid function in the win_dacl utility module
"""
import pytest

import salt.utils.win_dacl

# Third-party libs
try:
    import pywintypes
    import win32security

    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.skip_unless_on_windows,
    pytest.mark.skipif(not HAS_WIN32, reason="Requires Win32 libraries"),
]


@pytest.mark.parametrize(
    "principal",
    (
        "Administrators",  # Normal
        "adMiniStrAtorS",  # Mixed Case
        "S-1-5-32-544",  # String SID
    ),
)
def test_get_sid(principal):
    """
    Validate getting a pysid object with various inputs
    """
    sid_obj = salt.utils.win_dacl.get_sid(principal)
    assert isinstance(sid_obj, pywintypes.SIDType)
    assert win32security.LookupAccountSid(None, sid_obj)[0] == "Administrators"
