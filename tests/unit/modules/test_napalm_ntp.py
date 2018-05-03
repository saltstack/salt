# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Anthony Shaw <anthonyshaw@apache.org>`
'''

# Import Python Libs
from __future__ import absolute_import, unicode_literals, print_function

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    MagicMock,
    NO_MOCK,
    NO_MOCK_REASON
)

import tests.support.napalm as napalm_test_support
import salt.modules.napalm_ntp as napalm_ntp  # NOQA


def mock_net_load_template(template, *args, **kwargs):
    if template == 'set_ntp_peers' or template == 'delete_ntp_peers':
        assert '1.2.3.4' in kwargs['peers']
    if template == 'set_ntp_servers' or template == 'delete_ntp_servers':
        assert '2.2.3.4' in kwargs['servers']


@skipIf(NO_MOCK, NO_MOCK_REASON)
class NapalmNtpModuleTestCase(TestCase, LoaderModuleMockMixin):

    def setup_loader_modules(self):
        module_globals = {
            '__salt__': {
                'config.option': MagicMock(return_value={
                    'test': {
                        'driver': 'test',
                        'key': '2orgk34kgk34g'
                    }
                }),
                'file.file_exists': napalm_test_support.true,
                'file.join': napalm_test_support.join,
                'file.get_managed': napalm_test_support.get_managed_file,
                'random.hash': napalm_test_support.random_hash,
                'net.load_template': mock_net_load_template
            }
        }

        return {napalm_ntp: module_globals}

    def test_peers(self):
        ret = napalm_ntp.peers()
        assert '172.17.17.1' in ret['out']

    def test_servers(self):
        ret = napalm_ntp.servers()
        assert '172.17.17.1' in ret['out']

    def test_stats(self):
        ret = napalm_ntp.stats()
        assert ret['out'][0]['reachability'] == 377

    def test_set_peers(self):
        ret = napalm_ntp.set_peers('1.2.3.4', '5.6.7.8')
        assert ret is None

    def test_set_servers(self):
        ret = napalm_ntp.set_servers('2.2.3.4', '6.6.7.8')
        assert ret is None

    def test_delete_servers(self):
        ret = napalm_ntp.delete_servers('2.2.3.4', '6.6.7.8')
        assert ret is None

    def test_delete_peers(self):
        ret = napalm_ntp.delete_peers('1.2.3.4', '5.6.7.8')
        assert ret is None
