# -*- coding: utf-8 -*-

from __future__ import absolute_import

# Import Salt libs
from tests.support.unit import TestCase, LOREM_IPSUM
import salt.utils.stringutils

# Import 3rd-party libs
from salt.ext import six
from salt.ext.six.moves import range  # pylint: disable=redefined-builtin


class StringutilsTestCase(TestCase):
    def test_contains_whitespace(self):
        does_contain_whitespace = 'A brown fox jumped over the red hen.'
        does_not_contain_whitespace = 'Abrownfoxjumpedovertheredhen.'

        self.assertTrue(salt.utils.stringutils.contains_whitespace(does_contain_whitespace))
        self.assertFalse(salt.utils.stringutils.contains_whitespace(does_not_contain_whitespace))

    def test_to_num(self):
        self.assertEqual(7, salt.utils.stringutils.to_num('7'))
        self.assertIsInstance(salt.utils.stringutils.to_num('7'), int)
        self.assertEqual(7, salt.utils.stringutils.to_num('7.0'))
        self.assertIsInstance(salt.utils.stringutils.to_num('7.0'), float)
        self.assertEqual(salt.utils.stringutils.to_num('Seven'), 'Seven')
        self.assertIsInstance(salt.utils.stringutils.to_num('Seven'), str)

    def test_is_binary(self):
        self.assertFalse(salt.utils.stringutils.is_binary(LOREM_IPSUM))

        zero_str = '{0}{1}'.format(LOREM_IPSUM, '\0')
        self.assertTrue(salt.utils.stringutils.is_binary(zero_str))

        # To to ensure safe exit if str passed doesn't evaluate to True
        self.assertFalse(salt.utils.stringutils.is_binary(''))

        nontext = 3 * (''.join([chr(x) for x in range(1, 32) if x not in (8, 9, 10, 12, 13)]))
        almost_bin_str = '{0}{1}'.format(LOREM_IPSUM[:100], nontext[:42])
        self.assertFalse(salt.utils.stringutils.is_binary(almost_bin_str))

        bin_str = almost_bin_str + '\x01'
        self.assertTrue(salt.utils.stringutils.is_binary(bin_str))

    def test_to_str(self):
        for x in (123, (1, 2, 3), [1, 2, 3], {1: 23}, None):
            self.assertRaises(TypeError, salt.utils.stringutils.to_str, x)
        if six.PY3:
            self.assertEqual(salt.utils.stringutils.to_str('plugh'), 'plugh')
            self.assertEqual(salt.utils.stringutils.to_str('áéíóúý', 'utf-8'), 'áéíóúý')
            un = '\u4e2d\u56fd\u8a9e (\u7e41\u4f53)'  # pylint: disable=anomalous-unicode-escape-in-string
            ut = bytes((0xe4, 0xb8, 0xad, 0xe5, 0x9b, 0xbd, 0xe8, 0xaa, 0x9e, 0x20, 0x28, 0xe7, 0xb9, 0x81, 0xe4, 0xbd, 0x93, 0x29))
            self.assertEqual(salt.utils.stringutils.to_str(ut, 'utf-8'), un)
            self.assertEqual(salt.utils.stringutils.to_str(bytearray(ut), 'utf-8'), un)
            # Test situation when a minion returns incorrect utf-8 string because of... million reasons
            ut2 = b'\x9c'
            self.assertEqual(salt.utils.stringutils.to_str(ut2, 'utf-8'), u'\ufffd')
            self.assertEqual(salt.utils.stringutils.to_str(bytearray(ut2), 'utf-8'), u'\ufffd')
        else:
            self.assertEqual(salt.utils.stringutils.to_str('plugh'), 'plugh')
            self.assertEqual(salt.utils.stringutils.to_str(u'áéíóúý', 'utf-8'), 'áéíóúý')
            un = u'\u4e2d\u56fd\u8a9e (\u7e41\u4f53)'
            ut = '\xe4\xb8\xad\xe5\x9b\xbd\xe8\xaa\x9e (\xe7\xb9\x81\xe4\xbd\x93)'
            self.assertEqual(salt.utils.stringutils.to_str(un, 'utf-8'), ut)
            self.assertEqual(salt.utils.stringutils.to_str(bytearray(ut), 'utf-8'), ut)

    def test_to_bytes(self):
        for x in (123, (1, 2, 3), [1, 2, 3], {1: 23}, None):
            self.assertRaises(TypeError, salt.utils.stringutils.to_bytes, x)
        if six.PY3:
            self.assertEqual(salt.utils.stringutils.to_bytes('xyzzy'), b'xyzzy')
            ut = bytes((0xe4, 0xb8, 0xad, 0xe5, 0x9b, 0xbd, 0xe8, 0xaa, 0x9e, 0x20, 0x28, 0xe7, 0xb9, 0x81, 0xe4, 0xbd, 0x93, 0x29))
            un = '\u4e2d\u56fd\u8a9e (\u7e41\u4f53)'  # pylint: disable=anomalous-unicode-escape-in-string
            self.assertEqual(salt.utils.stringutils.to_bytes(ut), ut)
            self.assertEqual(salt.utils.stringutils.to_bytes(bytearray(ut)), ut)
            self.assertEqual(salt.utils.stringutils.to_bytes(un, 'utf-8'), ut)
        else:
            self.assertEqual(salt.utils.stringutils.to_bytes('xyzzy'), 'xyzzy')
            ut = ''.join([chr(x) for x in (0xe4, 0xb8, 0xad, 0xe5, 0x9b, 0xbd, 0xe8, 0xaa, 0x9e, 0x20, 0x28, 0xe7, 0xb9, 0x81, 0xe4, 0xbd, 0x93, 0x29)])
            un = u'\u4e2d\u56fd\u8a9e (\u7e41\u4f53)'  # pylint: disable=anomalous-unicode-escape-in-string
            self.assertEqual(salt.utils.stringutils.to_bytes(ut), ut)
            self.assertEqual(salt.utils.stringutils.to_bytes(bytearray(ut)), ut)
            self.assertEqual(salt.utils.stringutils.to_bytes(un, 'utf-8'), ut)

    def test_to_unicode(self):
        if six.PY3:
            self.assertEqual(salt.utils.stringutils.to_unicode('plugh'), 'plugh')
            self.assertEqual(salt.utils.stringutils.to_unicode('áéíóúý'), 'áéíóúý')
            un = '\u4e2d\u56fd\u8a9e (\u7e41\u4f53)'  # pylint: disable=anomalous-unicode-escape-in-string
            ut = bytes((0xe4, 0xb8, 0xad, 0xe5, 0x9b, 0xbd, 0xe8, 0xaa, 0x9e, 0x20, 0x28, 0xe7, 0xb9, 0x81, 0xe4, 0xbd, 0x93, 0x29))
            self.assertEqual(salt.utils.stringutils.to_unicode(ut, 'utf-8'), un)
            self.assertEqual(salt.utils.stringutils.to_unicode(bytearray(ut), 'utf-8'), un)
        else:
            self.assertEqual(salt.utils.stringutils.to_unicode('xyzzy', 'utf-8'), u'xyzzy')
            ut = '\xe4\xb8\xad\xe5\x9b\xbd\xe8\xaa\x9e (\xe7\xb9\x81\xe4\xbd\x93)'
            un = u'\u4e2d\u56fd\u8a9e (\u7e41\u4f53)'
            self.assertEqual(salt.utils.stringutils.to_unicode(ut, 'utf-8'), un)

    def test_build_whitespace_split_regex(self):
        expected_regex = '(?m)^(?:[\\s]+)?Lorem(?:[\\s]+)?ipsum(?:[\\s]+)?dolor(?:[\\s]+)?sit(?:[\\s]+)?amet\\,' \
                         '(?:[\\s]+)?$'
        ret = salt.utils.stringutils.build_whitespace_split_regex(' '.join(LOREM_IPSUM.split()[:5]))
        self.assertEqual(ret, expected_regex)
