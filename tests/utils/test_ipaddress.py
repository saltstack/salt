'''
Python 2.[67] port of Python 3.4's test_ipaddress.

Almost verbatim copy of core lib w/compatibility fixes
'''
# pylint: skip-file

# List of compatibility changes:

# This backport uses bytearray instead of bytes, as bytes is the same
# as str in Python 2.7.
#bytes = bytearray
# s/\(b'[^']\+'\)/bytearray(\1)/g
# plus manual fixes for implicit string concatenation.

# Python 3.4 has assertRaisesRegex where Python 2.7 only has assertRaisesRegexp.
# s/\.assertRaisesRegexp(/.assertRaisesRegexp(/

# Python 2.6 carries assertRaisesRegexp and others in unittest2

# Python 2.6 wants unicode into bytes.fromhex
# s/bytes.fromhex\("/bytes.fromhex(u"/g

# Further compatibility changes are marked "Compatibility", below.

# ----------------------------------------------------------------------------


# Copyright 2007 Google Inc.
#  Licensed to PSF under a Contributor Agreement.

"""Unittest for ipaddress module."""

# Import python libs
import re
import sys
import contextlib
import operator
import sys

# Import salt libs
from salt._compat import ipaddress
# Import salt test libs
from tests.support.unit import TestCase, skipIf
import pytest

if sys.version_info < (3,):
    bytes = bytearray

@skipIf(sys.version_info > (3,), 'These are tested by the python test suite under Py3')
class BaseTestCase(TestCase):
    # One big change in ipaddress over the original ipaddr module is
    # error reporting that tries to assume users *don't know the rules*
    # for what constitutes an RFC compliant IP address

    # Ensuring these errors are emitted correctly in all relevant cases
    # meant moving to a more systematic test structure that allows the
    # test structure to map more directly to the module structure

    # Note that if the constructors are refactored so that addresses with
    # multiple problems get classified differently, that's OK - just
    # move the affected examples to the newly appropriate test case.

    # There is some duplication between the original relatively ad hoc
    # test suite and the new systematic tests. While some redundancy in
    # testing is considered preferable to accidentally deleting a valid
    # test, the original test suite will likely be reduced over time as
    # redundant tests are identified.

    @property
    def factory(self):
        raise NotImplementedError

    @contextlib.contextmanager
    def assertCleanError(self, exc_type, details, *args):
        """
        Ensure exception does not display a context by default

        Wraps TestCase.assertRaisesRegex
        """
        if args:
            details = details % args
        cm = pytest.raises(exc_type, match=details)
        with cm as exc:
            yield exc

        # Compatibility: Python 2.7 does not support exception chaining
        ## Ensure we produce clean tracebacks on failure
        #if exc.exception.__context__ is not None:
        #    self.assertTrue(exc.exception.__suppress_context__)

    def assertAddressError(self, details, *args):
        """Ensure a clean AddressValueError"""
        return self.assertCleanError(ipaddress.AddressValueError,
                                       details, *args)

    def assertNetmaskError(self, details, *args):
        """Ensure a clean NetmaskValueError"""
        return self.assertCleanError(ipaddress.NetmaskValueError,
                                details, *args)

    def assertInstancesEqual(self, lhs, rhs):
        """Check constructor arguments produce equivalent instances"""
        assert self.factory(lhs) == self.factory(rhs)


class CommonTestMixin:

    def test_empty_address(self):
        with self.assertAddressError("Address cannot be empty"):
            self.factory("")

    def test_floats_rejected(self):
        with self.assertAddressError(re.escape(repr("1.0"))):
            self.factory(1.0)

    def test_not_an_index_issue15559(self):
        # Implementing __index__ makes for a very nasty interaction with the
        # bytes constructor. Thus, we disallow implicit use as an integer
        with pytest.raises(TypeError):
            operator.index(self.factory(1))
        with pytest.raises(TypeError):
            hex(self.factory(1))
        with pytest.raises(TypeError):
            bytes(self.factory(1))


class CommonTestMixin_v4(CommonTestMixin):

    def test_leading_zeros(self):
        self.assertInstancesEqual("000.000.000.000", "0.0.0.0")
        self.assertInstancesEqual("192.168.000.001", "192.168.0.1")

    def test_int(self):
        self.assertInstancesEqual(0, "0.0.0.0")
        self.assertInstancesEqual(3232235521, "192.168.0.1")

    def test_packed(self):
        self.assertInstancesEqual(bytes.fromhex(u"00000000"), "0.0.0.0")
        self.assertInstancesEqual(bytes.fromhex(u"c0a80001"), "192.168.0.1")

    def test_negative_ints_rejected(self):
        msg = "-1 (< 0) is not permitted as an IPv4 address"
        with self.assertAddressError(re.escape(msg)):
            self.factory(-1)

    def test_large_ints_rejected(self):
        msg = "%d (>= 2**32) is not permitted as an IPv4 address"
        with self.assertAddressError(re.escape(msg % 2**32)):
            self.factory(2**32)

    def test_bad_packed_length(self):
        def assertBadLength(length):
            addr = bytes(length)
            msg = "%r (len %d != 4) is not permitted as an IPv4 address"
            with self.assertAddressError(re.escape(msg % (addr, length))):
                self.factory(addr)

        assertBadLength(3)
        assertBadLength(5)


class CommonTestMixin_v6(CommonTestMixin):

    def test_leading_zeros(self):
        self.assertInstancesEqual("0000::0000", "::")
        self.assertInstancesEqual("000::c0a8:0001", "::c0a8:1")

    def test_int(self):
        self.assertInstancesEqual(0, "::")
        self.assertInstancesEqual(3232235521, "::c0a8:1")

    def test_packed(self):
        addr = bytes(12) + bytes.fromhex(u"00000000")
        self.assertInstancesEqual(addr, "::")
        addr = bytes(12) + bytes.fromhex(u"c0a80001")
        self.assertInstancesEqual(addr, "::c0a8:1")
        addr = bytes.fromhex(u"c0a80001") + bytes(12)
        self.assertInstancesEqual(addr, "c0a8:1::")

    def test_negative_ints_rejected(self):
        msg = "-1 (< 0) is not permitted as an IPv6 address"
        with self.assertAddressError(re.escape(msg)):
            self.factory(-1)

    def test_large_ints_rejected(self):
        msg = "%d (>= 2**128) is not permitted as an IPv6 address"
        with self.assertAddressError(re.escape(msg % 2**128)):
            self.factory(2**128)

    def test_bad_packed_length(self):
        def assertBadLength(length):
            addr = bytes(length)
            msg = "%r (len %d != 16) is not permitted as an IPv6 address"
            with self.assertAddressError(re.escape(msg % (addr, length))):
                self.factory(addr)
                self.factory(addr)

        assertBadLength(15)
        assertBadLength(17)


@skipIf(sys.version_info > (3,), 'These are tested by the python test suite under Py3')
class AddressTestCase_v4(BaseTestCase, CommonTestMixin_v4):
    factory = ipaddress.IPv4Address

    def test_network_passed_as_address(self):
        addr = "127.0.0.1/24"
        with self.assertAddressError("Unexpected '/' in %r", addr):
            ipaddress.IPv4Address(addr)

    def test_bad_address_split(self):
        def assertBadSplit(addr):
            with self.assertAddressError("Expected 4 octets in %r", addr):
                ipaddress.IPv4Address(addr)

        assertBadSplit("127.0.1")
        assertBadSplit("42.42.42.42.42")
        assertBadSplit("42.42.42")
        assertBadSplit("42.42")
        assertBadSplit("42")
        assertBadSplit("42..42.42.42")
        assertBadSplit("42.42.42.42.")
        assertBadSplit("42.42.42.42...")
        assertBadSplit(".42.42.42.42")
        assertBadSplit("...42.42.42.42")
        assertBadSplit("016.016.016")
        assertBadSplit("016.016")
        assertBadSplit("016")
        assertBadSplit("000")
        assertBadSplit("0x0a.0x0a.0x0a")
        assertBadSplit("0x0a.0x0a")
        assertBadSplit("0x0a")
        assertBadSplit(".")
        assertBadSplit("bogus")
        assertBadSplit("bogus.com")
        assertBadSplit("1000")
        assertBadSplit("1000000000000000")
        assertBadSplit("192.168.0.1.com")

    def test_empty_octet(self):
        def assertBadOctet(addr):
            with self.assertAddressError("Empty octet not permitted in %r",
                                          addr):
                ipaddress.IPv4Address(addr)

        assertBadOctet("42..42.42")
        assertBadOctet("...")

    def test_invalid_characters(self):
        def assertBadOctet(addr, octet):
            msg = "Only decimal digits permitted in %r in %r" % (octet, addr)
            with self.assertAddressError(re.escape(msg)):
                ipaddress.IPv4Address(addr)

        assertBadOctet("0x0a.0x0a.0x0a.0x0a", "0x0a")
        assertBadOctet("0xa.0x0a.0x0a.0x0a", "0xa")
        assertBadOctet("42.42.42.-0", "-0")
        assertBadOctet("42.42.42.+0", "+0")
        assertBadOctet("42.42.42.-42", "-42")
        assertBadOctet("+1.+2.+3.4", "+1")
        assertBadOctet("1.2.3.4e0", "4e0")
        assertBadOctet("1.2.3.4::", "4::")
        assertBadOctet("1.a.2.3", "a")

    def test_octal_decimal_ambiguity(self):
        def assertBadOctet(addr, octet):
            msg = "Ambiguous (octal/decimal) value in %r not permitted in %r"
            with self.assertAddressError(re.escape(msg % (octet, addr))):
                ipaddress.IPv4Address(addr)

        assertBadOctet("016.016.016.016", "016")
        assertBadOctet("001.000.008.016", "008")

    def test_octet_length(self):
        def assertBadOctet(addr, octet):
            msg = "At most 3 characters permitted in %r in %r"
            with self.assertAddressError(re.escape(msg % (octet, addr))):
                ipaddress.IPv4Address(addr)

        assertBadOctet("0000.000.000.000", "0000")
        assertBadOctet("12345.67899.-54321.-98765", "12345")

    def test_octet_limit(self):
        def assertBadOctet(addr, octet):
            msg = "Octet %d (> 255) not permitted in %r" % (octet, addr)
            with self.assertAddressError(re.escape(msg)):
                ipaddress.IPv4Address(addr)

        assertBadOctet("257.0.0.0", 257)
        assertBadOctet("192.168.0.999", 999)


@skipIf(sys.version_info > (3,), 'These are tested by the python test suite under Py3')
class AddressTestCase_v6(BaseTestCase, CommonTestMixin_v6):
    factory = ipaddress.IPv6Address

    def test_network_passed_as_address(self):
        addr = "::1/24"
        with self.assertAddressError("Unexpected '/' in %r", addr):
            ipaddress.IPv6Address(addr)

    def test_bad_address_split_v6_not_enough_parts(self):
        def assertBadSplit(addr):
            msg = "At least 3 parts expected in %r"
            with self.assertAddressError(msg, addr):
                ipaddress.IPv6Address(addr)

        assertBadSplit(":")
        assertBadSplit(":1")
        assertBadSplit("FEDC:9878")

    def test_bad_address_split_v6_too_many_colons(self):
        def assertBadSplit(addr):
            msg = "At most 8 colons permitted in %r"
            with self.assertAddressError(msg, addr):
                ipaddress.IPv6Address(addr)

        assertBadSplit("9:8:7:6:5:4:3::2:1")
        assertBadSplit("10:9:8:7:6:5:4:3:2:1")
        assertBadSplit("::8:7:6:5:4:3:2:1")
        assertBadSplit("8:7:6:5:4:3:2:1::")
        # A trailing IPv4 address is two parts
        assertBadSplit("10:9:8:7:6:5:4:3:42.42.42.42")

    def test_bad_address_split_v6_too_many_parts(self):
        def assertBadSplit(addr):
            msg = "Exactly 8 parts expected without '::' in %r"
            with self.assertAddressError(msg, addr):
                ipaddress.IPv6Address(addr)

        assertBadSplit("3ffe:0:0:0:0:0:0:0:1")
        assertBadSplit("9:8:7:6:5:4:3:2:1")
        assertBadSplit("7:6:5:4:3:2:1")
        # A trailing IPv4 address is two parts
        assertBadSplit("9:8:7:6:5:4:3:42.42.42.42")
        assertBadSplit("7:6:5:4:3:42.42.42.42")

    def test_bad_address_split_v6_too_many_parts_with_double_colon(self):
        def assertBadSplit(addr):
            msg = "Expected at most 7 other parts with '::' in %r"
            with self.assertAddressError(msg, addr):
                ipaddress.IPv6Address(addr)

        assertBadSplit("1:2:3:4::5:6:7:8")

    def test_bad_address_split_v6_repeated_double_colon(self):
        def assertBadSplit(addr):
            msg = "At most one '::' permitted in %r"
            with self.assertAddressError(msg, addr):
                ipaddress.IPv6Address(addr)

        assertBadSplit("3ffe::1::1")
        assertBadSplit("1::2::3::4:5")
        assertBadSplit("2001::db:::1")
        assertBadSplit("3ffe::1::")
        assertBadSplit("::3ffe::1")
        assertBadSplit(":3ffe::1::1")
        assertBadSplit("3ffe::1::1:")
        assertBadSplit(":3ffe::1::1:")
        assertBadSplit(":::")
        assertBadSplit('2001:db8:::1')

    def test_bad_address_split_v6_leading_colon(self):
        def assertBadSplit(addr):
            msg = "Leading ':' only permitted as part of '::' in %r"
            with self.assertAddressError(msg, addr):
                ipaddress.IPv6Address(addr)

        assertBadSplit(":2001:db8::1")
        assertBadSplit(":1:2:3:4:5:6:7")
        assertBadSplit(":1:2:3:4:5:6:")
        assertBadSplit(":6:5:4:3:2:1::")

    def test_bad_address_split_v6_trailing_colon(self):
        def assertBadSplit(addr):
            msg = "Trailing ':' only permitted as part of '::' in %r"
            with self.assertAddressError(msg, addr):
                ipaddress.IPv6Address(addr)

        assertBadSplit("2001:db8::1:")
        assertBadSplit("1:2:3:4:5:6:7:")
        assertBadSplit("::1.2.3.4:")
        assertBadSplit("::7:6:5:4:3:2:")

    def test_bad_v4_part_in(self):
        def assertBadAddressPart(addr, v4_error):
            with self.assertAddressError("%s in %r", v4_error, addr):
                ipaddress.IPv6Address(addr)

        assertBadAddressPart("3ffe::1.net", "Expected 4 octets in '1.net'")
        assertBadAddressPart("3ffe::127.0.1",
                             "Expected 4 octets in '127.0.1'")
        assertBadAddressPart("::1.2.3",
                             "Expected 4 octets in '1.2.3'")
        assertBadAddressPart("::1.2.3.4.5",
                             "Expected 4 octets in '1.2.3.4.5'")
        assertBadAddressPart("3ffe::1.1.1.net",
                             "Only decimal digits permitted in 'net' "
                             "in '1.1.1.net'")

    def test_invalid_characters(self):
        def assertBadPart(addr, part):
            msg = "Only hex digits permitted in %r in %r" % (part, addr)
            with self.assertAddressError(re.escape(msg)):
                ipaddress.IPv6Address(addr)

        assertBadPart("3ffe::goog", "goog")
        assertBadPart("3ffe::-0", "-0")
        assertBadPart("3ffe::+0", "+0")
        assertBadPart("3ffe::-1", "-1")
        assertBadPart("1.2.3.4::", "1.2.3.4")
        assertBadPart('1234:axy::b', "axy")

    def test_part_length(self):
        def assertBadPart(addr, part):
            msg = "At most 4 characters permitted in %r in %r"
            with self.assertAddressError(msg, part, addr):
                ipaddress.IPv6Address(addr)

        assertBadPart("::00000", "00000")
        assertBadPart("3ffe::10000", "10000")
        assertBadPart("02001:db8::", "02001")
        assertBadPart('2001:888888::1', "888888")


@skipIf(sys.version_info > (3,), 'These are tested by the python test suite under Py3')
class NetmaskTestMixin_v4(CommonTestMixin_v4):
    """Input validation on interfaces and networks is very similar"""

    def test_split_netmask(self):
        addr = "1.2.3.4/32/24"
        with self.assertAddressError("Only one '/' permitted in %r" % addr):
            self.factory(addr)

    def test_address_errors(self):
        def assertBadAddress(addr, details):
            with self.assertAddressError(details):
                self.factory(addr)

        assertBadAddress("/", "Address cannot be empty")
        assertBadAddress("/8", "Address cannot be empty")
        assertBadAddress("bogus", "Expected 4 octets")
        assertBadAddress("google.com", "Expected 4 octets")
        assertBadAddress("10/8", "Expected 4 octets")
        assertBadAddress("::1.2.3.4", "Only decimal digits")
        assertBadAddress("1.2.3.256", re.escape("256 (> 255)"))

    def test_valid_netmask(self):
        assert str(self.factory('192.0.2.0/255.255.255.0')) == \
                         '192.0.2.0/24'
        for i in range(0, 33):
            # Generate and re-parse the CIDR format (trivial).
            net_str = '0.0.0.0/%d' % i
            net = self.factory(net_str)
            assert str(net) == net_str
            # Generate and re-parse the expanded netmask.
            assert str(self.factory('0.0.0.0/%s' % net.netmask)) == net_str
            # Zero prefix is treated as decimal.
            assert str(self.factory('0.0.0.0/0%d' % i)) == net_str
            # Generate and re-parse the expanded hostmask.  The ambiguous
            # cases (/0 and /32) are treated as netmasks.
            if i in (32, 0):
                net_str = '0.0.0.0/%d' % (32 - i)
            assert str(self.factory('0.0.0.0/%s' % net.hostmask)) == net_str

    def test_netmask_errors(self):
        def assertBadNetmask(addr, netmask):
            msg = "%r is not a valid netmask" % netmask
            with self.assertNetmaskError(re.escape(msg)):
                self.factory("%s/%s" % (addr, netmask))

        assertBadNetmask("1.2.3.4", "")
        assertBadNetmask("1.2.3.4", "-1")
        assertBadNetmask("1.2.3.4", "+1")
        assertBadNetmask("1.2.3.4", " 1 ")
        assertBadNetmask("1.2.3.4", "0x1")
        assertBadNetmask("1.2.3.4", "33")
        assertBadNetmask("1.2.3.4", "254.254.255.256")
        assertBadNetmask("1.2.3.4", "1.a.2.3")
        assertBadNetmask("1.1.1.1", "254.xyz.2.3")
        assertBadNetmask("1.1.1.1", "240.255.0.0")
        assertBadNetmask("1.1.1.1", "255.254.128.0")
        assertBadNetmask("1.1.1.1", "0.1.127.255")
        assertBadNetmask("1.1.1.1", "pudding")
        assertBadNetmask("1.1.1.1", "::")


@skipIf(sys.version_info > (3,), 'These are tested by the python test suite under Py3')
class InterfaceTestCase_v4(BaseTestCase, NetmaskTestMixin_v4):
    factory = ipaddress.IPv4Interface


@skipIf(sys.version_info > (3,), 'These are tested by the python test suite under Py3')
class NetworkTestCase_v4(BaseTestCase, NetmaskTestMixin_v4):
    factory = ipaddress.IPv4Network


@skipIf(sys.version_info > (3,), 'These are tested by the python test suite under Py3')
class NetmaskTestMixin_v6(CommonTestMixin_v6):
    """Input validation on interfaces and networks is very similar"""

    def test_split_netmask(self):
        addr = "cafe:cafe::/128/190"
        with self.assertAddressError("Only one '/' permitted in %r" % addr):
            self.factory(addr)

    def test_address_errors(self):
        def assertBadAddress(addr, details):
            with self.assertAddressError(details):
                self.factory(addr)

        assertBadAddress("/", "Address cannot be empty")
        assertBadAddress("/8", "Address cannot be empty")
        assertBadAddress("google.com", "At least 3 parts")
        assertBadAddress("1.2.3.4", "At least 3 parts")
        assertBadAddress("10/8", "At least 3 parts")
        assertBadAddress("1234:axy::b", "Only hex digits")

    def test_valid_netmask(self):
        # We only support CIDR for IPv6, because expanded netmasks are not
        # standard notation.
        assert str(self.factory('2001:db8::/32')) == '2001:db8::/32'
        for i in range(0, 129):
            # Generate and re-parse the CIDR format (trivial).
            net_str = '::/%d' % i
            assert str(self.factory(net_str)) == net_str
            # Zero prefix is treated as decimal.
            assert str(self.factory('::/0%d' % i)) == net_str

    def test_netmask_errors(self):
        def assertBadNetmask(addr, netmask):
            msg = "%r is not a valid netmask" % netmask
            with self.assertNetmaskError(re.escape(msg)):
                self.factory("%s/%s" % (addr, netmask))

        assertBadNetmask("::1", "")
        assertBadNetmask("::1", "::1")
        assertBadNetmask("::1", "1::")
        assertBadNetmask("::1", "-1")
        assertBadNetmask("::1", "+1")
        assertBadNetmask("::1", " 1 ")
        assertBadNetmask("::1", "0x1")
        assertBadNetmask("::1", "129")
        assertBadNetmask("::1", "1.2.3.4")
        assertBadNetmask("::1", "pudding")
        assertBadNetmask("::", "::")


@skipIf(sys.version_info > (3,), 'These are tested by the python test suite under Py3')
class InterfaceTestCase_v6(BaseTestCase, NetmaskTestMixin_v6):
    factory = ipaddress.IPv6Interface


@skipIf(sys.version_info > (3,), 'These are tested by the python test suite under Py3')
class NetworkTestCase_v6(BaseTestCase, NetmaskTestMixin_v6):
    factory = ipaddress.IPv6Network


@skipIf(sys.version_info > (3,), 'These are tested by the python test suite under Py3')
class FactoryFunctionErrors(BaseTestCase):

    def assertFactoryError(self, factory, kind):
        """Ensure a clean ValueError with the expected message"""
        addr = "camelot"
        msg = '%r does not appear to be an IPv4 or IPv6 %s'
        with self.assertCleanError(ValueError, msg, addr, kind):
            factory(addr)

    def test_ip_address(self):
        self.assertFactoryError(ipaddress.ip_address, "address")

    def test_ip_interface(self):
        self.assertFactoryError(ipaddress.ip_interface, "interface")

    def test_ip_network(self):
        self.assertFactoryError(ipaddress.ip_network, "network")


@skipIf(sys.version_info > (3,), 'These are tested by the python test suite under Py3')
class ComparisonTests(TestCase):

    v4addr = ipaddress.IPv4Address(1)
    v4net = ipaddress.IPv4Network(1)
    v4intf = ipaddress.IPv4Interface(1)
    v6addr = ipaddress.IPv6Address(1)
    v6net = ipaddress.IPv6Network(1)
    v6intf = ipaddress.IPv6Interface(1)

    v4_addresses = [v4addr, v4intf]
    v4_objects = v4_addresses + [v4net]
    v6_addresses = [v6addr, v6intf]
    v6_objects = v6_addresses + [v6net]
    objects = v4_objects + v6_objects

    def test_foreign_type_equality(self):
        # __eq__ should never raise TypeError directly
        other = object()
        for obj in self.objects:
            assert obj != other
            assert not (obj == other)
            assert obj.__eq__(other) == NotImplemented
            assert obj.__ne__(other) == NotImplemented

    def test_mixed_type_equality(self):
        # Ensure none of the internal objects accidentally
        # expose the right set of attributes to become "equal"
        for lhs in self.objects:
            for rhs in self.objects:
                if lhs is rhs:
                    continue
                assert lhs != rhs

    def test_containment(self):
        for obj in self.v4_addresses:
            assert obj in self.v4net
        for obj in self.v6_addresses:
            assert obj in self.v6net
        for obj in self.v4_objects + [self.v6net]:
            assert obj not in self.v6net
        for obj in self.v6_objects + [self.v4net]:
            assert obj not in self.v4net

    def test_mixed_type_ordering(self):
        for lhs in self.objects:
            for rhs in self.objects:
                if isinstance(lhs, type(rhs)) or isinstance(rhs, type(lhs)):
                    continue
                with pytest.raises(TypeError):
                    lhs < rhs
                with pytest.raises(TypeError):
                    lhs > rhs
                with pytest.raises(TypeError):
                    lhs <= rhs
                with pytest.raises(TypeError):
                    lhs >= rhs

    def test_mixed_type_key(self):
        # with get_mixed_type_key, you can sort addresses and network.
        v4_ordered = [self.v4addr, self.v4net, self.v4intf]
        v6_ordered = [self.v6addr, self.v6net, self.v6intf]
        assert v4_ordered == \
                         sorted(self.v4_objects,
                                key=ipaddress.get_mixed_type_key)
        assert v6_ordered == \
                         sorted(self.v6_objects,
                                key=ipaddress.get_mixed_type_key)
        assert v4_ordered + v6_ordered == \
                         sorted(self.objects,
                                key=ipaddress.get_mixed_type_key)
        assert NotImplemented == ipaddress.get_mixed_type_key(object)

    def test_incompatible_versions(self):
        # These should always raise TypeError
        v4addr = ipaddress.ip_address('1.1.1.1')
        v4net = ipaddress.ip_network('1.1.1.1')
        v6addr = ipaddress.ip_address('::1')
        v6net = ipaddress.ip_address('::1')

        with pytest.raises(TypeError):
            v4addr.__lt__(v6addr)
        with pytest.raises(TypeError):
            v4addr.__gt__(v6addr)
        with pytest.raises(TypeError):
            v4net.__lt__(v6net)
        with pytest.raises(TypeError):
            v4net.__gt__(v6net)

        with pytest.raises(TypeError):
            v6addr.__lt__(v4addr)
        with pytest.raises(TypeError):
            v6addr.__gt__(v4addr)
        with pytest.raises(TypeError):
            v6net.__lt__(v4net)
        with pytest.raises(TypeError):
            v6net.__gt__(v4net)


@skipIf(sys.version_info > (3,), 'These are tested by the python test suite under Py3')
class IpaddrUnitTest(TestCase):

    def setUp(self):
        self.ipv4_address = ipaddress.IPv4Address('1.2.3.4')
        self.ipv4_interface = ipaddress.IPv4Interface('1.2.3.4/24')
        self.ipv4_network = ipaddress.IPv4Network('1.2.3.0/24')
        #self.ipv4_hostmask = ipaddress.IPv4Interface('10.0.0.1/0.255.255.255')
        self.ipv6_address = ipaddress.IPv6Interface(
            '2001:658:22a:cafe:200:0:0:1')
        self.ipv6_interface = ipaddress.IPv6Interface(
            '2001:658:22a:cafe:200:0:0:1/64')
        self.ipv6_network = ipaddress.IPv6Network('2001:658:22a:cafe::/64')

    def tearDown(self):
        for attrname in ('ipv4_network', 'ipv4_interface', 'ipv4_address',
                'ipv6_network', 'ipv6_interface', 'ipv6_address'):
            try:
                delattr(self, attrname)
            except AttributeError:
                continue

    def testRepr(self):
        assert "IPv4Interface('1.2.3.4/32')" == \
                         repr(ipaddress.IPv4Interface('1.2.3.4'))
        assert "IPv6Interface('::1/128')" == \
                         repr(ipaddress.IPv6Interface('::1'))

    # issue57
    def testAddressIntMath(self):
        assert ipaddress.IPv4Address('1.1.1.1') + 255 == \
                         ipaddress.IPv4Address('1.1.2.0')
        assert ipaddress.IPv4Address('1.1.1.1') - 256 == \
                         ipaddress.IPv4Address('1.1.0.1')
        assert ipaddress.IPv6Address('::1') + (2**16 - 2) == \
                         ipaddress.IPv6Address('::ffff')
        assert ipaddress.IPv6Address('::ffff') - (2**16 - 2) == \
                         ipaddress.IPv6Address('::1')

    def testInvalidIntToBytes(self):
        with pytest.raises(ValueError):
            ipaddress.v4_int_to_packed(-1)
        with pytest.raises(ValueError):
            ipaddress.v4_int_to_packed(2 ** ipaddress.IPV4LENGTH)
        with pytest.raises(ValueError):
            ipaddress.v6_int_to_packed(-1)
        with pytest.raises(ValueError):
            ipaddress.v6_int_to_packed(2 ** ipaddress.IPV6LENGTH)

    def testInternals(self):
        first, last = ipaddress._find_address_range([
            ipaddress.IPv4Address('10.10.10.10'),
            ipaddress.IPv4Address('10.10.10.12')])
        assert first == last
        assert 128 == ipaddress._count_righthand_zero_bits(0, 128)
        assert "IPv4Network('1.2.3.0/24')" == repr(self.ipv4_network)

    def testMissingAddressVersion(self):
        class Broken(ipaddress._BaseAddress):
            pass
        broken = Broken('127.0.0.1')
        with pytest.raises(NotImplementedError, match="Broken.*version"):
            broken.version

    def testMissingNetworkVersion(self):
        class Broken(ipaddress._BaseNetwork):
            pass
        broken = Broken('127.0.0.1')
        with pytest.raises(NotImplementedError, match="Broken.*version"):
            broken.version

    def testMissingAddressClass(self):
        class Broken(ipaddress._BaseNetwork):
            pass
        broken = Broken('127.0.0.1')
        with pytest.raises(NotImplementedError, match="Broken.*address"):
            broken._address_class

    def testGetNetwork(self):
        assert int(self.ipv4_network.network_address) == 16909056
        assert str(self.ipv4_network.network_address) == '1.2.3.0'

        assert int(self.ipv6_network.network_address) == \
                         42540616829182469433403647294022090752
        assert str(self.ipv6_network.network_address) == \
                         '2001:658:22a:cafe::'
        assert str(self.ipv6_network.hostmask) == \
                         '::ffff:ffff:ffff:ffff'

    def testIpFromInt(self):
        assert self.ipv4_interface._ip == \
                         ipaddress.IPv4Interface(16909060)._ip

        ipv4 = ipaddress.ip_network('1.2.3.4')
        ipv6 = ipaddress.ip_network('2001:658:22a:cafe:200:0:0:1')
        assert ipv4 == ipaddress.ip_network(int(ipv4.network_address))
        assert ipv6 == ipaddress.ip_network(int(ipv6.network_address))

        v6_int = 42540616829182469433547762482097946625
        assert self.ipv6_interface._ip == \
                         ipaddress.IPv6Interface(v6_int)._ip

        assert ipaddress.ip_network(self.ipv4_address._ip).version == \
                         4
        assert ipaddress.ip_network(self.ipv6_address._ip).version == \
                         6

    def testIpFromPacked(self):
        address = ipaddress.ip_address
        assert self.ipv4_interface._ip == \
                         ipaddress.ip_interface(bytearray(b'\x01\x02\x03\x04'))._ip
        assert address('255.254.253.252') == \
                         address(bytearray(b'\xff\xfe\xfd\xfc'))
        assert self.ipv6_interface.ip == \
                         ipaddress.ip_interface(
                    bytearray(b'\x20\x01\x06\x58\x02\x2a\xca\xfe'
                    b'\x02\x00\x00\x00\x00\x00\x00\x01')).ip
        assert address('ffff:2:3:4:ffff::') == \
                         address(bytearray(b'\xff\xff\x00\x02\x00\x03\x00\x04') +
                            bytearray(b'\xff\xff') + bytearray(b'\x00') * 6)
        assert address('::') == \
                         address(bytearray(b'\x00') * 16)

    def testGetIp(self):
        assert int(self.ipv4_interface.ip) == 16909060
        assert str(self.ipv4_interface.ip) == '1.2.3.4'

        assert int(self.ipv6_interface.ip) == \
                         42540616829182469433547762482097946625
        assert str(self.ipv6_interface.ip) == \
                         '2001:658:22a:cafe:200::1'

    def testGetNetmask(self):
        assert int(self.ipv4_network.netmask) == 4294967040
        assert str(self.ipv4_network.netmask) == '255.255.255.0'
        assert int(self.ipv6_network.netmask) == \
                         340282366920938463444927863358058659840
        assert self.ipv6_network.prefixlen == 64

    def testZeroNetmask(self):
        ipv4_zero_netmask = ipaddress.IPv4Interface('1.2.3.4/0')
        assert int(ipv4_zero_netmask.network.netmask) == 0
        assert ipv4_zero_netmask._prefix_from_prefix_string('0') == 0
        assert ipv4_zero_netmask._is_valid_netmask('0')
        assert ipv4_zero_netmask._is_valid_netmask('0.0.0.0')
        assert not ipv4_zero_netmask._is_valid_netmask('invalid')

        ipv6_zero_netmask = ipaddress.IPv6Interface('::1/0')
        assert int(ipv6_zero_netmask.network.netmask) == 0
        assert ipv6_zero_netmask._prefix_from_prefix_string('0') == 0

    def testIPv4NetAndHostmasks(self):
        net = self.ipv4_network
        assert not net._is_valid_netmask('invalid')
        assert net._is_valid_netmask('128.128.128.128')
        assert not net._is_valid_netmask('128.128.128.127')
        assert not net._is_valid_netmask('128.128.128.255')
        assert net._is_valid_netmask('255.128.128.128')

        assert not net._is_hostmask('invalid')
        assert net._is_hostmask('128.255.255.255')
        assert not net._is_hostmask('255.255.255.255')
        assert not net._is_hostmask('1.2.3.4')

        net = ipaddress.IPv4Network('127.0.0.0/0.0.0.255')
        assert net.prefixlen == 24

    def testGetBroadcast(self):
        assert int(self.ipv4_network.broadcast_address) == 16909311
        assert str(self.ipv4_network.broadcast_address) == '1.2.3.255'

        assert int(self.ipv6_network.broadcast_address) == \
                         42540616829182469451850391367731642367
        assert str(self.ipv6_network.broadcast_address) == \
                         '2001:658:22a:cafe:ffff:ffff:ffff:ffff'

    def testGetPrefixlen(self):
        assert self.ipv4_interface.network.prefixlen == 24
        assert self.ipv6_interface.network.prefixlen == 64

    def testGetSupernet(self):
        assert self.ipv4_network.supernet().prefixlen == 23
        assert str(self.ipv4_network.supernet().network_address) == \
                         '1.2.2.0'
        assert ipaddress.IPv4Interface('0.0.0.0/0').network.supernet() == \
            ipaddress.IPv4Network('0.0.0.0/0')

        assert self.ipv6_network.supernet().prefixlen == 63
        assert str(self.ipv6_network.supernet().network_address) == \
                         '2001:658:22a:cafe::'
        assert ipaddress.IPv6Interface('::0/0').network.supernet() == \
                         ipaddress.IPv6Network('::0/0')

    def testGetSupernet3(self):
        assert self.ipv4_network.supernet(3).prefixlen == 21
        assert str(self.ipv4_network.supernet(3).network_address) == \
                         '1.2.0.0'

        assert self.ipv6_network.supernet(3).prefixlen == 61
        assert str(self.ipv6_network.supernet(3).network_address) == \
                         '2001:658:22a:caf8::'

    def testGetSupernet4(self):
        with pytest.raises(ValueError):
            self.ipv4_network.supernet(prefixlen_diff=2, new_prefix=1)
        with pytest.raises(ValueError):
            self.ipv4_network.supernet(new_prefix=25)
        assert self.ipv4_network.supernet(prefixlen_diff=2) == \
                         self.ipv4_network.supernet(new_prefix=22)

        with pytest.raises(ValueError):
            self.ipv6_network.supernet(prefixlen_diff=2, new_prefix=1)
        with pytest.raises(ValueError):
            self.ipv6_network.supernet(new_prefix=65)
        assert self.ipv6_network.supernet(prefixlen_diff=2) == \
                         self.ipv6_network.supernet(new_prefix=62)

    def testHosts(self):
        hosts = list(self.ipv4_network.hosts())
        assert 254 == len(hosts)
        assert ipaddress.IPv4Address('1.2.3.1') == hosts[0]
        assert ipaddress.IPv4Address('1.2.3.254') == hosts[-1]

        # special case where only 1 bit is left for address
        assert [ipaddress.IPv4Address('2.0.0.0'),
                          ipaddress.IPv4Address('2.0.0.1')] == \
                         list(ipaddress.ip_network('2.0.0.0/31').hosts())

    def testFancySubnetting(self):
        assert sorted(self.ipv4_network.subnets(prefixlen_diff=3)) == \
                         sorted(self.ipv4_network.subnets(new_prefix=27))
        with pytest.raises(ValueError):
            list(self.ipv4_network.subnets(new_prefix=23))
        with pytest.raises(ValueError):
            list(self.ipv4_network.subnets(prefixlen_diff=3,
                                                   new_prefix=27))
        assert sorted(self.ipv6_network.subnets(prefixlen_diff=4)) == \
                         sorted(self.ipv6_network.subnets(new_prefix=68))
        with pytest.raises(ValueError):
            list(self.ipv6_network.subnets(new_prefix=63))
        with pytest.raises(ValueError):
            list(self.ipv6_network.subnets(prefixlen_diff=4,
                                                   new_prefix=68))

    def testGetSubnets(self):
        assert list(self.ipv4_network.subnets())[0].prefixlen == 25
        assert str(list(
                    self.ipv4_network.subnets())[0].network_address) == \
                         '1.2.3.0'
        assert str(list(
                    self.ipv4_network.subnets())[1].network_address) == \
                         '1.2.3.128'

        assert list(self.ipv6_network.subnets())[0].prefixlen == 65

    def testGetSubnetForSingle32(self):
        ip = ipaddress.IPv4Network('1.2.3.4/32')
        subnets1 = [str(x) for x in ip.subnets()]
        subnets2 = [str(x) for x in ip.subnets(2)]
        assert subnets1 == ['1.2.3.4/32']
        assert subnets1 == subnets2

    def testGetSubnetForSingle128(self):
        ip = ipaddress.IPv6Network('::1/128')
        subnets1 = [str(x) for x in ip.subnets()]
        subnets2 = [str(x) for x in ip.subnets(2)]
        assert subnets1 == ['::1/128']
        assert subnets1 == subnets2

    def testSubnet2(self):
        ips = [str(x) for x in self.ipv4_network.subnets(2)]
        assert ips == \
            ['1.2.3.0/26', '1.2.3.64/26', '1.2.3.128/26', '1.2.3.192/26']

        ipsv6 = [str(x) for x in self.ipv6_network.subnets(2)]
        assert ipsv6 == \
            ['2001:658:22a:cafe::/66',
             '2001:658:22a:cafe:4000::/66',
             '2001:658:22a:cafe:8000::/66',
             '2001:658:22a:cafe:c000::/66']

    def testSubnetFailsForLargeCidrDiff(self):
        with pytest.raises(ValueError):
            list(self.ipv4_interface.network.subnets(9))
        with pytest.raises(ValueError):
            list(self.ipv4_network.subnets(9))
        with pytest.raises(ValueError):
            list(self.ipv6_interface.network.subnets(65))
        with pytest.raises(ValueError):
            list(self.ipv6_network.subnets(65))

    def testSupernetFailsForLargeCidrDiff(self):
        with pytest.raises(ValueError):
            self.ipv4_interface.network.supernet(25)
        with pytest.raises(ValueError):
            self.ipv6_interface.network.supernet(65)

    def testSubnetFailsForNegativeCidrDiff(self):
        with pytest.raises(ValueError):
            list(self.ipv4_interface.network.subnets(-1))
        with pytest.raises(ValueError):
            list(self.ipv4_network.subnets(-1))
        with pytest.raises(ValueError):
            list(self.ipv6_interface.network.subnets(-1))
        with pytest.raises(ValueError):
            list(self.ipv6_network.subnets(-1))

    def testGetNum_Addresses(self):
        assert self.ipv4_network.num_addresses == 256
        assert list(self.ipv4_network.subnets())[0].num_addresses == \
                         128
        assert self.ipv4_network.supernet().num_addresses == 512

        assert self.ipv6_network.num_addresses == 18446744073709551616
        assert list(self.ipv6_network.subnets())[0].num_addresses == \
                         9223372036854775808
        assert self.ipv6_network.supernet().num_addresses == \
                         36893488147419103232

    def testContains(self):
        assert ipaddress.IPv4Interface('1.2.3.128/25') in \
                      self.ipv4_network
        assert ipaddress.IPv4Interface('1.2.4.1/24') not in \
                         self.ipv4_network
        # We can test addresses and string as well.
        addr1 = ipaddress.IPv4Address('1.2.3.37')
        assert addr1 in self.ipv4_network
        # issue 61, bad network comparison on like-ip'd network objects
        # with identical broadcast addresses.
        assert not ipaddress.IPv4Network('1.1.0.0/16').__contains__(
                ipaddress.IPv4Network('1.0.0.0/15'))

    def testNth(self):
        assert str(self.ipv4_network[5]) == '1.2.3.5'
        with pytest.raises(IndexError):
            self.ipv4_network.__getitem__(256)

        assert str(self.ipv6_network[5]) == \
                         '2001:658:22a:cafe::5'

    def testGetitem(self):
        # http://code.google.com/p/ipaddr-py/issues/detail?id=15
        addr = ipaddress.IPv4Network('172.31.255.128/255.255.255.240')
        assert 28 == addr.prefixlen
        addr_list = list(addr)
        assert '172.31.255.128' == str(addr_list[0])
        assert '172.31.255.128' == str(addr[0])
        assert '172.31.255.143' == str(addr_list[-1])
        assert '172.31.255.143' == str(addr[-1])
        assert addr_list[-1] == addr[-1]

    def testEqual(self):
        assert self.ipv4_interface == \
                        ipaddress.IPv4Interface('1.2.3.4/24')
        assert not (self.ipv4_interface ==
                         ipaddress.IPv4Interface('1.2.3.4/23'))
        assert not (self.ipv4_interface ==
                         ipaddress.IPv6Interface('::1.2.3.4/24'))
        assert not (self.ipv4_interface == '')
        assert not (self.ipv4_interface == [])
        assert not (self.ipv4_interface == 2)

        assert self.ipv6_interface == \
            ipaddress.IPv6Interface('2001:658:22a:cafe:200::1/64')
        assert not (self.ipv6_interface ==
            ipaddress.IPv6Interface('2001:658:22a:cafe:200::1/63'))
        assert not (self.ipv6_interface ==
                         ipaddress.IPv4Interface('1.2.3.4/23'))
        assert not (self.ipv6_interface == '')
        assert not (self.ipv6_interface == [])
        assert not (self.ipv6_interface == 2)

    def testNotEqual(self):
        assert not (self.ipv4_interface !=
                         ipaddress.IPv4Interface('1.2.3.4/24'))
        assert self.ipv4_interface != \
                        ipaddress.IPv4Interface('1.2.3.4/23')
        assert self.ipv4_interface != \
                        ipaddress.IPv6Interface('::1.2.3.4/24')
        assert self.ipv4_interface != ''
        assert self.ipv4_interface != []
        assert self.ipv4_interface != 2

        assert self.ipv4_address != \
                         ipaddress.IPv4Address('1.2.3.5')
        assert self.ipv4_address != ''
        assert self.ipv4_address != []
        assert self.ipv4_address != 2

        assert not (self.ipv6_interface !=
            ipaddress.IPv6Interface('2001:658:22a:cafe:200::1/64'))
        assert self.ipv6_interface != \
            ipaddress.IPv6Interface('2001:658:22a:cafe:200::1/63')
        assert self.ipv6_interface != \
                        ipaddress.IPv4Interface('1.2.3.4/23')
        assert self.ipv6_interface != ''
        assert self.ipv6_interface != []
        assert self.ipv6_interface != 2

        assert self.ipv6_address != \
                        ipaddress.IPv4Address('1.2.3.4')
        assert self.ipv6_address != ''
        assert self.ipv6_address != []
        assert self.ipv6_address != 2

    def testSlash32Constructor(self):
        assert str(ipaddress.IPv4Interface(
                    '1.2.3.4/255.255.255.255')) == '1.2.3.4/32'

    def testSlash128Constructor(self):
        assert str(ipaddress.IPv6Interface('::1/128')) == \
                                  '::1/128'

    def testSlash0Constructor(self):
        assert str(ipaddress.IPv4Interface('1.2.3.4/0.0.0.0')) == \
                          '1.2.3.4/0'

    def testCollapsing(self):
        # test only IP addresses including some duplicates
        ip1 = ipaddress.IPv4Address('1.1.1.0')
        ip2 = ipaddress.IPv4Address('1.1.1.1')
        ip3 = ipaddress.IPv4Address('1.1.1.2')
        ip4 = ipaddress.IPv4Address('1.1.1.3')
        ip5 = ipaddress.IPv4Address('1.1.1.4')
        ip6 = ipaddress.IPv4Address('1.1.1.0')
        # check that addreses are subsumed properly.
        collapsed = ipaddress.collapse_addresses(
            [ip1, ip2, ip3, ip4, ip5, ip6])
        assert list(collapsed) == \
                [ipaddress.IPv4Network('1.1.1.0/30'),
                 ipaddress.IPv4Network('1.1.1.4/32')]

        # test a mix of IP addresses and networks including some duplicates
        ip1 = ipaddress.IPv4Address('1.1.1.0')
        ip2 = ipaddress.IPv4Address('1.1.1.1')
        ip3 = ipaddress.IPv4Address('1.1.1.2')
        ip4 = ipaddress.IPv4Address('1.1.1.3')
        #ip5 = ipaddress.IPv4Interface('1.1.1.4/30')
        #ip6 = ipaddress.IPv4Interface('1.1.1.4/30')
        # check that addreses are subsumed properly.
        collapsed = ipaddress.collapse_addresses([ip1, ip2, ip3, ip4])
        assert list(collapsed) == \
                         [ipaddress.IPv4Network('1.1.1.0/30')]

        # test only IP networks
        ip1 = ipaddress.IPv4Network('1.1.0.0/24')
        ip2 = ipaddress.IPv4Network('1.1.1.0/24')
        ip3 = ipaddress.IPv4Network('1.1.2.0/24')
        ip4 = ipaddress.IPv4Network('1.1.3.0/24')
        ip5 = ipaddress.IPv4Network('1.1.4.0/24')
        # stored in no particular order b/c we want CollapseAddr to call
        # [].sort
        ip6 = ipaddress.IPv4Network('1.1.0.0/22')
        # check that addreses are subsumed properly.
        collapsed = ipaddress.collapse_addresses([ip1, ip2, ip3, ip4, ip5,
                                                     ip6])
        assert list(collapsed) == \
                         [ipaddress.IPv4Network('1.1.0.0/22'),
                          ipaddress.IPv4Network('1.1.4.0/24')]

        # test that two addresses are supernet'ed properly
        collapsed = ipaddress.collapse_addresses([ip1, ip2])
        assert list(collapsed) == \
                         [ipaddress.IPv4Network('1.1.0.0/23')]

        # test same IP networks
        ip_same1 = ip_same2 = ipaddress.IPv4Network('1.1.1.1/32')
        assert list(ipaddress.collapse_addresses(
                    [ip_same1, ip_same2])) == \
                         [ip_same1]

        # test same IP addresses
        ip_same1 = ip_same2 = ipaddress.IPv4Address('1.1.1.1')
        assert list(ipaddress.collapse_addresses(
                    [ip_same1, ip_same2])) == \
                         [ipaddress.ip_network('1.1.1.1/32')]
        ip1 = ipaddress.IPv6Network('2001::/100')
        ip2 = ipaddress.IPv6Network('2001::/120')
        ip3 = ipaddress.IPv6Network('2001::/96')
        # test that ipv6 addresses are subsumed properly.
        collapsed = ipaddress.collapse_addresses([ip1, ip2, ip3])
        assert list(collapsed) == [ip3]

        # the toejam test
        addr_tuples = [
                (ipaddress.ip_address('1.1.1.1'),
                 ipaddress.ip_address('::1')),
                (ipaddress.IPv4Network('1.1.0.0/24'),
                 ipaddress.IPv6Network('2001::/120')),
                (ipaddress.IPv4Network('1.1.0.0/32'),
                 ipaddress.IPv6Network('2001::/128')),
        ]
        for ip1, ip2 in addr_tuples:
            with pytest.raises(TypeError):
                ipaddress.collapse_addresses([ip1, ip2])

    def testSummarizing(self):
        #ip = ipaddress.ip_address
        #ipnet = ipaddress.ip_network
        summarize = ipaddress.summarize_address_range
        ip1 = ipaddress.ip_address('1.1.1.0')
        ip2 = ipaddress.ip_address('1.1.1.255')

        # summarize works only for IPv4 & IPv6
        class IPv7Address(ipaddress.IPv6Address):
            @property
            def version(self):
                return 7
        ip_invalid1 = IPv7Address('::1')
        ip_invalid2 = IPv7Address('::1')
        with pytest.raises(ValueError):
            list(summarize(ip_invalid1, ip_invalid2))
        # test that a summary over ip4 & ip6 fails
        with pytest.raises(TypeError):
            list(summarize(ip1, ipaddress.IPv6Address('::1')))
        # test a /24 is summarized properly
        assert list(summarize(ip1, ip2))[0] == \
                         ipaddress.ip_network('1.1.1.0/24')
        # test an  IPv4 range that isn't on a network byte boundary
        ip2 = ipaddress.ip_address('1.1.1.8')
        assert list(summarize(ip1, ip2)) == \
                         [ipaddress.ip_network('1.1.1.0/29'),
                          ipaddress.ip_network('1.1.1.8')]
        # all!
        ip1 = ipaddress.IPv4Address(0)
        ip2 = ipaddress.IPv4Address(ipaddress.IPv4Address._ALL_ONES)
        assert [ipaddress.IPv4Network('0.0.0.0/0')] == \
                         list(summarize(ip1, ip2))

        ip1 = ipaddress.ip_address('1::')
        ip2 = ipaddress.ip_address('1:ffff:ffff:ffff:ffff:ffff:ffff:ffff')
        # test a IPv6 is sumamrized properly
        assert list(summarize(ip1, ip2))[0] == \
                         ipaddress.ip_network('1::/16')
        # test an IPv6 range that isn't on a network byte boundary
        ip2 = ipaddress.ip_address('2::')
        assert list(summarize(ip1, ip2)) == \
                         [ipaddress.ip_network('1::/16'),
                          ipaddress.ip_network('2::/128')]

        # test exception raised when first is greater than last
        with pytest.raises(ValueError):
            list(summarize(ipaddress.ip_address('1.1.1.0'),
                                    ipaddress.ip_address('1.1.0.0')))
        # test exception raised when first and last aren't IP addresses
        with pytest.raises(TypeError):
            list(summarize(ipaddress.ip_network('1.1.1.0'),
                                    ipaddress.ip_network('1.1.0.0')))
        with pytest.raises(TypeError):
            list(summarize(ipaddress.ip_network('1.1.1.0'),
                                    ipaddress.ip_network('1.1.0.0')))
        # test exception raised when first and last are not same version
        with pytest.raises(TypeError):
            list(summarize(ipaddress.ip_address('::'),
                                    ipaddress.ip_network('1.1.0.0')))

    def testAddressComparison(self):
        assert ipaddress.ip_address('1.1.1.1') <= \
                        ipaddress.ip_address('1.1.1.1')
        assert ipaddress.ip_address('1.1.1.1') <= \
                        ipaddress.ip_address('1.1.1.2')
        assert ipaddress.ip_address('::1') <= \
                        ipaddress.ip_address('::1')
        assert ipaddress.ip_address('::1') <= \
                        ipaddress.ip_address('::2')

    def testInterfaceComparison(self):
        assert ipaddress.ip_interface('1.1.1.1') <= \
                        ipaddress.ip_interface('1.1.1.1')
        assert ipaddress.ip_interface('1.1.1.1') <= \
                        ipaddress.ip_interface('1.1.1.2')
        assert ipaddress.ip_interface('::1') <= \
                        ipaddress.ip_interface('::1')
        assert ipaddress.ip_interface('::1') <= \
                        ipaddress.ip_interface('::2')

    def testNetworkComparison(self):
        # ip1 and ip2 have the same network address
        ip1 = ipaddress.IPv4Network('1.1.1.0/24')
        ip2 = ipaddress.IPv4Network('1.1.1.0/32')
        ip3 = ipaddress.IPv4Network('1.1.2.0/24')

        assert ip1 < ip3
        assert ip3 > ip2

        assert ip1.compare_networks(ip1) == 0

        # if addresses are the same, sort by netmask
        assert ip1.compare_networks(ip2) == -1
        assert ip2.compare_networks(ip1) == 1

        assert ip1.compare_networks(ip3) == -1
        assert ip3.compare_networks(ip1) == 1
        assert ip1._get_networks_key() < ip3._get_networks_key()

        ip1 = ipaddress.IPv6Network('2001:2000::/96')
        ip2 = ipaddress.IPv6Network('2001:2001::/96')
        ip3 = ipaddress.IPv6Network('2001:ffff:2000::/96')

        assert ip1 < ip3
        assert ip3 > ip2
        assert ip1.compare_networks(ip3) == -1
        assert ip1._get_networks_key() < ip3._get_networks_key()

        # Test comparing different protocols.
        # Should always raise a TypeError.
        with pytest.raises(TypeError):
            self.ipv4_network.compare_networks(self.ipv6_network)
        ipv6 = ipaddress.IPv6Interface('::/0')
        ipv4 = ipaddress.IPv4Interface('0.0.0.0/0')
        with pytest.raises(TypeError):
            ipv4.__lt__(ipv6)
        with pytest.raises(TypeError):
            ipv4.__gt__(ipv6)
        with pytest.raises(TypeError):
            ipv6.__lt__(ipv4)
        with pytest.raises(TypeError):
            ipv6.__gt__(ipv4)

        # Regression test for issue 19.
        ip1 = ipaddress.ip_network('10.1.2.128/25')
        assert not (ip1 < ip1)
        assert not (ip1 > ip1)
        ip2 = ipaddress.ip_network('10.1.3.0/24')
        assert ip1 < ip2
        assert not (ip2 < ip1)
        assert not (ip1 > ip2)
        assert ip2 > ip1
        ip3 = ipaddress.ip_network('10.1.3.0/25')
        assert ip2 < ip3
        assert not (ip3 < ip2)
        assert not (ip2 > ip3)
        assert ip3 > ip2

        # Regression test for issue 28.
        ip1 = ipaddress.ip_network('10.10.10.0/31')
        ip2 = ipaddress.ip_network('10.10.10.0')
        ip3 = ipaddress.ip_network('10.10.10.2/31')
        ip4 = ipaddress.ip_network('10.10.10.2')
        sorted = [ip1, ip2, ip3, ip4]
        unsorted = [ip2, ip4, ip1, ip3]
        unsorted.sort()
        assert sorted == unsorted
        unsorted = [ip4, ip1, ip3, ip2]
        unsorted.sort()
        assert sorted == unsorted
        with pytest.raises(TypeError):
            ip1.__lt__(ipaddress.ip_address('10.10.10.0'))
        with pytest.raises(TypeError):
            ip2.__lt__(ipaddress.ip_address('10.10.10.0'))

        # <=, >=
        assert ipaddress.ip_network('1.1.1.1') <= \
                        ipaddress.ip_network('1.1.1.1')
        assert ipaddress.ip_network('1.1.1.1') <= \
                        ipaddress.ip_network('1.1.1.2')
        assert not (ipaddress.ip_network('1.1.1.2') <=
                        ipaddress.ip_network('1.1.1.1'))
        assert ipaddress.ip_network('::1') <= \
                        ipaddress.ip_network('::1')
        assert ipaddress.ip_network('::1') <= \
                        ipaddress.ip_network('::2')
        assert not (ipaddress.ip_network('::2') <=
                         ipaddress.ip_network('::1'))

    def testStrictNetworks(self):
        with pytest.raises(ValueError):
            ipaddress.ip_network('192.168.1.1/24')
        with pytest.raises(ValueError):
            ipaddress.ip_network('::1/120')

    def testOverlaps(self):
        other = ipaddress.IPv4Network('1.2.3.0/30')
        other2 = ipaddress.IPv4Network('1.2.2.0/24')
        other3 = ipaddress.IPv4Network('1.2.2.64/26')
        assert self.ipv4_network.overlaps(other)
        assert not self.ipv4_network.overlaps(other2)
        assert other2.overlaps(other3)

    def testEmbeddedIpv4(self):
        ipv4_string = '192.168.0.1'
        ipv4 = ipaddress.IPv4Interface(ipv4_string)
        v4compat_ipv6 = ipaddress.IPv6Interface('::%s' % ipv4_string)
        assert int(v4compat_ipv6.ip) == int(ipv4.ip)
        v4mapped_ipv6 = ipaddress.IPv6Interface('::ffff:%s' % ipv4_string)
        assert v4mapped_ipv6.ip != ipv4.ip
        with pytest.raises(ipaddress.AddressValueError):
            ipaddress.IPv6Interface('2001:1.1.1.1:1.1.1.1')

    # Issue 67: IPv6 with embedded IPv4 address not recognized.
    def testIPv6AddressTooLarge(self):
        # RFC4291 2.5.5.2
        assert ipaddress.ip_address('::FFFF:192.0.2.1') == \
                          ipaddress.ip_address('::FFFF:c000:201')
        # RFC4291 2.2 (part 3) x::d.d.d.d
        assert ipaddress.ip_address('FFFF::192.0.2.1') == \
                          ipaddress.ip_address('FFFF::c000:201')

    def testIPVersion(self):
        assert self.ipv4_address.version == 4
        assert self.ipv6_address.version == 6

    def testMaxPrefixLength(self):
        assert self.ipv4_interface.max_prefixlen == 32
        assert self.ipv6_interface.max_prefixlen == 128

    def testPacked(self):
        assert self.ipv4_address.packed == \
                         bytearray(b'\x01\x02\x03\x04')
        assert ipaddress.IPv4Interface('255.254.253.252').packed == \
                         bytearray(b'\xff\xfe\xfd\xfc')
        assert self.ipv6_address.packed == \
                         bytearray(b'\x20\x01\x06\x58\x02\x2a\xca\xfe'
                         b'\x02\x00\x00\x00\x00\x00\x00\x01')
        assert ipaddress.IPv6Interface('ffff:2:3:4:ffff::').packed == \
                         bytearray(b'\xff\xff\x00\x02\x00\x03\x00\x04\xff\xff') \
                            + bytearray(b'\x00') * 6
        assert ipaddress.IPv6Interface('::1:0:0:0:0').packed == \
                         bytearray(b'\x00') * 6 + bytearray(b'\x00\x01') + bytearray(b'\x00') * 8

    def testIpType(self):
        ipv4net = ipaddress.ip_network('1.2.3.4')
        ipv4addr = ipaddress.ip_address('1.2.3.4')
        ipv6net = ipaddress.ip_network('::1.2.3.4')
        ipv6addr = ipaddress.ip_address('::1.2.3.4')
        assert ipaddress.IPv4Network == type(ipv4net)
        assert ipaddress.IPv4Address == type(ipv4addr)
        assert ipaddress.IPv6Network == type(ipv6net)
        assert ipaddress.IPv6Address == type(ipv6addr)

    def testReservedIpv4(self):
        # test networks
        assert ipaddress.ip_interface(
                '224.1.1.1/31').is_multicast is True
        assert ipaddress.ip_network('240.0.0.0').is_multicast is False
        assert ipaddress.ip_network('240.0.0.0').is_reserved is True

        assert ipaddress.ip_interface(
                '192.168.1.1/17').is_private is True
        assert ipaddress.ip_network('192.169.0.0').is_private is False
        assert ipaddress.ip_network(
                '10.255.255.255').is_private is True
        assert ipaddress.ip_network('11.0.0.0').is_private is False
        assert ipaddress.ip_network('11.0.0.0').is_reserved is False
        assert ipaddress.ip_network(
                '172.31.255.255').is_private is True
        assert ipaddress.ip_network('172.32.0.0').is_private is False
        assert ipaddress.ip_network('169.254.1.0/24').is_link_local is True

        assert ipaddress.ip_interface(
                              '169.254.100.200/24').is_link_local is True
        assert ipaddress.ip_interface(
                              '169.255.100.200/24').is_link_local is False

        assert ipaddress.ip_network(
                              '127.100.200.254/32').is_loopback is True
        assert ipaddress.ip_network(
                '127.42.0.0/16').is_loopback is True
        assert ipaddress.ip_network('128.0.0.0').is_loopback is False
        assert ipaddress.ip_network('100.64.0.0/10').is_private is False
        assert ipaddress.ip_network('100.64.0.0/10').is_global is False

        assert ipaddress.ip_network('192.0.2.128/25').is_private is True
        assert ipaddress.ip_network('192.0.3.0/24').is_global is True

        # test addresses
        assert ipaddress.ip_address('0.0.0.0').is_unspecified is True
        assert ipaddress.ip_address('224.1.1.1').is_multicast is True
        assert ipaddress.ip_address('240.0.0.0').is_multicast is False
        assert ipaddress.ip_address('240.0.0.1').is_reserved is True
        assert ipaddress.ip_address('239.255.255.255').is_reserved is False

        assert ipaddress.ip_address('192.168.1.1').is_private is True
        assert ipaddress.ip_address('192.169.0.0').is_private is False
        assert ipaddress.ip_address(
                '10.255.255.255').is_private is True
        assert ipaddress.ip_address('11.0.0.0').is_private is False
        assert ipaddress.ip_address(
                '172.31.255.255').is_private is True
        assert ipaddress.ip_address('172.32.0.0').is_private is False

        assert ipaddress.ip_address('169.254.100.200').is_link_local is True
        assert ipaddress.ip_address('169.255.100.200').is_link_local is False

        assert ipaddress.ip_address('127.100.200.254').is_loopback is True
        assert ipaddress.ip_address('127.42.0.0').is_loopback is True
        assert ipaddress.ip_address('128.0.0.0').is_loopback is False
        assert ipaddress.ip_network('0.0.0.0').is_unspecified is True

    def testReservedIpv6(self):

        assert ipaddress.ip_network('ffff::').is_multicast is True
        assert ipaddress.ip_network(2**128 - 1).is_multicast is True
        assert ipaddress.ip_network('ff00::').is_multicast is True
        assert ipaddress.ip_network('fdff::').is_multicast is False

        assert ipaddress.ip_network('fecf::').is_site_local is True
        assert ipaddress.ip_network(
                'feff:ffff:ffff:ffff::').is_site_local is True
        assert ipaddress.ip_network(
                'fbf:ffff::').is_site_local is False
        assert ipaddress.ip_network('ff00::').is_site_local is False

        assert ipaddress.ip_network('fc00::').is_private is True
        assert ipaddress.ip_network(
                'fc00:ffff:ffff:ffff::').is_private is True
        assert ipaddress.ip_network('fbff:ffff::').is_private is False
        assert ipaddress.ip_network('fe00::').is_private is False

        assert ipaddress.ip_network('fea0::').is_link_local is True
        assert ipaddress.ip_network(
                'febf:ffff::').is_link_local is True
        assert ipaddress.ip_network(
                'fe7f:ffff::').is_link_local is False
        assert ipaddress.ip_network('fec0::').is_link_local is False

        assert ipaddress.ip_interface('0:0::0:01').is_loopback is True
        assert ipaddress.ip_interface('::1/127').is_loopback is False
        assert ipaddress.ip_network('::').is_loopback is False
        assert ipaddress.ip_network('::2').is_loopback is False

        assert ipaddress.ip_network('0::0').is_unspecified is True
        assert ipaddress.ip_network('::1').is_unspecified is False
        assert ipaddress.ip_network('::/127').is_unspecified is False

        assert ipaddress.ip_network('2001::1/128').is_private is True
        assert ipaddress.ip_network('200::1/128').is_global is True
        # test addresses
        assert ipaddress.ip_address('ffff::').is_multicast is True
        assert ipaddress.ip_address(2**128 - 1).is_multicast is True
        assert ipaddress.ip_address('ff00::').is_multicast is True
        assert ipaddress.ip_address('fdff::').is_multicast is False

        assert ipaddress.ip_address('fecf::').is_site_local is True
        assert ipaddress.ip_address(
                'feff:ffff:ffff:ffff::').is_site_local is True
        assert ipaddress.ip_address(
                'fbf:ffff::').is_site_local is False
        assert ipaddress.ip_address('ff00::').is_site_local is False

        assert ipaddress.ip_address('fc00::').is_private is True
        assert ipaddress.ip_address(
                'fc00:ffff:ffff:ffff::').is_private is True
        assert ipaddress.ip_address('fbff:ffff::').is_private is False
        assert ipaddress.ip_address('fe00::').is_private is False

        assert ipaddress.ip_address('fea0::').is_link_local is True
        assert ipaddress.ip_address(
                'febf:ffff::').is_link_local is True
        assert ipaddress.ip_address(
                'fe7f:ffff::').is_link_local is False
        assert ipaddress.ip_address('fec0::').is_link_local is False

        assert ipaddress.ip_address('0:0::0:01').is_loopback is True
        assert ipaddress.ip_address('::1').is_loopback is True
        assert ipaddress.ip_address('::2').is_loopback is False

        assert ipaddress.ip_address('0::0').is_unspecified is True
        assert ipaddress.ip_address('::1').is_unspecified is False

        # some generic IETF reserved addresses
        assert ipaddress.ip_address('100::').is_reserved is True
        assert ipaddress.ip_network('4000::1/128').is_reserved is True

    def testIpv4Mapped(self):
        assert ipaddress.ip_address('::ffff:192.168.1.1').ipv4_mapped == \
                ipaddress.ip_address('192.168.1.1')
        assert ipaddress.ip_address('::c0a8:101').ipv4_mapped is None
        assert ipaddress.ip_address('::ffff:c0a8:101').ipv4_mapped == \
                         ipaddress.ip_address('192.168.1.1')

    def testAddrExclude(self):
        addr1 = ipaddress.ip_network('10.1.1.0/24')
        addr2 = ipaddress.ip_network('10.1.1.0/26')
        addr3 = ipaddress.ip_network('10.2.1.0/24')
        addr4 = ipaddress.ip_address('10.1.1.0')
        addr5 = ipaddress.ip_network('2001:db8::0/32')
        assert sorted(list(addr1.address_exclude(addr2))) == \
                         [ipaddress.ip_network('10.1.1.64/26'),
                          ipaddress.ip_network('10.1.1.128/25')]
        with pytest.raises(ValueError):
            list(addr1.address_exclude(addr3))
        with pytest.raises(TypeError):
            list(addr1.address_exclude(addr4))
        with pytest.raises(TypeError):
            list(addr1.address_exclude(addr5))
        assert list(addr1.address_exclude(addr1)) == []

    def testHash(self):
        assert hash(ipaddress.ip_interface('10.1.1.0/24')) == \
                         hash(ipaddress.ip_interface('10.1.1.0/24'))
        assert hash(ipaddress.ip_network('10.1.1.0/24')) == \
                         hash(ipaddress.ip_network('10.1.1.0/24'))
        assert hash(ipaddress.ip_address('10.1.1.0')) == \
                         hash(ipaddress.ip_address('10.1.1.0'))
        # i70
        assert hash(ipaddress.ip_address('1.2.3.4')) == \
                         hash(ipaddress.ip_address(
                    int(ipaddress.ip_address('1.2.3.4')._ip)))
        ip1 = ipaddress.ip_address('10.1.1.0')
        ip2 = ipaddress.ip_address('1::')
        dummy = {}
        dummy[self.ipv4_address] = None
        dummy[self.ipv6_address] = None
        dummy[ip1] = None
        dummy[ip2] = None
        assert self.ipv4_address in dummy
        assert ip2 in dummy

    def testIPBases(self):
        net = self.ipv4_network
        assert '1.2.3.0/24' == net.compressed
        net = self.ipv6_network
        with pytest.raises(ValueError):
            net._string_from_ip_int(2**128 + 1)

    def testIPv6NetworkHelpers(self):
        net = self.ipv6_network
        assert '2001:658:22a:cafe::/64' == net.with_prefixlen
        assert '2001:658:22a:cafe::/ffff:ffff:ffff:ffff::' == \
                         net.with_netmask
        assert '2001:658:22a:cafe::/::ffff:ffff:ffff:ffff' == \
                         net.with_hostmask
        assert '2001:658:22a:cafe::/64' == str(net)

    def testIPv4NetworkHelpers(self):
        net = self.ipv4_network
        assert '1.2.3.0/24' == net.with_prefixlen
        assert '1.2.3.0/255.255.255.0' == net.with_netmask
        assert '1.2.3.0/0.0.0.255' == net.with_hostmask
        assert '1.2.3.0/24' == str(net)

    def testCopyConstructor(self):
        addr1 = ipaddress.ip_network('10.1.1.0/24')
        addr2 = ipaddress.ip_network(addr1)
        addr3 = ipaddress.ip_interface('2001:658:22a:cafe:200::1/64')
        addr4 = ipaddress.ip_interface(addr3)
        addr5 = ipaddress.IPv4Address('1.1.1.1')
        addr6 = ipaddress.IPv6Address('2001:658:22a:cafe:200::1')

        assert addr1 == addr2
        assert addr3 == addr4
        assert addr5 == ipaddress.IPv4Address(addr5)
        assert addr6 == ipaddress.IPv6Address(addr6)

    def testCompressIPv6Address(self):
        test_addresses = {
            '1:2:3:4:5:6:7:8': '1:2:3:4:5:6:7:8/128',
            '2001:0:0:4:0:0:0:8': '2001:0:0:4::8/128',
            '2001:0:0:4:5:6:7:8': '2001::4:5:6:7:8/128',
            '2001:0:3:4:5:6:7:8': '2001:0:3:4:5:6:7:8/128',
            '2001:0:3:4:5:6:7:8': '2001:0:3:4:5:6:7:8/128',
            '0:0:3:0:0:0:0:ffff': '0:0:3::ffff/128',
            '0:0:0:4:0:0:0:ffff': '::4:0:0:0:ffff/128',
            '0:0:0:0:5:0:0:ffff': '::5:0:0:ffff/128',
            '1:0:0:4:0:0:7:8': '1::4:0:0:7:8/128',
            '0:0:0:0:0:0:0:0': '::/128',
            '0:0:0:0:0:0:0:0/0': '::/0',
            '0:0:0:0:0:0:0:1': '::1/128',
            '2001:0658:022a:cafe:0000:0000:0000:0000/66':
            '2001:658:22a:cafe::/66',
            '::1.2.3.4': '::102:304/128',
            '1:2:3:4:5:ffff:1.2.3.4': '1:2:3:4:5:ffff:102:304/128',
            '::7:6:5:4:3:2:1': '0:7:6:5:4:3:2:1/128',
            '::7:6:5:4:3:2:0': '0:7:6:5:4:3:2:0/128',
            '7:6:5:4:3:2:1::': '7:6:5:4:3:2:1:0/128',
            '0:6:5:4:3:2:1::': '0:6:5:4:3:2:1:0/128',
            }
        for uncompressed, compressed in list(test_addresses.items()):
            assert compressed == str(ipaddress.IPv6Interface(
                uncompressed))

    def testExplodeShortHandIpStr(self):
        addr1 = ipaddress.IPv6Interface('2001::1')
        addr2 = ipaddress.IPv6Address('2001:0:5ef5:79fd:0:59d:a0e5:ba1')
        addr3 = ipaddress.IPv6Network('2001::/96')
        addr4 = ipaddress.IPv4Address('192.168.178.1')
        assert '2001:0000:0000:0000:0000:0000:0000:0001/128' == \
                         addr1.exploded
        assert '0000:0000:0000:0000:0000:0000:0000:0001/128' == \
                         ipaddress.IPv6Interface('::1/128').exploded
        # issue 77
        assert '2001:0000:5ef5:79fd:0000:059d:a0e5:0ba1' == \
                         addr2.exploded
        assert '2001:0000:0000:0000:0000:0000:0000:0000/96' == \
                         addr3.exploded
        assert '192.168.178.1' == addr4.exploded

    def testIntRepresentation(self):
        assert 16909060 == int(self.ipv4_address)
        assert 42540616829182469433547762482097946625 == \
                         int(self.ipv6_address)

    def testForceVersion(self):
        assert ipaddress.ip_network(1).version == 4
        assert ipaddress.IPv6Network(1).version == 6

    def testWithStar(self):
        assert self.ipv4_interface.with_prefixlen == "1.2.3.4/24"
        assert self.ipv4_interface.with_netmask == \
                         "1.2.3.4/255.255.255.0"
        assert self.ipv4_interface.with_hostmask == \
                         "1.2.3.4/0.0.0.255"

        assert self.ipv6_interface.with_prefixlen == \
                         '2001:658:22a:cafe:200::1/64'
        assert self.ipv6_interface.with_netmask == \
                         '2001:658:22a:cafe:200::1/ffff:ffff:ffff:ffff::'
        # this probably don't make much sense, but it's included for
        # compatibility with ipv4
        assert self.ipv6_interface.with_hostmask == \
                         '2001:658:22a:cafe:200::1/::ffff:ffff:ffff:ffff'

    def testNetworkElementCaching(self):
        # V4 - make sure we're empty
        assert 'network_address' not in self.ipv4_network._cache
        assert 'broadcast_address' not in self.ipv4_network._cache
        assert 'hostmask' not in self.ipv4_network._cache

        # V4 - populate and test
        assert self.ipv4_network.network_address == \
                         ipaddress.IPv4Address('1.2.3.0')
        assert self.ipv4_network.broadcast_address == \
                         ipaddress.IPv4Address('1.2.3.255')
        assert self.ipv4_network.hostmask == \
                         ipaddress.IPv4Address('0.0.0.255')

        # V4 - check we're cached
        assert 'broadcast_address' in self.ipv4_network._cache
        assert 'hostmask' in self.ipv4_network._cache

        # V6 - make sure we're empty
        assert 'broadcast_address' not in self.ipv6_network._cache
        assert 'hostmask' not in self.ipv6_network._cache

        # V6 - populate and test
        assert self.ipv6_network.network_address == \
                         ipaddress.IPv6Address('2001:658:22a:cafe::')
        assert self.ipv6_interface.network.network_address == \
                         ipaddress.IPv6Address('2001:658:22a:cafe::')

        assert self.ipv6_network.broadcast_address == \
            ipaddress.IPv6Address('2001:658:22a:cafe:ffff:ffff:ffff:ffff')
        assert self.ipv6_network.hostmask == \
                         ipaddress.IPv6Address('::ffff:ffff:ffff:ffff')
        assert self.ipv6_interface.network.broadcast_address == \
            ipaddress.IPv6Address('2001:658:22a:cafe:ffff:ffff:ffff:ffff')
        assert self.ipv6_interface.network.hostmask == \
                         ipaddress.IPv6Address('::ffff:ffff:ffff:ffff')

        # V6 - check we're cached
        assert 'broadcast_address' in self.ipv6_network._cache
        assert 'hostmask' in self.ipv6_network._cache
        assert 'broadcast_address' in self.ipv6_interface.network._cache
        assert 'hostmask' in self.ipv6_interface.network._cache

    def testTeredo(self):
        # stolen from wikipedia
        server = ipaddress.IPv4Address('65.54.227.120')
        client = ipaddress.IPv4Address('192.0.2.45')
        teredo_addr = '2001:0000:4136:e378:8000:63bf:3fff:fdd2'
        assert (server, client) == \
                         ipaddress.ip_address(teredo_addr).teredo
        bad_addr = '2000::4136:e378:8000:63bf:3fff:fdd2'
        assert not ipaddress.ip_address(bad_addr).teredo
        bad_addr = '2001:0001:4136:e378:8000:63bf:3fff:fdd2'
        assert not ipaddress.ip_address(bad_addr).teredo

        # i77
        teredo_addr = ipaddress.IPv6Address('2001:0:5ef5:79fd:0:59d:a0e5:ba1')
        assert (ipaddress.IPv4Address('94.245.121.253'),
                          ipaddress.IPv4Address('95.26.244.94')) == \
                         teredo_addr.teredo

    def testsixtofour(self):
        sixtofouraddr = ipaddress.ip_address('2002:ac1d:2d64::1')
        bad_addr = ipaddress.ip_address('2000:ac1d:2d64::1')
        assert ipaddress.IPv4Address('172.29.45.100') == \
                         sixtofouraddr.sixtofour
        assert not bad_addr.sixtofour
