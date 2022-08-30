import sys

import pytest

from salt._compat import ipaddress
from tests.support.pytest.ipaddress import assert_clean_error

pytestmark = [
    pytest.mark.skipif(
        sys.version_info >= (3, 9, 5),
        reason="We use builtin ipaddress on Python >= 3.9.5",
    )
]


def assert_factory_error(factory, kind):
    """Ensure a clean ValueError with the expected message"""
    addr = "camelot"
    msg = "%r does not appear to be an IPv4 or IPv6 %s"
    with assert_clean_error(ValueError, msg, addr, kind):
        factory(addr)


def test_ip_address():
    assert_factory_error(ipaddress.ip_address, "address")


def test_ip_interface():
    assert_factory_error(ipaddress.ip_interface, "interface")


def test_ip_network():
    assert_factory_error(ipaddress.ip_network, "network")
