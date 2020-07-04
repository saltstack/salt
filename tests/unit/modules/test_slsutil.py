# -*- coding: utf-8 -*-

from __future__ import absolute_import

import logging

import salt.modules.slsutil as slsutil
from tests.support.unit import TestCase

log = logging.getLogger(__name__)


class SlsUtilTestCase(TestCase):
    """
    Test cases for salt.modules.slsutil
    """

    def test_banner(self):
        """
        Test banner function
        """
        self.check_banner()
        self.check_banner(width=81)
        self.check_banner(width=20)
        self.check_banner(commentchar="//", borderchar="-")
        self.check_banner(title="title here", text="text here")
        self.check_banner(commentchar=" *")

    def check_banner(
        self,
        width=72,
        commentchar="#",
        borderchar="#",
        blockstart=None,
        blockend=None,
        title=None,
        text=None,
        newline=True,
    ):

        result = slsutil.banner(
            width=width,
            commentchar=commentchar,
            borderchar=borderchar,
            blockstart=blockstart,
            blockend=blockend,
            title=title,
            text=text,
            newline=newline,
        ).splitlines()
        for line in result:
            self.assertEqual(len(line), width)
            self.assertTrue(line.startswith(commentchar))
            self.assertTrue(line.endswith(commentchar.strip()))

    def test_boolstr(self):
        """
        Test boolstr function
        """
        self.assertEqual("yes", slsutil.boolstr(True, true="yes", false="no"))
        self.assertEqual("no", slsutil.boolstr(False, true="yes", false="no"))
