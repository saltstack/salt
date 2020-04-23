# -*- coding: utf-8 -*-
"""
    tests.integration.shell.master_tops
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
"""

from __future__ import absolute_import, print_function, unicode_literals

import pytest
from tests.support.case import ShellCase
from tests.support.unit import skipIf


@pytest.mark.windows_whitelisted
class MasterTopsTest(ShellCase):

    _call_binary_ = "salt"

    @skipIf(True, "SLOWTEST skip")
    def test_custom_tops_gets_utilized(self):
        resp = self.run_call("state.show_top")
        self.assertTrue(any("master_tops_test" in _x for _x in resp))
