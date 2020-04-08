# -*- coding: utf-8 -*-
"""
    :codeauthor: :email:`Alexandru Bleotu <alexandru.bleotu@morganstanley.com>`

    Tests for functions in salt.modules.esxdatacenter
"""

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
import salt.modules.esxdatacenter as esxdatacenter

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class GetDetailsTestCase(TestCase, LoaderModuleMockMixin):
    """Tests for salt.modules.esxdatacenter.get_details"""

    def setup_loader_modules(self):
        return {
            esxdatacenter: {
                "__virtual__": MagicMock(return_value="esxdatacenter"),
                "__proxy__": {},
            }
        }

    def test_get_details(self):
        mock_get_details = MagicMock()
        with patch.dict(
            esxdatacenter.__proxy__, {"esxdatacenter.get_details": mock_get_details}
        ):
            esxdatacenter.get_details()
        mock_get_details.assert_called_once_with()
