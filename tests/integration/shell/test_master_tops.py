# -*- coding: utf-8 -*-
"""
    tests.integration.shell.master_tops
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
"""

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing libs
from tests.support.case import ShellCase


class MasterTopsTest(ShellCase):

    _call_binary_ = "salt"

    def test_custom_tops_gets_utilized(self):
        resp = self.run_call("state.show_top")
        self.assertTrue(any("master_tops_test" in _x for _x in resp))
