# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals

import re
import sys
import textwrap

import salt.utils.stringutils

# Import 3rd-party libs
from salt.ext import six
from salt.ext.six.moves import builtins, range  # pylint: disable=redefined-builtin

# Import Salt libs
from tests.support.mock import patch
from tests.support.unit import LOREM_IPSUM, TestCase

UNICODE = "中国語 (繁体)"
STR = BYTES = UNICODE.encode("utf-8")
# This is an example of a unicode string with й constructed using two separate
# code points. Do not modify it.
EGGS = "\u044f\u0438\u0306\u0446\u0430"

LATIN1_UNICODE = "räksmörgås"
LATIN1_BYTES = LATIN1_UNICODE.encode("latin-1")

DOUBLE_TXT = """\
# set variable identifying the chroot you work in (used in the prompt below)
if [ -z "$debian_chroot" ] && [ -r /etc/debian_chroot ]; then
    debian_chroot=$(cat /etc/debian_chroot)
fi
"""

SINGLE_TXT = """\
# set variable identifying the chroot you work in (used in the prompt below)
if [ -z '$debian_chroot' ] && [ -r /etc/debian_chroot ]; then
    debian_chroot=$(cat /etc/debian_chroot)
fi
"""

SINGLE_DOUBLE_TXT = """\
# set variable identifying the chroot you work in (used in the prompt below)
if [ -z '$debian_chroot' ] && [ -r /etc/debian_chroot ]; then
    debian_chroot=$(cat /etc/debian_chroot)
fi

# set variable identifying the chroot you work in (used in the prompt below)
if [ -z "$debian_chroot" ] && [ -r /etc/debian_chroot ]; then
    debian_chroot=$(cat /etc/debian_chroot)
fi
"""

SINGLE_DOUBLE_SAME_LINE_TXT = """\
# set variable identifying the chroot you work in (used in the prompt below)
if [ -z '$debian_chroot' ] && [ -r "/etc/debian_chroot" ]; then
    debian_chroot=$(cat /etc/debian_chroot)
fi
"""

MATCH = """\
# set variable identifying the chroot you work in (used in the prompt below)
if [ -z '$debian_chroot' ] && [ -r /etc/debian_chroot ]; then
    debian_chroot=$(cat /etc/debian_chroot)
fi


# set variable identifying the chroot you work in (used in the prompt below)
if [ -z "$debian_chroot" ] && [ -r /etc/debian_chroot ]; then
    debian_chroot=$(cat /etc/debian_chroot)
fi


# set variable identifying the chroot you work in (used in the prompt below)
if [ -z "$debian_chroot" ] && [ -r /etc/debian_chroot ]; then
    debian_chroot=$(cat /etc/debian_chroot)
fi


# set variable identifying the chroot you work in (used in the prompt below)
if [ -z '$debian_chroot' ] && [ -r /etc/debian_chroot ]; then
    debian_chroot=$(cat /etc/debian_chroot)
fi


# set variable identifying the chroot you work in (used in the prompt below)
if [ -z '$debian_chroot' ] && [ -r "/etc/debian_chroot" ]; then
    debian_chroot=$(cat /etc/debian_chroot)
fi
"""


class TestBuildWhitespaceRegex(TestCase):
    def test_single_quotes(self):
        regex = salt.utils.stringutils.build_whitespace_split_regex(SINGLE_TXT)
        self.assertTrue(re.search(regex, MATCH))

    def test_double_quotes(self):
        regex = salt.utils.stringutils.build_whitespace_split_regex(DOUBLE_TXT)
        self.assertTrue(re.search(regex, MATCH))

    def test_single_and_double_quotes(self):
        regex = salt.utils.stringutils.build_whitespace_split_regex(SINGLE_DOUBLE_TXT)
        self.assertTrue(re.search(regex, MATCH))

    def test_issue_2227(self):
        regex = salt.utils.stringutils.build_whitespace_split_regex(
            SINGLE_DOUBLE_SAME_LINE_TXT
        )
        self.assertTrue(re.search(regex, MATCH))


class StringutilsTestCase(TestCase):
    def test_contains_whitespace(self):
        does_contain_whitespace = "A brown fox jumped over the red hen."
        does_not_contain_whitespace = "Abrownfoxjumpedovertheredhen."

        self.assertTrue(
            salt.utils.stringutils.contains_whitespace(does_contain_whitespace)
        )
        self.assertFalse(
            salt.utils.stringutils.contains_whitespace(does_not_contain_whitespace)
        )

    def test_to_num(self):
        self.assertEqual(7, salt.utils.stringutils.to_num("7"))
        self.assertIsInstance(salt.utils.stringutils.to_num("7"), int)
        self.assertEqual(7, salt.utils.stringutils.to_num("7.0"))
        self.assertIsInstance(salt.utils.stringutils.to_num("7.0"), float)
        self.assertEqual(salt.utils.stringutils.to_num("Seven"), "Seven")
        self.assertIsInstance(salt.utils.stringutils.to_num("Seven"), six.text_type)

    def test_to_none(self):
        self.assertIsNone(salt.utils.stringutils.to_none(""))
        self.assertIsNone(salt.utils.stringutils.to_none("  "))
        # Ensure that we do not inadvertently convert certain strings or 0 to None
        self.assertIsNotNone(salt.utils.stringutils.to_none("None"))
        self.assertIsNotNone(salt.utils.stringutils.to_none(0))

    def test_is_binary(self):
        self.assertFalse(salt.utils.stringutils.is_binary(LOREM_IPSUM))
        # Also test bytestring
        self.assertFalse(
            salt.utils.stringutils.is_binary(
                salt.utils.stringutils.is_binary(LOREM_IPSUM)
            )
        )

        zero_str = "{0}{1}".format(LOREM_IPSUM, "\0")
        self.assertTrue(salt.utils.stringutils.is_binary(zero_str))
        # Also test bytestring
        self.assertTrue(
            salt.utils.stringutils.is_binary(salt.utils.stringutils.to_bytes(zero_str))
        )

        # To to ensure safe exit if str passed doesn't evaluate to True
        self.assertFalse(salt.utils.stringutils.is_binary(""))
        self.assertFalse(salt.utils.stringutils.is_binary(b""))

        nontext = 3 * (
            "".join([chr(x) for x in range(1, 32) if x not in (8, 9, 10, 12, 13)])
        )
        almost_bin_str = "{0}{1}".format(LOREM_IPSUM[:100], nontext[:42])
        self.assertFalse(salt.utils.stringutils.is_binary(almost_bin_str))
        # Also test bytestring
        self.assertFalse(
            salt.utils.stringutils.is_binary(
                salt.utils.stringutils.to_bytes(almost_bin_str)
            )
        )

        bin_str = almost_bin_str + "\x01"
        self.assertTrue(salt.utils.stringutils.is_binary(bin_str))
        # Also test bytestring
        self.assertTrue(
            salt.utils.stringutils.is_binary(salt.utils.stringutils.to_bytes(bin_str))
        )

    def test_to_str(self):
        for x in (123, (1, 2, 3), [1, 2, 3], {1: 23}, None):
            self.assertRaises(TypeError, salt.utils.stringutils.to_str, x)
        if six.PY3:
            self.assertEqual(salt.utils.stringutils.to_str("plugh"), "plugh")
            self.assertEqual(salt.utils.stringutils.to_str("áéíóúý", "utf-8"), "áéíóúý")
            self.assertEqual(salt.utils.stringutils.to_str(BYTES, "utf-8"), UNICODE)
            self.assertEqual(
                salt.utils.stringutils.to_str(bytearray(BYTES), "utf-8"), UNICODE
            )
            # Test situation when a minion returns incorrect utf-8 string because of... million reasons
            ut2 = b"\x9c"
            self.assertRaises(
                UnicodeDecodeError, salt.utils.stringutils.to_str, ut2, "utf-8"
            )
            self.assertEqual(
                salt.utils.stringutils.to_str(ut2, "utf-8", "replace"), "\ufffd"
            )
            self.assertRaises(
                UnicodeDecodeError,
                salt.utils.stringutils.to_str,
                bytearray(ut2),
                "utf-8",
            )
            self.assertEqual(
                salt.utils.stringutils.to_str(bytearray(ut2), "utf-8", "replace"),
                "\ufffd",
            )
        else:
            self.assertEqual(
                salt.utils.stringutils.to_str("plugh"), str("plugh")
            )  # future lint: disable=blacklisted-function
            self.assertEqual(
                salt.utils.stringutils.to_str("áéíóúý", "utf-8"),
                "áéíóúý".encode("utf-8"),
            )
            self.assertEqual(salt.utils.stringutils.to_str(UNICODE, "utf-8"), STR)
            self.assertEqual(
                salt.utils.stringutils.to_str(bytearray(STR), "utf-8"), STR
            )

            # Test utf-8 fallback with Windows default codepage
            with patch.object(builtins, "__salt_system_encoding__", "CP1252"):
                self.assertEqual(
                    salt.utils.stringutils.to_str("Ψ"), "Ψ".encode("utf-8")
                )

    def test_to_bytes(self):
        for x in (123, (1, 2, 3), [1, 2, 3], {1: 23}, None):
            self.assertRaises(TypeError, salt.utils.stringutils.to_bytes, x)
        if six.PY3:
            self.assertEqual(salt.utils.stringutils.to_bytes("xyzzy"), b"xyzzy")
            self.assertEqual(salt.utils.stringutils.to_bytes(BYTES), BYTES)
            self.assertEqual(salt.utils.stringutils.to_bytes(bytearray(BYTES)), BYTES)
            self.assertEqual(salt.utils.stringutils.to_bytes(UNICODE, "utf-8"), BYTES)

            # Test utf-8 fallback with ascii default encoding
            with patch.object(builtins, "__salt_system_encoding__", "ascii"):
                self.assertEqual(salt.utils.stringutils.to_bytes("Ψ"), b"\xce\xa8")
        else:
            self.assertEqual(salt.utils.stringutils.to_bytes("xyzzy"), "xyzzy")
            self.assertEqual(salt.utils.stringutils.to_bytes(BYTES), BYTES)
            self.assertEqual(salt.utils.stringutils.to_bytes(bytearray(BYTES)), BYTES)
            self.assertEqual(salt.utils.stringutils.to_bytes(UNICODE, "utf-8"), BYTES)

    def test_to_unicode(self):
        self.assertEqual(
            salt.utils.stringutils.to_unicode(EGGS, normalize=True), "яйца"
        )
        self.assertNotEqual(
            salt.utils.stringutils.to_unicode(EGGS, normalize=False), "яйца"
        )

        self.assertEqual(
            salt.utils.stringutils.to_unicode(LATIN1_BYTES, encoding="latin-1"),
            LATIN1_UNICODE,
        )

        if six.PY3:
            self.assertEqual(salt.utils.stringutils.to_unicode("plugh"), "plugh")
            self.assertEqual(salt.utils.stringutils.to_unicode("áéíóúý"), "áéíóúý")
            self.assertEqual(salt.utils.stringutils.to_unicode(BYTES, "utf-8"), UNICODE)
            self.assertEqual(
                salt.utils.stringutils.to_unicode(bytearray(BYTES), "utf-8"), UNICODE
            )
        else:
            self.assertEqual(
                salt.utils.stringutils.to_unicode(str("xyzzy"), "utf-8"), "xyzzy"
            )  # future lint: disable=blacklisted-function
            self.assertEqual(salt.utils.stringutils.to_unicode(BYTES, "utf-8"), UNICODE)

            # Test that unicode chars are decoded properly even when using
            # locales which are not UTF-8 compatible
            with patch.object(builtins, "__salt_system_encoding__", "ascii"):
                self.assertEqual(
                    salt.utils.stringutils.to_unicode("Ψ".encode("utf-8")), "Ψ"
                )
            with patch.object(builtins, "__salt_system_encoding__", "CP1252"):
                self.assertEqual(
                    salt.utils.stringutils.to_unicode("Ψ".encode("utf-8")), "Ψ"
                )

    def test_to_unicode_multi_encoding(self):
        result = salt.utils.stringutils.to_unicode(
            LATIN1_BYTES, encoding=("utf-8", "latin1")
        )
        assert result == LATIN1_UNICODE

    def test_build_whitespace_split_regex(self):
        # With 3.7+,  re.escape only escapes special characters, no longer
        # escaping all characters other than ASCII letters, numbers and
        # underscores.  This includes commas.
        if sys.version_info >= (3, 7):
            expected_regex = (
                "(?m)^(?:[\\s]+)?Lorem(?:[\\s]+)?ipsum(?:[\\s]+)?dolor(?:[\\s]+)?sit(?:[\\s]+)?amet,"
                "(?:[\\s]+)?$"
            )
        else:
            expected_regex = (
                "(?m)^(?:[\\s]+)?Lorem(?:[\\s]+)?ipsum(?:[\\s]+)?dolor(?:[\\s]+)?sit(?:[\\s]+)?amet\\,"
                "(?:[\\s]+)?$"
            )
        ret = salt.utils.stringutils.build_whitespace_split_regex(
            " ".join(LOREM_IPSUM.split()[:5])
        )
        self.assertEqual(ret, expected_regex)

    def test_get_context(self):
        expected_context = textwrap.dedent(
            """\
            ---
            Lorem ipsum dolor sit amet, consectetur adipiscing elit. Quisque eget urna a arcu lacinia sagittis.
            Sed scelerisque, lacus eget malesuada vestibulum, justo diam facilisis tortor, in sodales dolor
            [...]
            ---"""
        )
        ret = salt.utils.stringutils.get_context(LOREM_IPSUM, 1, num_lines=1)
        self.assertEqual(ret, expected_context)

    def test_get_context_has_enough_context(self):
        template = "1\n2\n3\n4\n5\n6\n7\n8\n9\na\nb\nc\nd\ne\nf"
        context = salt.utils.stringutils.get_context(template, 8)
        expected = "---\n[...]\n3\n4\n5\n6\n7\n8\n9\na\nb\nc\nd\n[...]\n---"
        self.assertEqual(expected, context)

    def test_get_context_at_top_of_file(self):
        template = "1\n2\n3\n4\n5\n6\n7\n8\n9\na\nb\nc\nd\ne\nf"
        context = salt.utils.stringutils.get_context(template, 1)
        expected = "---\n1\n2\n3\n4\n5\n6\n[...]\n---"
        self.assertEqual(expected, context)

    def test_get_context_at_bottom_of_file(self):
        template = "1\n2\n3\n4\n5\n6\n7\n8\n9\na\nb\nc\nd\ne\nf"
        context = salt.utils.stringutils.get_context(template, 15)
        expected = "---\n[...]\na\nb\nc\nd\ne\nf\n---"
        self.assertEqual(expected, context)

    def test_get_context_2_context_lines(self):
        template = "1\n2\n3\n4\n5\n6\n7\n8\n9\na\nb\nc\nd\ne\nf"
        context = salt.utils.stringutils.get_context(template, 8, num_lines=2)
        expected = "---\n[...]\n6\n7\n8\n9\na\n[...]\n---"
        self.assertEqual(expected, context)

    def test_get_context_with_marker(self):
        template = "1\n2\n3\n4\n5\n6\n7\n8\n9\na\nb\nc\nd\ne\nf"
        context = salt.utils.stringutils.get_context(
            template, 8, num_lines=2, marker=" <---"
        )
        expected = "---\n[...]\n6\n7\n8 <---\n9\na\n[...]\n---"
        self.assertEqual(expected, context)

    def test_expr_match(self):
        val = "foo/bar/baz"
        # Exact match
        self.assertTrue(salt.utils.stringutils.expr_match(val, val))
        # Glob match
        self.assertTrue(salt.utils.stringutils.expr_match(val, "foo/*/baz"))
        # Glob non-match
        self.assertFalse(salt.utils.stringutils.expr_match(val, "foo/*/bar"))
        # Regex match
        self.assertTrue(salt.utils.stringutils.expr_match(val, r"foo/\w+/baz"))
        # Regex non-match
        self.assertFalse(salt.utils.stringutils.expr_match(val, r"foo/\w/baz"))

    def test_check_whitelist_blacklist(self):
        """
        Ensure that whitelist matching works on both PY2 and PY3
        """
        whitelist = ["one/two/three", r"web[0-9]"]
        blacklist = ["four/five/six", r"web[5-9]"]

        # Tests with string whitelist/blacklist
        self.assertFalse(
            salt.utils.stringutils.check_whitelist_blacklist(
                "web_one", whitelist=whitelist[1], blacklist=None,
            )
        )
        self.assertFalse(
            salt.utils.stringutils.check_whitelist_blacklist(
                "web_one", whitelist=whitelist[1], blacklist=[],
            )
        )
        self.assertTrue(
            salt.utils.stringutils.check_whitelist_blacklist(
                "web1", whitelist=whitelist[1], blacklist=None,
            )
        )
        self.assertTrue(
            salt.utils.stringutils.check_whitelist_blacklist(
                "web1", whitelist=whitelist[1], blacklist=[],
            )
        )
        self.assertFalse(
            salt.utils.stringutils.check_whitelist_blacklist(
                "web5", whitelist=None, blacklist=blacklist[1],
            )
        )
        self.assertFalse(
            salt.utils.stringutils.check_whitelist_blacklist(
                "web5", whitelist=[], blacklist=blacklist[1],
            )
        )
        self.assertTrue(
            salt.utils.stringutils.check_whitelist_blacklist(
                "web_five", whitelist=None, blacklist=blacklist[1],
            )
        )
        self.assertTrue(
            salt.utils.stringutils.check_whitelist_blacklist(
                "web_five", whitelist=[], blacklist=blacklist[1],
            )
        )
        self.assertFalse(
            salt.utils.stringutils.check_whitelist_blacklist(
                "web5", whitelist=whitelist[1], blacklist=blacklist[1],
            )
        )
        self.assertTrue(
            salt.utils.stringutils.check_whitelist_blacklist(
                "web4", whitelist=whitelist[1], blacklist=blacklist[1],
            )
        )

        # Tests with list whitelist/blacklist
        self.assertFalse(
            salt.utils.stringutils.check_whitelist_blacklist(
                "web_one", whitelist=whitelist, blacklist=None,
            )
        )
        self.assertFalse(
            salt.utils.stringutils.check_whitelist_blacklist(
                "web_one", whitelist=whitelist, blacklist=[],
            )
        )
        self.assertTrue(
            salt.utils.stringutils.check_whitelist_blacklist(
                "web1", whitelist=whitelist, blacklist=None,
            )
        )
        self.assertTrue(
            salt.utils.stringutils.check_whitelist_blacklist(
                "web1", whitelist=whitelist, blacklist=[],
            )
        )
        self.assertFalse(
            salt.utils.stringutils.check_whitelist_blacklist(
                "web5", whitelist=None, blacklist=blacklist,
            )
        )
        self.assertFalse(
            salt.utils.stringutils.check_whitelist_blacklist(
                "web5", whitelist=[], blacklist=blacklist,
            )
        )
        self.assertTrue(
            salt.utils.stringutils.check_whitelist_blacklist(
                "web_five", whitelist=None, blacklist=blacklist,
            )
        )
        self.assertTrue(
            salt.utils.stringutils.check_whitelist_blacklist(
                "web_five", whitelist=[], blacklist=blacklist,
            )
        )
        self.assertFalse(
            salt.utils.stringutils.check_whitelist_blacklist(
                "web5", whitelist=whitelist, blacklist=blacklist,
            )
        )
        self.assertTrue(
            salt.utils.stringutils.check_whitelist_blacklist(
                "web4", whitelist=whitelist, blacklist=blacklist,
            )
        )

        # Tests with set whitelist/blacklist
        self.assertFalse(
            salt.utils.stringutils.check_whitelist_blacklist(
                "web_one", whitelist=set(whitelist), blacklist=None,
            )
        )
        self.assertFalse(
            salt.utils.stringutils.check_whitelist_blacklist(
                "web_one", whitelist=set(whitelist), blacklist=set(),
            )
        )
        self.assertTrue(
            salt.utils.stringutils.check_whitelist_blacklist(
                "web1", whitelist=set(whitelist), blacklist=None,
            )
        )
        self.assertTrue(
            salt.utils.stringutils.check_whitelist_blacklist(
                "web1", whitelist=set(whitelist), blacklist=set(),
            )
        )
        self.assertFalse(
            salt.utils.stringutils.check_whitelist_blacklist(
                "web5", whitelist=None, blacklist=set(blacklist),
            )
        )
        self.assertFalse(
            salt.utils.stringutils.check_whitelist_blacklist(
                "web5", whitelist=set(), blacklist=set(blacklist),
            )
        )
        self.assertTrue(
            salt.utils.stringutils.check_whitelist_blacklist(
                "web_five", whitelist=None, blacklist=set(blacklist),
            )
        )
        self.assertTrue(
            salt.utils.stringutils.check_whitelist_blacklist(
                "web_five", whitelist=set(), blacklist=set(blacklist),
            )
        )
        self.assertFalse(
            salt.utils.stringutils.check_whitelist_blacklist(
                "web5", whitelist=set(whitelist), blacklist=set(blacklist),
            )
        )
        self.assertTrue(
            salt.utils.stringutils.check_whitelist_blacklist(
                "web4", whitelist=set(whitelist), blacklist=set(blacklist),
            )
        )

        # Test with invalid type for whitelist/blacklist
        self.assertRaises(
            TypeError,
            salt.utils.stringutils.check_whitelist_blacklist,
            "foo",
            whitelist=123,
        )
        self.assertRaises(
            TypeError,
            salt.utils.stringutils.check_whitelist_blacklist,
            "foo",
            blacklist=123,
        )
