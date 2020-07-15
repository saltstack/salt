# -*- coding: utf-8 -*-
"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
import salt.states.process as process

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class ProcessTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.states.process
    """

    def setup_loader_modules(self):
        return {process: {}}

    # 'absent' function tests: 1

    def test_absent(self):
        """
        Test to ensures that the named command is not running.
        """
        name = "apache2"

        ret = {"name": name, "changes": {}, "result": None, "comment": ""}

        mock = MagicMock(return_value="")
        with patch.dict(process.__salt__, {"ps.pgrep": mock, "ps.pkill": mock}):
            with patch.dict(process.__opts__, {"test": True}):
                comt = "No matching processes running"
                ret.update({"comment": comt})
                self.assertDictEqual(process.absent(name), ret)

            with patch.dict(process.__opts__, {"test": False}):
                ret.update({"result": True})
                self.assertDictEqual(process.absent(name), ret)
