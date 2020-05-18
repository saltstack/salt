# -*- coding: utf-8 -*-
"""
    tests.integration.shell.master_tops
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
"""

from __future__ import absolute_import, print_function, unicode_literals

import pytest
from tests.support.case import ShellCase
from tests.support.helpers import slowTest


@pytest.mark.windows_whitelisted
class MasterTopsTest(ShellCase):

    _call_binary_ = "salt"

    @slowTest
    def test_custom_tops_gets_utilized(self):
        resp = self.run_call("state.show_top")
        self.assertTrue(any("master_tops_test" in _x for _x in resp))
