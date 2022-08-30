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
        ipaddress.IPv4Address,
        ipaddress.IPv4Interface,
        ipaddress.IPv4Network,
    ),
)
def factory(request):
    return request.param


@pytest.mark.parametrize(
    "address",
    [
        "000.000.000.000",
        "192.168.000.001",
        "016.016.016.016",
        "192.168.000.001",
        "001.000.008.016",
        "01.2.3.40",
        "1.02.3.40",
        "1.2.03.40",
        "1.2.3.040",
    ],
)
def test_leading_zeros(factory, address):
    # bpo-36384: no leading zeros to avoid ambiguity with octal notation
    msg = r"Leading zeros are not permitted in '\d+'"
    with assert_address_error(msg):
        factory(address)


def test_int(factory):
    assert_instances_equal(factory, 0, "0.0.0.0")
    assert_instances_equal(factory, 3232235521, "192.168.0.1")


def test_packed(factory):
    assert_instances_equal(factory, bytes.fromhex("00000000"), "0.0.0.0")
    assert_instances_equal(factory, bytes.fromhex("c0a80001"), "192.168.0.1")


def test_negative_ints_rejected(factory):
    msg = "-1 (< 0) is not permitted as an IPv4 address"
    with assert_address_error(re.escape(msg)):
        factory(-1)


def test_large_ints_rejected(factory):
    msg = "%d (>= 2**32) is not permitted as an IPv4 address"
    with assert_address_error(re.escape(msg % 2**32)):
        factory(2**32)


def test_bad_packed_length(factory):
    def assert_bad_length(length):
        addr = b"\0" * length
        msg = "%r (len %d != 4) is not permitted as an IPv4 address"
        with assert_address_error(re.escape(msg % (addr, length))):
            factory(addr)

    assert_bad_length(3)
    assert_bad_length(5)
