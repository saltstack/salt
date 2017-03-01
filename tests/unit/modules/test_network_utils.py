# coding: utf-8

# Import Python libs
from __future__ import absolute_import

# Import Salt Testing libs
from tests.support.case import ModuleCase

# Import Salt libs
import salt.loader


class NetworkUtilsTestCase(ModuleCase):
    def test_is_private(self):
        __salt__ = salt.loader.raw_mod(self.minion_opts, 'network', None)
        self.assertTrue(__salt__['network.is_private']('10.0.0.1'), True)

    def test_is_loopback(self):
        __salt__ = salt.loader.raw_mod(self.minion_opts, 'network', None)
        self.assertTrue(__salt__['network.is_loopback']('127.0.0.1'), True)
