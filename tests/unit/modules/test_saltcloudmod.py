# -*- coding: utf-8 -*-
"""
    :codeauthor: Rahul Handay <rahulha@saltstack.com>
"""

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
import salt.modules.saltcloudmod as saltcloudmod
import salt.utils.json

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class SaltcloudmodTestCase(TestCase, LoaderModuleMockMixin):
    """
        Test cases for salt.modules.saltcloudmod
    """

    def setup_loader_modules(self):
        return {saltcloudmod: {}}

    def setUp(self):
        self.mock_json_loads = MagicMock(side_effect=ValueError())

    def test_create(self):
        """
            Test if create the named vm
        """
        mock = MagicMock(return_value="""{"foo": "bar"}""")
        with patch.dict(saltcloudmod.__salt__, {"cmd.run_stdout": mock}):
            self.assertTrue(saltcloudmod.create("webserver", "rackspace_centos_512"))

            with patch.object(salt.utils.json, "loads", self.mock_json_loads):
                self.assertDictEqual(
                    saltcloudmod.create("webserver", "rackspace_centos_512"), {}
                )
