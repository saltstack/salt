# -*- coding: utf-8 -*-
"""
    tests.unit.utils.runtime_whitespace_regex
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    :copyright: © 2012 UfSoft.org - :email:`Pedro Algarvio (pedro@algarvio.me)`
    :license: Apache 2.0, see LICENSE for more details.
"""

import re
from saltunittest import TestCase, TestLoader, TextTestRunner

from salt.utils import build_whitepace_splited_regex

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


class TestRuntimeWhitespaceRegex(TestCase):

    def test_single_quotes(self):
        regex = build_whitepace_splited_regex(SINGLE_TXT)
        self.assertTrue(re.search(regex, MATCH))

    def test_double_quotes(self):
        regex = build_whitepace_splited_regex(DOUBLE_TXT)
        self.assertTrue(re.search(regex, MATCH))

    def test_single_and_double_quotes(self):
        regex = build_whitepace_splited_regex(SINGLE_DOUBLE_TXT)
        self.assertTrue(re.search(regex, MATCH))

    def test_issue_2227(self):
        regex = build_whitepace_splited_regex(SINGLE_DOUBLE_SAME_LINE_TXT)
        self.assertTrue(re.search(regex, MATCH))


if __name__ == "__main__":
    loader = TestLoader()
    tests = loader.loadTestsFromTestCase(TestRuntimeWhitespaceRegex)
    TextTestRunner(verbosity=1).run(tests)
