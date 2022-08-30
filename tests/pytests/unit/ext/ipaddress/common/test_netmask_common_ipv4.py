# pylint: disable=string-substitution-usage-error

import re
import sys

import pytest

from salt._compat import ipaddress
from tests.support.pytest.ipaddress import (
    assert_address_error,
    assert_netmask_error,
    pickle_test,
)

pytestmark = [
    pytest.mark.skipif(
        sys.version_info >= (3, 9, 5),
        reason="We use builtin ipaddress on Python >= 3.9.5",
    )
]


@pytest.fixture(
    params=(
        ipaddress.IPv4Interface,
        ipaddress.IPv4Network,
    ),
)
def factory(request):
    return request.param


def test_no_mask(factory):
    for address in ("1.2.3.4", 0x01020304, b"\x01\x02\x03\x04"):
        net = factory(address)
        assert str(net) == "1.2.3.4/32"
        assert str(net.netmask) == "255.255.255.255"
        assert str(net.hostmask) == "0.0.0.0"
        # IPv4Network has prefixlen, but IPv4Interface doesn't.
        # Should we add it to IPv4Interface too? (bpo-36392)


def test_split_netmask(factory):
    addr = "1.2.3.4/32/24"
    with assert_address_error("Only one '/' permitted in %r" % addr):
        factory(addr)


def test_address_errors(factory):
    def assert_bad_address(addr, details):
        with assert_address_error(details):
            factory(addr)

    assert_bad_address("/", "Address cannot be empty")
    assert_bad_address("/8", "Address cannot be empty")
    assert_bad_address("bogus", "Expected 4 octets")
    assert_bad_address("google.com", "Expected 4 octets")
    assert_bad_address("10/8", "Expected 4 octets")
    assert_bad_address("::1.2.3.4", "Only decimal digits")
    assert_bad_address("1.2.3.256", re.escape("256 (> 255)"))


def test_valid_netmask(factory):
    assert str(factory("192.0.2.0/255.255.255.0")) == "192.0.2.0/24"
    for i in range(0, 33):
        # Generate and re-parse the CIDR format (trivial).
        net_str = "0.0.0.0/%d" % i
        net = factory(net_str)
        assert str(net) == net_str
        # Generate and re-parse the expanded netmask.
        assert str(factory("0.0.0.0/%s" % net.netmask)) == net_str
        # Zero prefix is treated as decimal.
        assert str(factory("0.0.0.0/0%d" % i)) == net_str
        # Generate and re-parse the expanded hostmask.  The ambiguous
        # cases (/0 and /32) are treated as netmasks.
        if i in (32, 0):
            net_str = "0.0.0.0/%d" % (32 - i)
        assert str(factory("0.0.0.0/%s" % net.hostmask)) == net_str


def test_netmask_errors(factory):
    def assert_bad_netmask(addr, netmask):
        msg = "%r is not a valid netmask" % netmask
        with assert_netmask_error(re.escape(msg)):
            factory("{}/{}".format(addr, netmask))

    assert_bad_netmask("1.2.3.4", "")
    assert_bad_netmask("1.2.3.4", "-1")
    assert_bad_netmask("1.2.3.4", "+1")
    assert_bad_netmask("1.2.3.4", " 1 ")
    assert_bad_netmask("1.2.3.4", "0x1")
    assert_bad_netmask("1.2.3.4", "33")
    assert_bad_netmask("1.2.3.4", "254.254.255.256")
    assert_bad_netmask("1.2.3.4", "1.a.2.3")
    assert_bad_netmask("1.1.1.1", "254.xyz.2.3")
    assert_bad_netmask("1.1.1.1", "240.255.0.0")
    assert_bad_netmask("1.1.1.1", "255.254.128.0")
    assert_bad_netmask("1.1.1.1", "0.1.127.255")
    assert_bad_netmask("1.1.1.1", "pudding")
    assert_bad_netmask("1.1.1.1", "::")


def test_netmask_in_tuple_errors(factory):
    def assert_bad_netmask(addr, netmask):
        msg = "%r is not a valid netmask" % netmask
        with assert_netmask_error(re.escape(msg)):
            factory((addr, netmask))

    assert_bad_netmask("1.1.1.1", -1)
    assert_bad_netmask("1.1.1.1", 33)


def test_pickle(factory):
    pickle_test(factory, "192.0.2.0/27")
    pickle_test(factory, "192.0.2.0/31")  # IPV4LENGTH - 1
    pickle_test(factory, "192.0.2.0")  # IPV4LENGTH
