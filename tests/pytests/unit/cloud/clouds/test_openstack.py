import pytest
import salt.cloud.clouds.openstack as openstack

# from tests.support.helpers import TstSuiteLoggingHandler
from tests.support.mock import MagicMock, call, patch


@pytest.fixture
def configure_loader_modules():
    return {openstack: {"__opts__": {},}}


@pytest.fixture
def expected_config_stuff():
    vm = {"asdf": ...}

    with patch("copy.deepcopy", autospec=True, return_value=42), patch.dict(
        openstack.__opts__, {"foo": "bar"}
    ):
        yield vm


def test_when_not_HAS_NETADDR_then_ignore_cidr_should_be_False():

    with patch("salt.cloud.clouds.openstack.HAS_NETADDR", False):
        result = openstack.ignore_cidr("fnord", "fnord")

    assert result == False


# optional!
def test_when_not_HAS_NETADDR_then_error_message_should_be_logged():
    # patch log.error
    # call openstack.ignore_cidr(..., ...)
    # assert that log.error was called with the correct message
    pass


def test_when_getting_cloud_config_values_expected_args_should_be_provided():
    expected_vm = "whatever"
    expected_calls = call(
        "ignore_cidr", expected_vm, openstack.__opts__, default="", search_global=False
    )

    ...


@pytest.mark.parametrize(
    "example_ip,ignored_cidr,expected,comment",
    [
        ("203.0.113.1", "203.0.113.0/24", True, "ip is in ignore_cidr"),
        ("192.0.2.1", "203.0.113.0/24", False, "ip is not in ignore_cidr"),
        ("192.0.2.1", "", False, "ignore_cidr is empty"),
        ("192.0.2.1", False, False, "ignore_cidr is False"),
        ("192.0.2.1", None, False, "ignore_cidr is None"),
    ],
)
def test_when_ignore_cidr_is_configured_and_ip_is_provided_result_is_expected(
    example_ip, ignored_cidr, expected, comment
):
    with patch(
        "salt.config.get_cloud_config_value", autospec=True, return_value=ignored_cidr,
    ):
        result = openstack.ignore_cidr("fnord", example_ip)

    assert result is expected


@pytest.mark.parametrize(
    "comment,example_ips,ignored_cidr,expected",
    [
        (
            "Return the first ip not in ignore_cidr range",
            ["203.0.113.1", "203.0.113.2", "192.0.2.1", "192.0.2.2",],
            "203.0.113.0/24",
            "192.0.2.1",
        ),
        (
            "Return the first ip not in different ignore_cidr range",
            ["203.0.113.1", "203.0.113.2", "192.0.2.1", "192.0.2.2",],
            "192.0.2.0/24",
            "203.0.113.1",
        ),
        (
            "ignore_cidr is not set",
            ["203.0.113.1", "203.0.113.2", "192.0.2.1", "192.0.2.2",],
            None,
            "203.0.113.1",
        ),
    ],
)
def test_preferred_ip_returns_first_ip_not_in_ignore_cidr(
    comment, example_ips, ignored_cidr, expected
):
    with patch(
        "salt.config.get_cloud_config_value", autospec=True, return_value=ignored_cidr,
    ):
        result = openstack.preferred_ip("fnord", example_ips)

    assert result is expected


"""
def test_when_no_ips_should_be_ignored_then_preferred_ip_should_return_something():
    ...


def test_when_ip_should_be_ignore_cidr_then_ip_should_not_be_preferred():
    ...
"""

# fill out all of these tests, refactor some and then also add a changelog entry
