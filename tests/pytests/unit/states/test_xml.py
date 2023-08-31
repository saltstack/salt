"""
Test cases for xml state
"""

import pytest

import salt.states.xml as xml
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {xml: {}}


def test_value_already_present():
    """
    Test for existing value_present
    """

    name = "testfile.xml"
    xpath = ".//list[@id='1']"
    value = "test value"

    state_return = {
        "name": name,
        "changes": {},
        "result": True,
        "comment": "{} is already present".format(value),
    }

    with patch.dict(xml.__salt__, {"xml.get_value": MagicMock(return_value=value)}):
        assert xml.value_present(name, xpath, value) == state_return


def test_value_update():
    """
    Test for updating value_present
    """

    name = "testfile.xml"
    xpath = ".//list[@id='1']"
    value = "test value"

    old_value = "not test value"

    state_return = {
        "name": name,
        "changes": {name: {"new": value, "old": old_value}},
        "result": True,
        "comment": "{} updated".format(name),
    }

    with patch.dict(xml.__salt__, {"xml.get_value": MagicMock(return_value=old_value)}):
        with patch.dict(xml.__salt__, {"xml.set_value": MagicMock(return_value=True)}):
            assert xml.value_present(name, xpath, value) == state_return


def test_value_update_test():
    """
    Test for value_present test=True
    """

    name = "testfile.xml"
    xpath = ".//list[@id='1']"
    value = "test value"

    old_value = "not test value"

    state_return = {
        "name": name,
        "changes": {name: {"old": old_value, "new": value}},
        "result": None,
        "comment": "{} will be updated".format(name),
    }

    with patch.dict(xml.__salt__, {"xml.get_value": MagicMock(return_value=old_value)}):
        assert xml.value_present(name, xpath, value, test=True) == state_return


def test_value_update_invalid_xpath():
    """
    Test for value_present invalid xpath
    """

    name = "testfile.xml"
    xpath = ".//list[@id='1']"
    value = "test value"

    state_return = {
        "name": name,
        "changes": {},
        "result": False,
        "comment": "xpath query {} not found in {}".format(xpath, name),
    }

    with patch.dict(xml.__salt__, {"xml.get_value": MagicMock(return_value=False)}):
        assert xml.value_present(name, xpath, value, test=True) == state_return
