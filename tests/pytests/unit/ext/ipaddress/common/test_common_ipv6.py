import re
import sys

import pytest

from salt._compat import ipaddress
from tests.support.pytest.ipaddress import assert_address_error, assert_instances_equal

pytestmark = [
    pytest.mark.skipif(
        sys.version_info >= (3, 9, 5),
        reason="We use builtin ipaddress on Python >= 3.9.5",
    )
]


@pytest.fixture(
    params=(
        ipaddress.IPv6Address,
        ipaddress.IPv6Interface,
        ipaddress.IPv6Network,
    ),
)
def factory(request):
    return request.param


def test_leading_zeros(factory):
    assert_instances_equal(factory, "0000::0000", "::")
    assert_instances_equal(factory, "000::c0a8:0001", "::c0a8:1")


def test_int(factory):
    assert_instances_equal(factory, 0, "::")
    assert_instances_equal(factory, 3232235521, "::c0a8:1")


def test_packed(factory):
    addr = b"\0" * 12 + bytes.fromhex("00000000")
    assert_instances_equal(factory, addr, "::")
    addr = b"\0" * 12 + bytes.fromhex("c0a80001")
    assert_instances_equal(factory, addr, "::c0a8:1")
    addr = bytes.fromhex("c0a80001") + b"\0" * 12
    assert_instances_equal(factory, addr, "c0a8:1::")


def test_negative_ints_rejected(factory):
    msg = "-1 (< 0) is not permitted as an IPv6 address"
    with assert_address_error(re.escape(msg)):
        factory(-1)


def test_large_ints_rejected(factory):
    msg = "%d (>= 2**128) is not permitted as an IPv6 address"
    with assert_address_error(re.escape(msg % 2**128)):
        factory(2**128)


def test_bad_packed_length(factory):
    def assert_bad_length(length):
        addr = b"\0" * length
        msg = "%r (len %d != 16) is not permitted as an IPv6 address"
        with assert_address_error(re.escape(msg % (addr, length))):
            factory(addr)
            factory(addr)

    assert_bad_length(15)
    assert_bad_length(17)


def test_blank_scope_id(factory):
    address = "::1%"
    with assert_address_error('Invalid IPv6 address: "%r"', address):
        factory(address)


def test_invalid_scope_id_with_percent(factory):
    address = "::1%scope%"
    with assert_address_error('Invalid IPv6 address: "%r"', address):
        factory(address)
