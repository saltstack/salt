# coding: utf-8

# Python libs
from __future__ import absolute_import
from collections import namedtuple

# Salt testing libs
from tests.support.unit import skipIf, TestCase
from tests.support.mock import NO_MOCK, NO_MOCK_REASON, patch, MagicMock
from tests.support.mixins import LoaderModuleMockMixin

# Salt libs
import salt.beacons.salt_proxy as salt_proxy

PATCH_OPTS = dict(autospec=True, spec_set=True)

FakeProcess = namedtuple('Process', 'cmdline pid')


@skipIf(NO_MOCK, NO_MOCK_REASON)
class SaltProxyBeaconTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test case for salt.beacons.[s]
    '''

    def setup_loader_modules(self):
        return {
            salt_proxy: {
                '__context__': {},
                '__salt__': {},
            }
        }

    def test_non_list_config(self):
        config = {}

        ret = salt_proxy.validate(config)

        self.assertEqual(ret, (False, 'Configuration for salt_proxy beacon'
                                      ' must be a list.'))

    def test_empty_config(self):
        config = [{}]

        ret = salt_proxy.validate(config)

        self.assertEqual(ret, (False, 'Configuration for salt_proxy '
                                      'beacon requires proxies.'))

    def test_salt_proxy_running(self):
        mock = MagicMock(return_value={'result': True})
        with patch.dict(salt_proxy.__salt__, {'salt_proxy.is_running': mock}):
            config = [{'proxies': {'p8000': ''}}]

            ret = salt_proxy.validate(config)

            ret = salt_proxy.beacon(config)
            self.assertEqual(ret, [{'p8000': 'Proxy p8000 is already running'}])

    def test_salt_proxy_not_running(self):
        is_running_mock = MagicMock(return_value={'result': False})
        configure_mock = MagicMock(return_value={'result': True,
                                                 'changes': {'new': 'Salt Proxy: Started proxy process for p8000',
                                                             'old': []}})
        cmd_run_mock = MagicMock(return_value={'pid': 1000,
                                               'retcode': 0,
                                               'stderr': '',
                                               'stdout': ''})
        with patch.dict(salt_proxy.__salt__,
                        {'salt_proxy.is_running': is_running_mock}), \
                patch.dict(salt_proxy.__salt__,
                           {'salt_proxy.configure_proxy': configure_mock}), \
                   patch.dict(salt_proxy.__salt__,
                              {'cmd.run_all': cmd_run_mock}):
            config = [{'proxies': {'p8000': ''}}]

            ret = salt_proxy.validate(config)

            ret = salt_proxy.beacon(config)
            self.assertEqual(ret, [{'p8000': 'Proxy p8000 was started'}])
