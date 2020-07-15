# -*- coding: utf-8 -*-
"""
    :codeauthor: :email:`Alexandru Bleotu <alexandru.bleotu@morganstanley.com>`

    Tests for functions in salt.modules.esxcluster
"""

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
import salt.modules.esxcluster as esxcluster

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class GetDetailsTestCase(TestCase, LoaderModuleMockMixin):
    """Tests for salt.modules.esxcluster.get_details"""

    def setup_loader_modules(self):
        return {
            esxcluster: {
                "__virtual__": MagicMock(return_value="esxcluster"),
                "__proxy__": {},
            }
        }

    def test_get_details(self):
        mock_get_details = MagicMock()
        with patch.dict(
            esxcluster.__proxy__, {"esxcluster.get_details": mock_get_details}
        ):
            esxcluster.get_details()
        mock_get_details.assert_called_once_with()
