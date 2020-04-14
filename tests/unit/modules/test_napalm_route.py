# -*- coding: utf-8 -*-
"""
    :codeauthor: :email:`Anthony Shaw <anthonyshaw@apache.org>`
"""

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

import tests.support.napalm as napalm_test_support

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock
from tests.support.unit import TestCase

import salt.modules.napalm_route as napalm_route  # NOQA


def mock_net_load(template, *args, **kwargs):
    raise ValueError("incorrect template {0}".format(template))


class NapalmRouteModuleTestCase(TestCase, LoaderModuleMockMixin):
    def setup_loader_modules(self):
        module_globals = {
            "__salt__": {
                "config.option": MagicMock(
                    return_value={"test": {"driver": "test", "key": "2orgk34kgk34g"}}
                ),
                "file.file_exists": napalm_test_support.true,
                "file.join": napalm_test_support.join,
                "file.get_managed": napalm_test_support.get_managed_file,
                "random.hash": napalm_test_support.random_hash,
                "net.load_template": mock_net_load,
            }
        }

        return {napalm_route: module_globals}

    def test_show(self):
        ret = napalm_route.show("1.2.3.4")
        assert ret["out"] == napalm_test_support.TEST_ROUTE
