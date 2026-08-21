"""
    :codeauthor: Rahul Handay <rahulha@saltstack.com>
"""

import pytest

import salt.states.sysrc as sysrc
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {sysrc: {}}


def test_managed():
    """
    Test to ensure a sysrc variable is set to a specific value.
    """
    ret = {"name": "salt", "changes": {}, "result": True, "comment": ""}
    mock = MagicMock(side_effect=[{"key1": {"salt": "stack"}}, None, None])
    mock1 = MagicMock(return_value=True)
    with patch.dict(sysrc.__salt__, {"sysrc.get": mock, "sysrc.set": mock1}):
        ret.update({"comment": "salt is already set to the desired value."})
        assert sysrc.managed("salt", "stack") == ret

        with patch.dict(sysrc.__opts__, {"test": True}):
            ret.update(
                {
                    "changes": {"new": "salt = stack will be set.", "old": None},
                    "comment": 'The value of "salt" will be changed!',
                    "result": None,
                }
            )
            assert sysrc.managed("salt", "stack") == ret

        with patch.dict(sysrc.__opts__, {"test": False}):
            ret.update(
                {
                    "changes": {"new": True, "old": None},
                    "comment": 'The value of "salt" was changed!',
                    "result": True,
                }
            )
            assert sysrc.managed("salt", "stack") == ret


def test_managed_test_mode_bool_value_60048():
    """
    Test mode must not raise TypeError when the value is a non-string
    (e.g. YAML coerces an unquoted ``YES`` to the bool ``True``).

    Regression test for #60048.
    """
    # sysrc.get returns None -> variable not yet set, so managed() falls
    # through to the __opts__["test"] preview branch.
    mock_get = MagicMock(return_value=None)
    with patch.dict(sysrc.__salt__, {"sysrc.get": mock_get}):
        # __opts__["test"] = True exercises the test-mode preview path.
        with patch.dict(sysrc.__opts__, {"test": True}):
            ret = sysrc.managed("vm_enable", True)
    assert ret["result"] is None
    assert ret["comment"] == 'The value of "vm_enable" will be changed!'
    assert ret["changes"] == {
        "old": None,
        "new": "vm_enable = True will be set.",
    }


def test_managed_test_mode_string_value_60048():
    """
    Inverse of the #60048 regression: a normal string value must render
    identically before and after the f-string change, so this passes both
    with and without the fix and guards against an output regression.
    """
    mock_get = MagicMock(return_value=None)
    with patch.dict(sysrc.__salt__, {"sysrc.get": mock_get}):
        with patch.dict(sysrc.__opts__, {"test": True}):
            ret = sysrc.managed("syslogd_flags", "-ss")
    assert ret["result"] is None
    assert ret["changes"] == {
        "old": None,
        "new": "syslogd_flags = -ss will be set.",
    }


def test_managed_test_mode_int_value_60048():
    """
    Peripheral coverage for the test-mode preview: an integer value
    (e.g. YAML ``value: 22``) is coerced to its string form rather than
    raising TypeError.
    """
    mock_get = MagicMock(return_value=None)
    with patch.dict(sysrc.__salt__, {"sysrc.get": mock_get}):
        with patch.dict(sysrc.__opts__, {"test": True}):
            ret = sysrc.managed("sshd_port", 22)
    assert ret["result"] is None
    assert ret["changes"]["new"] == "sshd_port = 22 will be set."


def test_absent():
    """
    Test to ensure a sysrc variable is absent.
    """
    ret = {"name": "salt", "changes": {}, "result": True, "comment": ""}
    mock = MagicMock(side_effect=[None, True, True])
    mock1 = MagicMock(return_value=True)
    with patch.dict(sysrc.__salt__, {"sysrc.get": mock, "sysrc.remove": mock1}):
        ret.update({"comment": '"salt" is already absent.'})
        assert sysrc.absent("salt") == ret

        with patch.dict(sysrc.__opts__, {"test": True}):
            ret.update(
                {
                    "changes": {"new": '"salt" will be removed.', "old": True},
                    "comment": '"salt" will be removed!',
                    "result": None,
                }
            )
            assert sysrc.absent("salt") == ret

        with patch.dict(sysrc.__opts__, {"test": False}):
            ret.update(
                {
                    "changes": {"new": True, "old": True},
                    "comment": '"salt" was removed!',
                    "result": True,
                }
            )
            assert sysrc.absent("salt") == ret
