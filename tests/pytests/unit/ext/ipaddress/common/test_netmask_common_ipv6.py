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
        ipaddress.IPv6Interface,
        ipaddress.IPv6Network,
    ),
)
def factory(request):
    return request.param


def test_no_mask(factory):
    for address in ("::1", 1, b"\x00" * 15 + b"\x01"):
        net = factory(address)
        assert str(net) == "::1/128"
        assert str(net.netmask) == "ffff:ffff:ffff:ffff:ffff:ffff:ffff:ffff"
        assert str(net.hostmask) == "::"
        # IPv6Network has prefixlen, but IPv6Interface doesn't.
        # Should we add it to IPv4Interface too? (bpo-36392)

    scoped_net = factory("::1%scope")
    assert str(scoped_net) == "::1%scope/128"
    assert str(scoped_net.netmask) == "ffff:ffff:ffff:ffff:ffff:ffff:ffff:ffff"
    assert str(scoped_net.hostmask) == "::"


def test_split_netmask(factory):
    addr = "cafe:cafe::/128/190"
    with assert_address_error("Only one '/' permitted in %r" % addr):
        factory(addr)

    scoped_addr = "cafe:cafe::%scope/128/190"
    with assert_address_error("Only one '/' permitted in %r" % scoped_addr):
        factory(scoped_addr)


def test_address_errors(factory):
    def assert_bad_address(addr, details):
        with assert_address_error(details):
            factory(addr)

    assert_bad_address("/", "Address cannot be empty")
    assert_bad_address("/8", "Address cannot be empty")
    assert_bad_address("google.com", "At least 3 parts")
    assert_bad_address("1.2.3.4", "At least 3 parts")
    assert_bad_address("10/8", "At least 3 parts")
    assert_bad_address("1234:axy::b", "Only hex digits")

    assert_bad_address("/%scope", "Address cannot be empty")
    assert_bad_address("/%scope8", "Address cannot be empty")
    assert_bad_address("google.com%scope", "At least 3 parts")
    assert_bad_address("1.2.3.4%scope", "At least 3 parts")
    assert_bad_address("10%scope/8", "At least 3 parts")
    assert_bad_address("1234:axy::b%scope", "Only hex digits")


def test_valid_netmask(factory):
    # We only support CIDR for IPv6, because expanded netmasks are not
    # standard notation.
    assert str(factory("2001:db8::/32")) == "2001:db8::/32"
    for i in range(0, 129):
        # Generate and re-parse the CIDR format (trivial).
        net_str = "::/%d" % i
        assert str(factory(net_str)) == net_str
        # Zero prefix is treated as decimal.
        assert str(factory("::/0%d" % i)) == net_str

    assert str(factory("2001:db8::%scope/32")) == "2001:db8::%scope/32"
    for i in range(0, 129):
        # Generate and re-parse the CIDR format (trivial).
        net_str = "::/%d" % i
        assert str(factory(net_str)) == net_str
        # Zero prefix is treated as decimal.
        assert str(factory("::/0%d" % i)) == net_str


def test_netmask_errors(factory):
    def assert_bad_netmask(addr, netmask):
        msg = "%r is not a valid netmask" % netmask
        with assert_netmask_error(re.escape(msg)):
            factory("{}/{}".format(addr, netmask))

    assert_bad_netmask("::1", "")
    assert_bad_netmask("::1", "::1")
    assert_bad_netmask("::1", "1::")
    assert_bad_netmask("::1", "-1")
    assert_bad_netmask("::1", "+1")
    assert_bad_netmask("::1", " 1 ")
    assert_bad_netmask("::1", "0x1")
    assert_bad_netmask("::1", "129")
    assert_bad_netmask("::1", "1.2.3.4")
    assert_bad_netmask("::1", "pudding")
    assert_bad_netmask("::", "::")

    assert_bad_netmask("::1%scope", "pudding")


def test_netmask_in_tuple_errors(factory):
    def assert_bad_netmask(addr, netmask):
        msg = "%r is not a valid netmask" % netmask
        with assert_netmask_error(re.escape(msg)):
            factory((addr, netmask))

    assert_bad_netmask("::1", -1)
    assert_bad_netmask("::1", 129)
    assert_bad_netmask("::1%scope", 129)


def test_pickle(factory):
    pickle_test(factory, "2001:db8::1000/124")
    pickle_test(factory, "2001:db8::1000/127")  # IPV6LENGTH - 1
    pickle_test(factory, "2001:db8::1000")  # IPV6LENGTH
    pickle_test(factory, "2001:db8::1000%scope")  # IPV6LENGTH
