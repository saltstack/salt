"""
tests.pytests.unit.utils.win_dacl.test_get_name
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Test the get_name function in the win_dacl utility module
"""
# Python libs
import pytest

# Salt libs
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
]


def test_get_name_normal_name():
    """
    Test get_name when passing a normal string name
    """
    result = salt.utils.win_dacl.get_name("Administrators")
    expected = "Administrators"
    assert result == expected


def test_get_name_mixed_case():
    """
    Test get_name when passing an account name with mixed case characters
    """
    result = salt.utils.win_dacl.get_name("adMiniStrAtorS")
    expected = "Administrators"
    assert result == expected


def test_get_name_sid():
    """
    Test get_name when passing a sid string
    """
    result = salt.utils.win_dacl.get_name("S-1-5-32-544")
    expected = "Administrators"
    assert result == expected


def test_get_name_sid_object():
    """
    Test get_name when passing a sid object
    """
    # SID Object
    sid_obj = salt.utils.win_dacl.get_sid("Administrators")
    result = salt.utils.win_dacl.get_name(sid_obj)
    expected = "Administrators"
    assert result == expected


def test_get_name_virtual_account():
    """
    Test get_name with a virtual account. Should prepend the name with
    NT Security
    """
    result = salt.utils.win_dacl.get_name("NT Service\\EventLog")
    expected = "NT Service\\EventLog"
    assert result == expected


def test_get_name_virtual_account_sid():
    """
    Test get_name with a virtual account using the sid. Should prepend the name
    with NT Security
    """
    sid = "S-1-5-80-880578595-1860270145-482643319-2788375705-1540778122"
    result = salt.utils.win_dacl.get_name(sid)
    expected = "NT Service\\EventLog"
    assert result == expected


def test_get_name_capability_sid():
    """
    Test get_name with a compatibility SID. Should return `None` as we want to
    ignore these SIDs
    """
    cap_sid = "S-1-15-3-1024-1065365936-1281604716-3511738428-1654721687-432734479-3232135806-4053264122-3456934681"
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
