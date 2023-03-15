import threading

import pytest

import salt.modules.network as networkmod
from tests.support.mock import patch


@pytest.fixture
def configure_loader_modules():
    return {networkmod: {}}


@pytest.fixture
def socket_errors():
    # Not sure what kind of errors could be returned by getfqdn or
    # gethostbyaddr, but we have reports that thread leaks are happening
    with patch("socket.getfqdn", autospec=True, side_effect=Exception), patch(
        "socket.gethostbyaddr", autospec=True, side_effect=Exception
    ):
        yield


@pytest.fixture
def fake_fqdn():
    fqdn = "some.sample.fqdn.example.com"
    # Since we're mocking getfqdn it doesn't matter what gethostbyaddr returns.
    # At least as long as it's the right shape (i.e. has a [0] element)
    with patch("socket.getfqdn", autospec=True, return_value=fqdn), patch(
        "socket.gethostbyaddr",
        autospec=True,
        return_value=("fnord", "fnord fnord"),
    ):
        yield fqdn


@pytest.fixture
def fake_ips():
    with patch(
        "salt.utils.network.ip_addrs",
        autospec=True,
        return_value=[
            "203.0.113.1",
            "203.0.113.3",
            "203.0.113.6",
            "203.0.113.25",
            "203.0.113.82",
        ],
    ), patch("salt.utils.network.ip_addrs6", autospec=True, return_value=[]):
        yield


def test_when_errors_happen_looking_up_fqdns_threads_should_not_leak(socket_errors):
    before_threads = threading.active_count()
    networkmod.fqdns()
    after_threads = threading.active_count()
    assert (
        before_threads == after_threads
    ), "Difference in thread count means the thread pool is not correctly cleaning up."


def test_when_no_errors_happen_looking_up_fqdns_threads_should_not_leak(
    fake_fqdn, fake_ips
):
    before_threads = threading.active_count()
    networkmod.fqdns()
    after_threads = threading.active_count()
    assert (
        before_threads == after_threads
    ), "Difference in thread count means the thread pool is not correctly cleaning up."


def test_when_no_errors_happen_looking_up_fqdns_results_from_fqdns_lookup_should_be_returned(
    fake_fqdn, fake_ips
):
    actual_fqdn = networkmod.fqdns()
    # Even though we have two fake IPs they magically resolve to the same fqdn
    assert actual_fqdn == {"fqdns": [fake_fqdn]}


def test_fqdns_should_return_sorted_unique_domains(fake_ips):
    # These need to match the number of ips in fake_ips
    fake_domains = [
        "z.example.com",
        "z.example.com",
        "c.example.com",
        "a.example.com",
    ]
    with patch("socket.getfqdn", autospec=True, side_effect=fake_domains), patch(
        "socket.gethostbyaddr",
        autospec=True,
        return_value=("fnord", "fnord fnord"),
    ):
        actual_fqdns = networkmod.fqdns()
        assert actual_fqdns == {
            "fqdns": ["a.example.com", "c.example.com", "z.example.com"]
        }
