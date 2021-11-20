"""
tests.pytests.unit.utils.win_dacl.test_get_sid_string
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Test the get_sid_string function in the win_dacl utility module
"""
# Python libs
import pytest

# Salt libs
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
]


def test_get_sid_string_name():
    """
    Validate getting a sid string from a valid pysid object
    """
    sid_obj = salt.utils.win_dacl.get_sid("Administrators")
    assert isinstance(sid_obj, pywintypes.SIDType)
    assert salt.utils.win_dacl.get_sid_string(sid_obj) == "S-1-5-32-544"


def test_get_sid_string_none():
    """
    Validate getting a null sid (S-1-0-0) when a null sid is passed
    """
    sid_obj = salt.utils.win_dacl.get_sid(None)
    assert isinstance(sid_obj, pywintypes.SIDType)
    assert salt.utils.win_dacl.get_sid_string(sid_obj) == "S-1-0-0"
