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
    return ipaddress.IPv6Address


@pytest.mark.skipif(sys.version_info < (3, 6), reason="Don't run on Py3.5")
def test_format():
    v6 = ipaddress.IPv6Address("::1.2.3.42")
    v6_pairs = [
        (
            "b",
            "000000000000000000000000000000000000000000000000000000"
            "000000000000000000000000000000000000000000000000010000"
            "00100000001100101010",
        ),
        ("n", "0000000000000000000000000102032a"),
        ("x", "0000000000000000000000000102032a"),
        ("X", "0000000000000000000000000102032A"),
        (
            "_b",
            "0000_0000_0000_0000_0000_0000_0000_0000_0000_0000_0000"
            "_0000_0000_0000_0000_0000_0000_0000_0000_0000_0000"
            "_0000_0000_0000_0000_0001_0000_0010_0000_0011_0010"
            "_1010",
        ),
        ("_n", "0000_0000_0000_0000_0000_0000_0102_032a"),
        ("_x", "0000_0000_0000_0000_0000_0000_0102_032a"),
        ("_X", "0000_0000_0000_0000_0000_0000_0102_032A"),
        (
            "#b",
            "0b0000000000000000000000000000000000000000000000000000"
            "000000000000000000000000000000000000000000000000000100"
            "0000100000001100101010",
        ),
        ("#n", "0x0000000000000000000000000102032a"),
        ("#x", "0x0000000000000000000000000102032a"),
        ("#X", "0X0000000000000000000000000102032A"),
        (
            "#_b",
            "0b0000_0000_0000_0000_0000_0000_0000_0000_0000_0000"
            "_0000_0000_0000_0000_0000_0000_0000_0000_0000_0000"
            "_0000_0000_0000_0000_0000_0001_0000_0010_0000_0011"
            "_0010_1010",
        ),
        ("#_n", "0x0000_0000_0000_0000_0000_0000_0102_032a"),
        ("#_x", "0x0000_0000_0000_0000_0000_0000_0102_032a"),
        ("#_X", "0X0000_0000_0000_0000_0000_0000_0102_032A"),
        ("s", "::102:32a"),
        ("", "::102:32a"),
    ]

    for (fmt, txt) in v6_pairs:
        assert txt == format(v6, fmt)


def test_network_passed_as_address():
    def assert_bad_split(addr):
        msg = "Unexpected '/' in %r"
        with assert_address_error(msg, addr):
            ipaddress.IPv6Address(addr)

    assert_bad_split("::1/24")
    assert_bad_split("::1%scope_id/24")


def test_bad_address_split_v6_not_enough_parts():
    def assert_bad_split(addr):
        msg = "At least 3 parts expected in %r"
        with assert_address_error(msg, addr.split("%")[0]):
            ipaddress.IPv6Address(addr)

    assert_bad_split(":")
    assert_bad_split(":1")
    assert_bad_split("FEDC:9878")
    assert_bad_split(":%scope")
    assert_bad_split(":1%scope")
    assert_bad_split("FEDC:9878%scope")


def test_bad_address_split_v6_too_many_colons():
    def assert_bad_split(addr):
        msg = "At most 8 colons permitted in %r"
        with assert_address_error(msg, addr.split("%")[0]):
            ipaddress.IPv6Address(addr)

    assert_bad_split("9:8:7:6:5:4:3::2:1")
    assert_bad_split("10:9:8:7:6:5:4:3:2:1")
    assert_bad_split("::8:7:6:5:4:3:2:1")
    assert_bad_split("8:7:6:5:4:3:2:1::")
    # A trailing IPv4 address is two parts
    assert_bad_split("10:9:8:7:6:5:4:3:42.42.42.42")

    assert_bad_split("9:8:7:6:5:4:3::2:1%scope")
    assert_bad_split("10:9:8:7:6:5:4:3:2:1%scope")
    assert_bad_split("::8:7:6:5:4:3:2:1%scope")
    assert_bad_split("8:7:6:5:4:3:2:1::%scope")
    # A trailing IPv4 address is two parts
    assert_bad_split("10:9:8:7:6:5:4:3:42.42.42.42%scope")


def test_bad_address_split_v6_too_many_parts():
    def assert_bad_split(addr):
        msg = "Exactly 8 parts expected without '::' in %r"
        with assert_address_error(msg, addr.split("%")[0]):
            ipaddress.IPv6Address(addr)

    assert_bad_split("3ffe:0:0:0:0:0:0:0:1")
    assert_bad_split("9:8:7:6:5:4:3:2:1")
    assert_bad_split("7:6:5:4:3:2:1")
    # A trailing IPv4 address is two parts
    assert_bad_split("9:8:7:6:5:4:3:42.42.42.42")
    assert_bad_split("7:6:5:4:3:42.42.42.42")

    assert_bad_split("3ffe:0:0:0:0:0:0:0:1%scope")
    assert_bad_split("9:8:7:6:5:4:3:2:1%scope")
    assert_bad_split("7:6:5:4:3:2:1%scope")
    # A trailing IPv4 address is two parts
    assert_bad_split("9:8:7:6:5:4:3:42.42.42.42%scope")
    assert_bad_split("7:6:5:4:3:42.42.42.42%scope")


def test_bad_address_split_v6_too_many_parts_with_double_colon():
    def assert_bad_split(addr):
        msg = "Expected at most 7 other parts with '::' in %r"
        with assert_address_error(msg, addr.split("%")[0]):
            ipaddress.IPv6Address(addr)

    assert_bad_split("1:2:3:4::5:6:7:8")
    assert_bad_split("1:2:3:4::5:6:7:8%scope")


def test_bad_address_split_v6_repeated_double_colon():
    def assert_bad_split(addr):
        msg = "At most one '::' permitted in %r"
        with assert_address_error(msg, addr.split("%")[0]):
            ipaddress.IPv6Address(addr)

    assert_bad_split("3ffe::1::1")
    assert_bad_split("1::2::3::4:5")
    assert_bad_split("2001::db:::1")
    assert_bad_split("3ffe::1::")
    assert_bad_split("::3ffe::1")
    assert_bad_split(":3ffe::1::1")
    assert_bad_split("3ffe::1::1:")
    assert_bad_split(":3ffe::1::1:")
    assert_bad_split(":::")
    assert_bad_split("2001:db8:::1")

    assert_bad_split("3ffe::1::1%scope")
    assert_bad_split("1::2::3::4:5%scope")
    assert_bad_split("2001::db:::1%scope")
    assert_bad_split("3ffe::1::%scope")
    assert_bad_split("::3ffe::1%scope")
    assert_bad_split(":3ffe::1::1%scope")
    assert_bad_split("3ffe::1::1:%scope")
    assert_bad_split(":3ffe::1::1:%scope")
    assert_bad_split(":::%scope")
    assert_bad_split("2001:db8:::1%scope")


def test_bad_address_split_v6_leading_colon():
    def assert_bad_split(addr):
        msg = "Leading ':' only permitted as part of '::' in %r"
        with assert_address_error(msg, addr.split("%")[0]):
            ipaddress.IPv6Address(addr)

    assert_bad_split(":2001:db8::1")
    assert_bad_split(":1:2:3:4:5:6:7")
    assert_bad_split(":1:2:3:4:5:6:")
    assert_bad_split(":6:5:4:3:2:1::")

    assert_bad_split(":2001:db8::1%scope")
    assert_bad_split(":1:2:3:4:5:6:7%scope")
    assert_bad_split(":1:2:3:4:5:6:%scope")
    assert_bad_split(":6:5:4:3:2:1::%scope")


def test_bad_address_split_v6_trailing_colon():
    def assert_bad_split(addr):
        msg = "Trailing ':' only permitted as part of '::' in %r"
        with assert_address_error(msg, addr.split("%")[0]):
            ipaddress.IPv6Address(addr)

    assert_bad_split("2001:db8::1:")
    assert_bad_split("1:2:3:4:5:6:7:")
    assert_bad_split("::1.2.3.4:")
    assert_bad_split("::7:6:5:4:3:2:")

    assert_bad_split("2001:db8::1:%scope")
    assert_bad_split("1:2:3:4:5:6:7:%scope")
    assert_bad_split("::1.2.3.4:%scope")
    assert_bad_split("::7:6:5:4:3:2:%scope")


def test_bad_v4_part_in():
    def assertBadAddressPart(addr, v4_error):
        with assert_address_error("%s in %r", v4_error, addr.split("%")[0]):
            ipaddress.IPv6Address(addr)

    assertBadAddressPart("3ffe::1.net", "Expected 4 octets in '1.net'")
    assertBadAddressPart("3ffe::127.0.1", "Expected 4 octets in '127.0.1'")
    assertBadAddressPart("::1.2.3", "Expected 4 octets in '1.2.3'")
    assertBadAddressPart("::1.2.3.4.5", "Expected 4 octets in '1.2.3.4.5'")
    assertBadAddressPart(
        "3ffe::1.1.1.net",
        "Only decimal digits permitted in 'net' in '1.1.1.net'",
    )

    assertBadAddressPart("3ffe::1.net%scope", "Expected 4 octets in '1.net'")
    assertBadAddressPart("3ffe::127.0.1%scope", "Expected 4 octets in '127.0.1'")
    assertBadAddressPart("::1.2.3%scope", "Expected 4 octets in '1.2.3'")
    assertBadAddressPart("::1.2.3.4.5%scope", "Expected 4 octets in '1.2.3.4.5'")
    assertBadAddressPart(
        "3ffe::1.1.1.net%scope",
        "Only decimal digits permitted in 'net' in '1.1.1.net'",
    )


def test_invalid_characters():
    def assert_bad_part(addr, part):
        msg = "Only hex digits permitted in {!r} in {!r}".format(
            part, addr.split("%")[0]
        )
        with assert_address_error(re.escape(msg)):
            ipaddress.IPv6Address(addr)

    assert_bad_part("3ffe::goog", "goog")
    assert_bad_part("3ffe::-0", "-0")
    assert_bad_part("3ffe::+0", "+0")
    assert_bad_part("3ffe::-1", "-1")
    assert_bad_part("1.2.3.4::", "1.2.3.4")
    assert_bad_part("1234:axy::b", "axy")

    assert_bad_part("3ffe::goog%scope", "goog")
    assert_bad_part("3ffe::-0%scope", "-0")
    assert_bad_part("3ffe::+0%scope", "+0")
    assert_bad_part("3ffe::-1%scope", "-1")
    assert_bad_part("1.2.3.4::%scope", "1.2.3.4")
    assert_bad_part("1234:axy::b%scope", "axy")


def test_part_length():
    def assert_bad_part(addr, part):
        msg = "At most 4 characters permitted in %r in %r"
        with assert_address_error(msg, part, addr.split("%")[0]):
            ipaddress.IPv6Address(addr)

    assert_bad_part("::00000", "00000")
    assert_bad_part("3ffe::10000", "10000")
    assert_bad_part("02001:db8::", "02001")
    assert_bad_part("2001:888888::1", "888888")

    assert_bad_part("::00000%scope", "00000")
    assert_bad_part("3ffe::10000%scope", "10000")
    assert_bad_part("02001:db8::%scope", "02001")
    assert_bad_part("2001:888888::1%scope", "888888")


def test_pickle(factory):
    pickle_test(factory, "2001:db8::")


def test_weakref(factory):
    weakref.ref(factory("2001:db8::"))
    weakref.ref(factory("2001:db8::%scope"))
