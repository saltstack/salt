"""
tests.pytests.unit.utils.win_dacl.test_get_name
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Test the get_name function in the win_dacl utility module
"""

import pytest

import salt.exceptions
import salt.utils.win_dacl

# Third-party libs
try:
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
def test_get_name(principal):
    """
    Test get_name with various input methods
    """
    result = salt.utils.win_dacl.get_name(principal)
    expected = "Administrators"
    assert result == expected


def test_get_name_pysid_obj():
    """
    Test get_name with various input methods
    We can't parametrize this one as it gets evaluated before the test runs
    and tries to import salt.utils.win_functions on non-Windows boxes
    """
    pysid_obj = salt.utils.win_dacl.get_sid("Administrators")
    result = salt.utils.win_dacl.get_name(pysid_obj)
    expected = "Administrators"
    assert result == expected


@pytest.mark.parametrize(
    "principal",
    (
        "NT Service\\EventLog",  # Normal
        "S-1-5-80-880578595-1860270145-482643319-2788375705-1540778122",  # SID
    ),
)
def test_get_name_virtual_account(principal):
    """
    Test get_name with a virtual account. Should prepend the name with
    NT Security
    """
    result = salt.utils.win_dacl.get_name(principal)
    expected = "NT Service\\EventLog"
    assert result == expected


def test_get_name_capability_sid():
    """
    Test get_name with a compatibility SID. Should return `None` as we want to
    ignore these SIDs
    """
    cap_sid = (
        "S-1-15-3-1024-1065365936-1281604716-3511738428-1654721687-432734479-"
        "3232135806-4053264122-3456934681"
    )
    sid_obj = win32security.ConvertStringSidToSid(cap_sid)
    assert salt.utils.win_dacl.get_name(sid_obj) is None


def test_get_name_error():
    """
    Test get_name with an un mapped SID, should throw a CommandExecutionError
    """
    test_sid = "S-1-2-3-4"
    sid_obj = win32security.ConvertStringSidToSid(test_sid)
    with pytest.raises(salt.exceptions.CommandExecutionError) as exc:
        salt.utils.win_dacl.get_name(sid_obj)
    assert "No mapping between account names" in exc.value.message
