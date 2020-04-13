# -*- coding: utf-8 -*-
"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""
# Import Python libs
from __future__ import absolute_import

# Import Salt Libs
import salt.states.makeconf as makeconf

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class MakeconfTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.states.makeconf
    """

    def setup_loader_modules(self):
        return {makeconf: {}}

    # 'present' function tests: 1

    def test_present(self):
        """
        Test to verify that the variable is in the ``make.conf``
        and has the provided settings.
        """
        name = "makeopts"

        ret = {"name": name, "result": True, "comment": "", "changes": {}}

        mock_t = MagicMock(return_value=True)
        with patch.dict(makeconf.__salt__, {"makeconf.get_var": mock_t}):
            comt = "Variable {0} is already present in make.conf".format(name)
            ret.update({"comment": comt})
            self.assertDictEqual(makeconf.present(name), ret)

    # 'absent' function tests: 1

    def test_absent(self):
        """
        Test to verify that the variable is not in the ``make.conf``.
        """
        name = "makeopts"

        ret = {"name": name, "result": True, "comment": "", "changes": {}}

        mock = MagicMock(return_value=None)
        with patch.dict(makeconf.__salt__, {"makeconf.get_var": mock}):
            comt = "Variable {0} is already absent from make.conf".format(name)
            ret.update({"comment": comt})
            self.assertDictEqual(makeconf.absent(name), ret)
