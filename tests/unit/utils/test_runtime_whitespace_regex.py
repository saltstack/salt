# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`


    tests.unit.utils.runtime_whitespace_regex_test
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
'''

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import re

# Import Salt Testing libs
from tests.support.unit import TestCase

# Import salt libs
from salt.utils.stringutils import build_whitespace_split_regex

DOUBLE_TXT = '''\
# set variable identifying the chroot you work in (used in the prompt below)
if [ -z "$debian_chroot" ] && [ -r /etc/debian_chroot ]; then
    debian_chroot=$(cat /etc/debian_chroot)
fi
'''

SINGLE_TXT = '''\
# set variable identifying the chroot you work in (used in the prompt below)
if [ -z '$debian_chroot' ] && [ -r /etc/debian_chroot ]; then
    debian_chroot=$(cat /etc/debian_chroot)
fi
'''

SINGLE_DOUBLE_TXT = '''\
# set variable identifying the chroot you work in (used in the prompt below)
if [ -z '$debian_chroot' ] && [ -r /etc/debian_chroot ]; then
    debian_chroot=$(cat /etc/debian_chroot)
fi

# set variable identifying the chroot you work in (used in the prompt below)
if [ -z "$debian_chroot" ] && [ -r /etc/debian_chroot ]; then
    debian_chroot=$(cat /etc/debian_chroot)
fi
'''

SINGLE_DOUBLE_SAME_LINE_TXT = '''\
# set variable identifying the chroot you work in (used in the prompt below)
if [ -z '$debian_chroot' ] && [ -r "/etc/debian_chroot" ]; then
    debian_chroot=$(cat /etc/debian_chroot)
fi
'''

MATCH = '''\
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
'''


class TestRuntimeWhitespaceRegex(TestCase):

    def test_single_quotes(self):
        regex = build_whitespace_split_regex(SINGLE_TXT)
        self.assertTrue(re.search(regex, MATCH))

    def test_double_quotes(self):
        regex = build_whitespace_split_regex(DOUBLE_TXT)
        self.assertTrue(re.search(regex, MATCH))

    def test_single_and_double_quotes(self):
        regex = build_whitespace_split_regex(SINGLE_DOUBLE_TXT)
        self.assertTrue(re.search(regex, MATCH))

    def test_issue_2227(self):
        regex = build_whitespace_split_regex(SINGLE_DOUBLE_SAME_LINE_TXT)
        self.assertTrue(re.search(regex, MATCH))
