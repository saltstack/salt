"""
    :codeauthor: Rahul Handay <rahulha@saltstack.com>

    Test cases for salt.modules.pagerduty
"""


import pytest

import salt.modules.pagerduty as pagerduty
import salt.utils.json
import salt.utils.pagerduty
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {pagerduty: {"__salt__": {"config.option": MagicMock(return_value=None)}}}


def test_list_services():
    """
    Test for List services belonging to this account
    """
    with patch.object(salt.utils.pagerduty, "list_items", return_value="A"):
        assert pagerduty.list_services() == "A"


def test_list_incidents():
    """
    Test for List incidents belonging to this account
    """
    with patch.object(salt.utils.pagerduty, "list_items", return_value="A"):
        assert pagerduty.list_incidents() == "A"


def test_list_users():
    """
    Test for List users belonging to this account
    """
    with patch.object(salt.utils.pagerduty, "list_items", return_value="A"):
        assert pagerduty.list_users() == "A"


def test_list_schedules():
    """
    Test for List schedules belonging to this account
    """
    with patch.object(salt.utils.pagerduty, "list_items", return_value="A"):
        assert pagerduty.list_schedules() == "A"


def test_list_windows():
    """
    Test for List maintenance windows belonging to this account
    """
    with patch.object(salt.utils.pagerduty, "list_items", return_value="A"):
        assert pagerduty.list_windows() == "A"


def test_list_policies():
    """
    Test for List escalation policies belonging to this account
    """
    with patch.object(salt.utils.pagerduty, "list_items", return_value="A"):
        assert pagerduty.list_policies() == "A"


def test_create_event():
    """
    Test for Create an event in PagerDuty. Designed for use in states.
    """
    with patch.object(salt.utils.json, "loads", return_value=["A"]):
        with patch.object(salt.utils.pagerduty, "query", return_value="A"):
            assert pagerduty.create_event() == ["A"]
