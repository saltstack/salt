"""
Test generic roster matching utility.
"""

import pytest
import salt.config
import salt.utils.roster_matcher
from tests.support.mock import patch


@pytest.fixture
def expected():
    return {
        "host1": {
            "host": "host1",
            "passwd": "test123",
            "minion_opts": {
                "escape_pods": 2,
                "halon_system_timeout": 30,
                "self_destruct_countdown": 60,
                "some_server": "foo.southeast.example.com",
            },
        },
        "host2": {
            "host": "host2",
            "passwd": "test123",
            "minion_opts": {
                "escape_pods": 2,
                "halon_system_timeout": 30,
                "self_destruct_countdown": 60,
                "some_server": "foo.southeast.example.com",
            },
        },
        "host3": {"host": "host3", "passwd": "test123", "minion_opts": {}},
        "host4": "host4.example.com",  # For testing get_data -> string_types branch
        "host5": None,  # For testing get_data -> False
    }


@pytest.fixture
def ssh_list_nodegroups():
    return {
        "list_nodegroup": ["host5", "host1", "host2"],
        "string_nodegroup": "host3,host5,host1,host4",
    }


def test_get_data(expected):
    """
    Test that the get_data method returns the expected dictionaries.
    """
    # We don't care about tgt and tgt_type here.
    roster_matcher = salt.utils.roster_matcher.RosterMatcher(
        expected, "tgt", "tgt_type"
    )
    assert roster_matcher.get_data("host1") == expected["host1"]
    assert roster_matcher.get_data("host2") == expected["host2"]
    assert roster_matcher.get_data("host3") == expected["host3"]
    assert roster_matcher.get_data("host4") == {"host": expected["host4"]}


def test_ret_glob_minions(expected):
    """
    Test that we return minions matching a glob.
    """
    result = salt.utils.roster_matcher.targets(expected, "*[245]", "glob")
    assert "host1" not in result
    assert "host2" in result
    assert "host3" not in result
    assert "host4" in result
    assert "host5" not in result


def test_ret_pcre_minions(expected):
    """
    Test that we return minions matching a regular expression.
    """
    result = salt.utils.roster_matcher.targets(expected, ".*[^23]$", "pcre")
    assert "host1" in result
    assert "host2" not in result
    assert "host3" not in result
    assert "host4" in result
    assert "host5" not in result


def test_ret_literal_list_minions(expected):
    """
    Test that we return minions that are in a literal list.
    """
    result = salt.utils.roster_matcher.targets(
        expected, ["host1", "host2", "host5"], "list"
    )
    assert "host1" in result
    assert "host2" in result
    assert "host3" not in result
    assert "host4" not in result
    assert "host5" not in result


def test_ret_comma_delimited_string_minions(expected):
    """
    Test that we return minions that are in a comma-delimited
    string of literal minion names.
    """
    result = salt.utils.roster_matcher.targets(expected, "host5,host3,host2", "list")
    assert "host1" not in result
    assert "host2" in result
    assert "host3" in result
    assert "host4" not in result
    assert "host5" not in result


def test_ret_oops_minions(expected):
    """
    Test that we return no minions when we try to use a matching
    method that is not defined.
    """
    result = salt.utils.roster_matcher.targets(expected, None, "xyzzy")
    assert result == {}


def test_ret_literal_list_nodegroup_minions(expected, ssh_list_nodegroups):
    """
    Test that we return minions that are in a nodegroup
    where the nodegroup expresses a literal list of minion names.
    """
    result = salt.utils.roster_matcher.targets(
        expected, "list_nodegroup", "nodegroup", ssh_list_nodegroups=ssh_list_nodegroups
    )
    assert "host1" in result
    assert "host2" in result
    assert "host3" not in result
    assert "host4" not in result
    assert "host5" not in result


def test_ret_comma_delimited_string_nodegroup_minions(expected, ssh_list_nodegroups):
    """
    Test that we return minions that are in a nodegroup
    where the nodegroup expresses a comma delimited string
    of minion names.
    """
    result = salt.utils.roster_matcher.targets(
        expected,
        "string_nodegroup",
        "nodegroup",
        ssh_list_nodegroups=ssh_list_nodegroups,
    )
    assert "host1" in result
    assert "host2" not in result
    assert "host3" in result
    assert "host4" in result
    assert "host5" not in result


def test_ret_no_range_installed_minions(expected):
    """
    Test that range matcher raises a Runtime Error if seco.range is not installed.
    """
    with patch("salt.utils.roster_matcher.HAS_RANGE", False):
        with pytest.raises(RuntimeError):
            salt.utils.roster_matcher.targets(expected, None, "range")


@pytest.mark.skipif(
    salt.utils.roster_matcher.HAS_RANGE is False, reason="seco.range is not installed"
)
def test_ret_range_minions(expected):
    """
    Test that range matcher raises a Runtime Error if seco.range is not installed.
    """
    pytest.fail("Not implemented")
