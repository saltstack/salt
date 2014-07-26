# coding: utf-8
import salt.loader

from tests.integration import ModuleCase


class NetworkUtilsTestCase(ModuleCase):
    def test_is_private(self):
        __salt__ = salt.loader.raw_mod(self.minion_opts, 'network', None)
        self.assertTrue(__salt__['network.is_private']('10.0.0.1'), True)

    def test_is_loopback(self):
        __salt__ = salt.loader.raw_mod(self.minion_opts, 'network', None)
        self.assertTrue(__salt__['network.is_loopback']('127.0.0.1'), True)

if __name__ == '__main__':
    from integration import run_tests
    run_tests(NetworkUtilsTestCase,
              needs_daemon=False)
