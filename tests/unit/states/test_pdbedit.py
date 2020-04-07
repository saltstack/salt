# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

import salt.modules.pdbedit as pdbedit_mod

# Import Salt Libs
import salt.states.pdbedit as pdbedit

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class PdbeditTestCase(TestCase, LoaderModuleMockMixin):
    """
    TestCase for salt.states.pdbedit module
    """

    def setup_loader_modules(self):
        return {pdbedit: {}, pdbedit_mod: {}}

    def test_generate_absent(self):
        """
        Test salt.states.pdbedit.absent when
        user is already absent
        """
        name = "testname"
        cmd_ret = {"pid": 13172, "retcode": 0, "stdout": "", "stderr": ""}
        with patch.dict(pdbedit.__salt__, {"pdbedit.list": pdbedit_mod.list_users}):
            with patch.dict(
                pdbedit_mod.__salt__, {"cmd.run_all": MagicMock(return_value=cmd_ret)}
            ):
                ret = pdbedit.absent(name)
        assert ret["comment"] == "account {0} is absent".format(name)
