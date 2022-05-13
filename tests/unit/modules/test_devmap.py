"""
    :codeauthor: Rupesh Tare <rupesht@saltstack.com>
"""


import os.path

import salt.modules.devmap as devmap
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class DevMapTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.modules.devmap
    """

    def setup_loader_modules(self):
        return {devmap: {}}

    def test_multipath_list(self):
        """
        Test for Device-Mapper Multipath list
        """
        mock = MagicMock(return_value="A")
        with patch.dict(devmap.__salt__, {"cmd.run": mock}):
            self.assertEqual(devmap.multipath_list(), ["A"])

    def test_multipath_flush(self):
        """
        Test for Device-Mapper Multipath flush
        """
        mock = MagicMock(return_value=False)
        with patch.object(os.path, "exists", mock):
            self.assertEqual(devmap.multipath_flush("device"), "device does not exist")

        mock = MagicMock(return_value=True)
        with patch.object(os.path, "exists", mock):
            mock = MagicMock(return_value="A")
            with patch.dict(devmap.__salt__, {"cmd.run": mock}):
                self.assertEqual(devmap.multipath_flush("device"), ["A"])
