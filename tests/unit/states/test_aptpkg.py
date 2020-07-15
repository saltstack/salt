# -*- coding: utf-8 -*-
"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
import salt.states.aptpkg as aptpkg

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class AptTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.states.aptpkg
    """

    def setup_loader_modules(self):
        return {aptpkg: {}}

    # 'held' function tests: 1

    def test_held(self):
        """
        Test to set package in 'hold' state, meaning it will not be upgraded.
        """
        name = "tmux"

        ret = {
            "name": name,
            "result": False,
            "changes": {},
            "comment": "Package {0} does not have a state".format(name),
        }

        mock = MagicMock(return_value=False)
        with patch.dict(aptpkg.__salt__, {"pkg.get_selections": mock}):
            self.assertDictEqual(aptpkg.held(name), ret)
