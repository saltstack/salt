import pytest
import salt.cloud.clouds.openstack as openstack
from tests.support.mock import call, patch


@pytest.fixture
def configure_loader_modules():
    return {openstack: {"__opts__": {}}}


@pytest.fixture
def expected_config_stuff():
    vm = {"asdf": ...}

    with patch("copy.deepcopy", autospec=True, return_value=42), patch.dict(
        openstack.__opts__, {"foo": "bar"}
    ):
        yield vm


def test_when_getting_cloud_config_values_expected_args_should_be_provided():
    expected_vm = "whatever"
    expected_calls = call(
        "ignore_cidr", expected_vm, openstack.__opts__, default="", search_global=False
    )


@pytest.mark.parametrize(
    "comment,example_ip,ignored_cidr,expected",
    [
        ("ip is in ignore_cidr string", "203.0.113.1", "203.0.113.0/24", True),
        ("ip is not in ignore_cidr string", "192.0.2.1", "203.0.113.0/24", False),
        ("ignore_cidr is empty", "192.0.2.1", "", False),
        ("ignore_cidr is False", "192.0.2.1", False, False),
        ("ignore_cidr is None", "192.0.2.1", None, False),
        (
            "ip is in ignore_cidr list",
            "192.0.2.1",
            ["192.0.2.0/24", "203.0.113.0/24"],
            True,
        ),
        (
            "ip is not in ignore_cidr list",
            "192.0.2.1",
            ["198.51.100.0/24", "203.0.113.0/24"],
            False,
        ),
    ],
)
def test_when_ignore_cidr_is_configured_and_ip_is_provided_result_is_expected(
    comment, example_ip, ignored_cidr, expected
):
    with patch(
        "salt.config.get_cloud_config_value", autospec=True, return_value=ignored_cidr
    ):
        result = openstack.ignore_cidr("fnord", example_ip)

    assert result is expected


@pytest.mark.parametrize(
    "comment,example_ips,ignored_cidr,expected",
    [
        (
            "ignore_cidr matches first 2 ips, expected value will be first ip that"
            " doesn't match cidr.",
            ["203.0.113.1", "203.0.113.2", "192.0.2.1", "192.0.2.2"],
            "203.0.113.0/24",
            "192.0.2.1",
        ),
        (
            "ignore_cidr matches 2nd 2 IPs, expected value will be first ip in list. ",
            ["203.0.113.1", "203.0.113.2", "192.0.2.1", "192.0.2.2"],
            "192.0.2.0/24",
            "203.0.113.1",
        ),
        (
            "ignore_cidr doesn't match any IPs, expected value will be first ip in"
            " list.",
            ["203.0.113.1", "203.0.113.2", "192.0.2.1", "192.0.2.2"],
            "198.51.100.0/24",
            "203.0.113.1",
        ),
        (
            "ignore_cidr matches all IPs, expected value will be False.",
            ["203.0.113.1", "203.0.113.2", "203.0.113.3", "203.0.113.4"],
            "203.0.113.0/24",
            False,
        ),
        (
            "When ignore_cidr is not set, return first ip",
            ["203.0.113.1", "203.0.113.2", "192.0.2.1", "192.0.2.2"],
            None,
            "203.0.113.1",
        ),
    ],
)
def test_preferred_ip_function_returns_expected(
    comment, example_ips, ignored_cidr, expected
):
    with patch(
        "salt.config.get_cloud_config_value", autospec=True, return_value=ignored_cidr
    ):
        result = openstack.preferred_ip("fnord", example_ips)

    assert result is expected
