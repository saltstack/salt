# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Anthony Shaw <anthonyshaw@apache.org>`
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    patch,
    MagicMock,
    NO_MOCK,
    NO_MOCK_REASON
)
import salt.modules.libcloud_loadbalancer as libcloud_loadbalancer

from libcloud.loadbalancer.base import BaseDriver, LoadBalancer, Algorithm


class MockLBDriver(BaseDriver):
    def __init__(self):
        self._TEST_BALANCER = LoadBalancer(
            id='test_id', name='test_balancer', 
            state=0,  # RUNNING
            ip='1.2.3.4', 
            port=80, driver=self, 
            extra={})

    def get_balancer(self, balancer_id):
        assert balancer_id == 'test_balancer'
        return self._TEST_BALANCER

    def list_balancers(self):
        return [self._TEST_BALANCER]

    def list_protocols(self):
        return ['http', 'https']

    def create_balancer(self, name, port, protocol, algorithm, members):
        assert name == 'new_test_balancer'
        assert port == 80
        assert protocol == 'http'
        assert isinstance(algorithm, (Algorithm, int))
        assert isinstance(members, list)
        return self._TEST_BALANCER

    def destroy_balancer(self, balancer):
        assert balancer == self._TEST_BALANCER
        return True

def get_mock_driver():
    return MockLBDriver()


@skipIf(NO_MOCK, NO_MOCK_REASON)
@patch('salt.modules.libcloud_loadbalancer._get_driver',
       MagicMock(return_value=MockLBDriver()))
class LibcloudLoadBalancerModuleTestCase(TestCase, LoaderModuleMockMixin):

    def setup_loader_modules(self):
        module_globals = {
            '__salt__': {
                'config.option': MagicMock(return_value={
                    'test': {
                        'driver': 'test',
                        'key': '2orgk34kgk34g'
                    }
                })
            }
        }
        if libcloud_loadbalancer.HAS_LIBCLOUD is False:
            module_globals['sys.modules'] = {'libcloud': MagicMock()}

        return {libcloud_loadbalancer: module_globals}

    def test_module_creation(self):
        client = libcloud_loadbalancer._get_driver('test')
        self.assertFalse(client is None)

    def test_init(self):
        with patch('salt.utils.compat.pack_dunder', return_value=False) as dunder:
            libcloud_loadbalancer.__init__(None)
            dunder.assert_called_with('salt.modules.libcloud_loadbalancer')

    def _validate_balancer(self, balancer):
        self.assertEqual(balancer['name'], 'test_balancer')

    def test_list_balancers(self):
        balancers = libcloud_loadbalancer.list_balancers('test')
        self.assertEqual(len(balancers), 1)
        self._validate_balancer(balancers[0])

    def test_list_protocols(self):
        protocols = libcloud_loadbalancer.list_protocols('test')
        self.assertEqual(len(protocols), 2)
        self.assertTrue('http' in protocols)

    def test_create_balancer(self):
        balancer = libcloud_loadbalancer.create_balancer('new_test_balancer', 80, 'http', 'test')
        self._validate_balancer(balancer)

    def test_destroy_balancer(self):
        result = libcloud_loadbalancer.destroy_balancer('test_balancer', 'test')
        self.assertTrue(result)