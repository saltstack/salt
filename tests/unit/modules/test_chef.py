"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import salt.modules.chef as chef
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.runtests import RUNTIME_VARS
from tests.support.unit import TestCase


class ChefTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.modules.chef
    """

    def setup_loader_modules(self):
        return {
            chef: {
                "_exec_cmd": MagicMock(return_value={}),
                "__opts__": {"cachedir": RUNTIME_VARS.TMP},
            }
        }

    # 'client' function tests: 1

    def test_client(self):
        """
        Test if it execute a chef client run and return a dict
        """
        with patch("salt.utils.path.which", MagicMock(return_value=True)):
            self.assertDictEqual(chef.client(), {})

    # 'solo' function tests: 1

    def test_solo(self):
        """
        Test if it execute a chef solo run and return a dict
        """
        with patch("salt.utils.path.which", MagicMock(return_value=True)):
            self.assertDictEqual(chef.solo("/dev/sda1"), {})
