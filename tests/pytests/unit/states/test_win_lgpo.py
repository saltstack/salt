"""
:codeauthor: Shane Lee <slee@saltstack.com>
"""
import copy

import pytest
import salt.config
import salt.loader
import salt.states.win_lgpo as win_lgpo
import salt.utils.platform
import salt.utils.stringutils
from tests.support.mock import patch


@pytest.fixture
def configure_loader_modules():
    opts = salt.config.DEFAULT_MINION_OPTS.copy()
    utils = salt.loader.utils(opts)
    modules = salt.loader.minion_mods(opts, utils=utils)
    return {
        win_lgpo: {
            "__opts__": copy.deepcopy(opts),
            "__salt__": modules,
            "__utils__": utils,
        }
    }


@pytest.fixture(scope="function")
def policy_clear():
    # Make sure policy is not set to begin with, unsets it after test
    try:
        computer_policy = {"Point and Print Restrictions": "Not Configured"}
        with patch.dict(win_lgpo.__opts__, {"test": False}):
            win_lgpo.set_(name="test_state", computer_policy=computer_policy)
        yield
    finally:
        computer_policy = {"Point and Print Restrictions": "Not Configured"}
        with patch.dict(win_lgpo.__opts__, {"test": False}):
            win_lgpo.set_(name="test_state", computer_policy=computer_policy)


@pytest.fixture(scope="function")
def policy_set():
    # Make sure policy is set to begin with, unsets it after test
    try:
        computer_policy = {
            "Point and Print Restrictions": {
                "Users can only point and print to these servers": True,
                "Enter fully qualified server names separated by semicolons": (
                    "fakeserver1;fakeserver2"
                ),
                "Users can only point and print to machines in their forest": True,
                "When installing drivers for a new connection": (
                    "Show warning and elevation prompt"
                ),
                "When updating drivers for an existing connection": "Show warning only",
            }
        }
        with patch.dict(win_lgpo.__opts__, {"test": False}):
            win_lgpo.set_(name="test_state", computer_policy=computer_policy)
        yield
    finally:
        computer_policy = {"Point and Print Restrictions": "Not Configured"}
        with patch.dict(win_lgpo.__opts__, {"test": False}):
            win_lgpo.set_(name="test_state", computer_policy=computer_policy)


def test__compare_policies_string():
    """
    ``_compare_policies`` should only return ``True`` when the string values
    are the same. All other scenarios should return ``False``
    """
    compare_string = "Salty test"
    # Same
    assert win_lgpo._compare_policies(compare_string, compare_string)
    # Different
    assert not win_lgpo._compare_policies(compare_string, "Not the same")
    # List
    assert not win_lgpo._compare_policies(compare_string, ["item1", "item2"])
    # Dict
    assert not win_lgpo._compare_policies(compare_string, {"key": "value"})
    # None
    assert not win_lgpo._compare_policies(compare_string, None)


def test__compare_policies_list():
    """
    ``_compare_policies`` should only return ``True`` when the lists are the
    same. All other scenarios should return ``False``
    """
    compare_list = ["Salty", "test"]
    # Same
    assert win_lgpo._compare_policies(compare_list, compare_list)
    # Different
    assert not win_lgpo._compare_policies(compare_list, ["Not", "the", "same"])
    # String
    assert not win_lgpo._compare_policies(compare_list, "Not a list")
    # Dict
    assert not win_lgpo._compare_policies(compare_list, {"key": "value"})
    # None
    assert not win_lgpo._compare_policies(compare_list, None)


def test__compare_policies_dict():
    """
    ``_compare_policies`` should only return ``True`` when the dicts are the
    same. All other scenarios should return ``False``
    """
    compare_dict = {"Salty": "test"}
    # Same
    assert win_lgpo._compare_policies(compare_dict, compare_dict)
    # Different
    assert not win_lgpo._compare_policies(compare_dict, {"key": "value"})
    # String
    assert not win_lgpo._compare_policies(compare_dict, "Not a dict")
    # List
    assert not win_lgpo._compare_policies(compare_dict, ["Not", "a", "dict"])
    # None
    assert not win_lgpo._compare_policies(compare_dict, None)


def test__compare_policies_integer():
    """
    ``_compare_policies`` should only return ``True`` when the integer
    values are the same. All other scenarios should return ``False``
    """
    compare_integer = 1
    # Same
    assert win_lgpo._compare_policies(compare_integer, compare_integer)
    # Different
    assert not win_lgpo._compare_policies(compare_integer, 0)
    # List
    assert not win_lgpo._compare_policies(compare_integer, ["item1", "item2"])
    # Dict
    assert not win_lgpo._compare_policies(compare_integer, {"key": "value"})
    # None
    assert not win_lgpo._compare_policies(compare_integer, None)


@pytest.mark.skip_unless_on_windows
@pytest.mark.destructive_test
@pytest.mark.slow_test
def test_current_element_naming_style(policy_clear):
    """
    Ensure that current naming style works properly.
    """
    computer_policy = {
        "Point and Print Restrictions": {
            "Users can only point and print to these servers": True,
            "Enter fully qualified server names separated by semicolons": (
                "fakeserver1;fakeserver2"
            ),
            "Users can only point and print to machines in their forest": True,
            "When installing drivers for a new connection": (
                "Show warning and elevation prompt"
            ),
            "When updating drivers for an existing connection": "Show warning only",
        }
    }
    with patch.dict(win_lgpo.__opts__, {"test": False}):
        result = win_lgpo.set_(name="test_state", computer_policy=computer_policy)
        result = win_lgpo._convert_to_unicode(result)
    expected = {
        "Point and Print Restrictions": {
            "Enter fully qualified server names separated by semicolons": (
                "fakeserver1;fakeserver2"
            ),
            "When installing drivers for a new connection": (
                "Show warning and elevation prompt"
            ),
            "Users can only point and print to machines in their forest": True,
            "Users can only point and print to these servers": True,
            "When updating drivers for an existing connection": "Show warning only",
        }
    }
    assert result["changes"]["new"]["Computer Configuration"] == expected


@pytest.mark.skip_unless_on_windows
@pytest.mark.destructive_test
@pytest.mark.slow_test
def test_old_element_naming_style(policy_clear):
    """
    Ensure that the old naming style is converted to new and a warning is
    returned
    """
    computer_policy = {
        "Point and Print Restrictions": {
            "Users can only point and print to these servers": True,
            "Enter fully qualified server names separated by semicolons": (
                "fakeserver1;fakeserver2"
            ),
            "Users can only point and print to machines in their forest": True,
            # Here's the old one
            "Security Prompts: When installing drivers for a new connection": (
                "Show warning and elevation prompt"
            ),
            "When updating drivers for an existing connection": "Show warning only",
        }
    }

    with patch.dict(win_lgpo.__opts__, {"test": False}):
        result = win_lgpo.set_(name="test_state", computer_policy=computer_policy)
    expected = {
        "Point and Print Restrictions": {
            "Enter fully qualified server names separated by semicolons": (
                "fakeserver1;fakeserver2"
            ),
            "When installing drivers for a new connection": (
                "Show warning and elevation prompt"
            ),
            "Users can only point and print to machines in their forest": True,
            "Users can only point and print to these servers": True,
            "When updating drivers for an existing connection": "Show warning only",
        }
    }
    assert result["changes"]["new"]["Computer Configuration"] == expected
    expected = (
        'The LGPO module changed the way it gets policy element names.\n"Security'
        ' Prompts: When installing drivers for a new connection" is no longer'
        ' valid.\nPlease use "When installing drivers for a new connection"'
        " instead.\nThe following policies changed:\nPoint and Print Restrictions"
    )
    assert result["comment"] == expected


@pytest.mark.skip_unless_on_windows
@pytest.mark.destructive_test
@pytest.mark.slow_test
def test_invalid_elements():
    computer_policy = {
        "Point and Print Restrictions": {
            "Invalid element spongebob": True,
            "Invalid element squidward": False,
        }
    }

    with patch.dict(win_lgpo.__opts__, {"test": False}):
        result = win_lgpo.set_(name="test_state", computer_policy=computer_policy)
    expected = {
        "changes": {},
        "comment": (
            "Invalid element name: Invalid element squidward\n"
            "Invalid element name: Invalid element spongebob"
        ),
        "name": "test_state",
        "result": False,
    }
    assert result["changes"] == expected["changes"]
    assert "Invalid element squidward" in result["comment"]
    assert "Invalid element spongebob" in result["comment"]
    assert not expected["result"]


@pytest.mark.skip_unless_on_windows
@pytest.mark.destructive_test
@pytest.mark.slow_test
def test_current_element_naming_style_true(policy_set):
    """
    Test current naming style with test=True
    """
    computer_policy = {
        "Point and Print Restrictions": {
            "Users can only point and print to these servers": True,
            "Enter fully qualified server names separated by semicolons": (
                "fakeserver1;fakeserver2"
            ),
            "Users can only point and print to machines in their forest": True,
            "When installing drivers for a new connection": (
                "Show warning and elevation prompt"
            ),
            "When updating drivers for an existing connection": "Show warning only",
        }
    }
    with patch.dict(win_lgpo.__opts__, {"test": True}):
        result = win_lgpo.set_(name="test_state", computer_policy=computer_policy)
    expected = {
        "changes": {},
        "comment": "All specified policies are properly configured",
    }
    assert result["changes"] == expected["changes"]
    assert result["result"]
    assert result["comment"] == expected["comment"]


@pytest.mark.skip_unless_on_windows
@pytest.mark.destructive_test
@pytest.mark.slow_test
def test_old_element_naming_style_true(policy_set):
    """
    Test old naming style with test=True. Should not make changes but return a
    warning
    """
    computer_policy = {
        "Point and Print Restrictions": {
            "Users can only point and print to these servers": True,
            "Enter fully qualified server names separated by semicolons": (
                "fakeserver1;fakeserver2"
            ),
            "Users can only point and print to machines in their forest": True,
            # Here's the old one
            "Security Prompts: When installing drivers for a new connection": (
                "Show warning and elevation prompt"
            ),
            "When updating drivers for an existing connection": "Show warning only",
        }
    }
    with patch.dict(win_lgpo.__opts__, {"test": True}):
        result = win_lgpo.set_(name="test_state", computer_policy=computer_policy)
    expected = {
        "changes": {},
        "comment": (
            'The LGPO module changed the way it gets policy element names.\n"Security'
            ' Prompts: When installing drivers for a new connection" is no longer'
            ' valid.\nPlease use "When installing drivers for a new connection"'
            " instead.\nAll specified policies are properly configured"
        ),
    }
    assert result["changes"] == expected["changes"]
    assert result["result"]
    assert result["comment"] == expected["comment"]


@pytest.mark.skip_unless_on_windows
@pytest.mark.destructive_test
@pytest.mark.slow_test
def test_invalid_elements_true():
    computer_policy = {
        "Point and Print Restrictions": {
            "Invalid element spongebob": True,
            "Invalid element squidward": False,
        }
    }

    with patch.dict(win_lgpo.__opts__, {"test": True}):
        result = win_lgpo.set_(name="test_state", computer_policy=computer_policy)
    expected = {
        "changes": {},
        "comment": (
            "Invalid element name: Invalid element squidward\n"
            "Invalid element name: Invalid element spongebob"
        ),
        "name": "test_state",
        "result": False,
    }
    assert result["changes"] == expected["changes"]
    assert "Invalid element squidward" in result["comment"]
    assert "Invalid element spongebob" in result["comment"]
    assert not expected["result"]
