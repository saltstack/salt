# -*- coding: utf-8 -*-
"""
Unit tests for salt._compat
"""

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

import logging
import sys

# Import Salt libs
import salt._compat as compat

# Import 3rd Party libs
from salt.ext.six import binary_type, text_type

# Import Salt Testing libs
from tests.support.unit import TestCase

log = logging.getLogger(__name__)
PY3 = sys.version_info.major == 3


class CompatTestCase(TestCase):
    def test_text(self):
        ret = compat.text_("test string")
        self.assertTrue(isinstance(ret, text_type))

    def test_text_binary(self):
        ret = compat.text_(b"test string")
        self.assertTrue(isinstance(ret, text_type))

    def test_bytes(self):
        ret = compat.bytes_("test string")
        self.assertTrue(isinstance(ret, binary_type))

    def test_bytes_binary(self):
        ret = compat.bytes_(b"test string")
        self.assertTrue(isinstance(ret, binary_type))

    def test_ascii_native(self):
        ret = compat.ascii_native_("test string")
        self.assertTrue(isinstance(ret, str))

    def test_ascii_native_binary(self):
        ret = compat.ascii_native_(b"test string")
        self.assertTrue(isinstance(ret, str))

    def test_native(self):
        ret = compat.native_("test string")
        self.assertTrue(isinstance(ret, str))

    def test_native_binary(self):
        ret = compat.native_(b"test string")
        self.assertTrue(isinstance(ret, str))

    def test_string_io(self):
        ret = compat.string_io("test string")
        if PY3:
            expected = "io.StringIO object"
        else:
            expected = "cStringIO.StringI object"
        self.assertTrue(expected in repr(ret))

    def test_string_io_unicode(self):
        ret = compat.string_io("test string \xf8")
        if PY3:
            expected = "io.StringIO object"
        else:
            expected = "StringIO.StringIO instance"
        self.assertTrue(expected in repr(ret))

    def test_ipv6_class__is_packed_binary(self):
        ipv6 = compat.IPv6AddressScoped("2001:db8::")
        self.assertEqual(str(ipv6), "2001:db8::")

    def test_ipv6_class__is_packed_binary_integer(self):
        ipv6 = compat.IPv6AddressScoped(42540766411282592856903984951653826560)
        self.assertEqual(str(ipv6), "2001:db8::")

    def test_ipv6_class__is_packed_binary__issue_51831(self):
        ipv6 = compat.IPv6AddressScoped(b"sixteen.digit.bn")
        self.assertEqual(str(ipv6), "7369:7874:6565:6e2e:6469:6769:742e:626e")
