# pylint: disable=string-substitution-usage-error

import re
import sys
import weakref

import pytest

from salt._compat import ipaddress
from tests.support.pytest.ipaddress import assert_address_error, pickle_test

pytestmark = [
    pytest.mark.skipif(
        sys.version_info >= (3, 9, 5),
        reason="We use builtin ipaddress on Python >= 3.9.5",
    )
]


@pytest.fixture
def factory():
    return ipaddress.IPv4Address


def test_format():
    v4 = ipaddress.IPv4Address("1.2.3.42")
    v4_pairs = [
        ("b", "00000001000000100000001100101010"),
        ("n", "00000001000000100000001100101010"),
        ("x", "0102032a"),
        ("X", "0102032A"),
        ("_b", "0000_0001_0000_0010_0000_0011_0010_1010"),
        ("_n", "0000_0001_0000_0010_0000_0011_0010_1010"),
        ("_x", "0102_032a"),
        ("_X", "0102_032A"),
        ("#b", "0b00000001000000100000001100101010"),
        ("#n", "0b00000001000000100000001100101010"),
        ("#x", "0x0102032a"),
        ("#X", "0X0102032A"),
        ("#_b", "0b0000_0001_0000_0010_0000_0011_0010_1010"),
        ("#_n", "0b0000_0001_0000_0010_0000_0011_0010_1010"),
        ("#_x", "0x0102_032a"),
        ("#_X", "0X0102_032A"),
        ("s", "1.2.3.42"),
        ("", "1.2.3.42"),
    ]
    for (fmt, txt) in v4_pairs:
        assert txt == format(v4, fmt)


def test_network_passed_as_address():
    addr = "127.0.0.1/24"
    with assert_address_error("Unexpected '/' in %r", addr):
        ipaddress.IPv4Address(addr)


def test_bad_address_split():
    def assert_bad_split(addr):
        with assert_address_error("Expected 4 octets in %r", addr):
            ipaddress.IPv4Address(addr)

    assert_bad_split("127.0.1")
    assert_bad_split("42.42.42.42.42")
    assert_bad_split("42.42.42")
    assert_bad_split("42.42")
    assert_bad_split("42")
    assert_bad_split("42..42.42.42")
    assert_bad_split("42.42.42.42.")
    assert_bad_split("42.42.42.42...")
    assert_bad_split(".42.42.42.42")
    assert_bad_split("...42.42.42.42")
    assert_bad_split("016.016.016")
    assert_bad_split("016.016")
    assert_bad_split("016")
    assert_bad_split("000")
    assert_bad_split("0x0a.0x0a.0x0a")
    assert_bad_split("0x0a.0x0a")
    assert_bad_split("0x0a")
    assert_bad_split(".")
    assert_bad_split("bogus")
    assert_bad_split("bogus.com")
    assert_bad_split("1000")
    assert_bad_split("1000000000000000")
    assert_bad_split("192.168.0.1.com")


def test_empty_octet():
    def assert_bad_octet(addr):
        with assert_address_error("Empty octet not permitted in %r", addr):
            ipaddress.IPv4Address(addr)

    assert_bad_octet("42..42.42")
    assert_bad_octet("...")


def test_invalid_characters():
    def assert_bad_octet(addr, octet):
        msg = "Only decimal digits permitted in {!r} in {!r}".format(octet, addr)
        with assert_address_error(re.escape(msg)):
            ipaddress.IPv4Address(addr)

    assert_bad_octet("0x0a.0x0a.0x0a.0x0a", "0x0a")
    assert_bad_octet("0xa.0x0a.0x0a.0x0a", "0xa")
    assert_bad_octet("42.42.42.-0", "-0")
    assert_bad_octet("42.42.42.+0", "+0")
    assert_bad_octet("42.42.42.-42", "-42")
    assert_bad_octet("+1.+2.+3.4", "+1")
    assert_bad_octet("1.2.3.4e0", "4e0")
    assert_bad_octet("1.2.3.4::", "4::")
    assert_bad_octet("1.a.2.3", "a")


def test_octet_length():
    def assert_bad_octet(addr, octet):
        msg = "At most 3 characters permitted in %r in %r"
        with assert_address_error(re.escape(msg % (octet, addr))):
            ipaddress.IPv4Address(addr)

    assert_bad_octet("0000.000.000.000", "0000")
    assert_bad_octet("12345.67899.-54321.-98765", "12345")


def test_octet_limit():
    def assert_bad_octet(addr, octet):
        msg = "Octet %d (> 255) not permitted in %r" % (octet, addr)
        with assert_address_error(re.escape(msg)):
            ipaddress.IPv4Address(addr)

    assert_bad_octet("257.0.0.0", 257)
    assert_bad_octet("192.168.0.999", 999)


def test_pickle(factory):
    pickle_test(factory, "192.0.2.1")


def test_weakref(factory):
    weakref.ref(factory("192.0.2.1"))
