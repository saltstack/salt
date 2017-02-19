# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Rupesh Tare <rupesht@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
import salt.modules.mine as mine


@skipIf(NO_MOCK, NO_MOCK_REASON)
class MineTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.modules.mine
    '''
    loader_module = mine

    def test_get_docker(self):
        '''
        Test for Get all mine data for 'docker.ps' and run an
        aggregation.
        '''
        ps_response = {
            'localhost': {
                'host': {
                    'interfaces': {
                        'docker0': {
                            'hwaddr': '88:99:00:00:99:99',
                            'inet': [{'address': '172.17.42.1',
                                     'broadcast': None,
                                     'label': 'docker0',
                                     'netmask': '255.255.0.0'}],
                            'inet6': [{'address': 'ffff::eeee:aaaa:bbbb:8888',
                                       'prefixlen': '64'}],
                            'up': True},
                        'eth0': {'hwaddr': '88:99:00:99:99:99',
                                'inet': [{'address': '192.168.0.1',
                                          'broadcast': '192.168.0.255',
                                          'label': 'eth0',
                                          'netmask': '255.255.255.0'}],
                                 'inet6': [{'address':
                                            'ffff::aaaa:aaaa:bbbb:8888',
                                            'prefixlen': '64'}],
                                 'up': True},
                }},
                'abcdefhjhi1234567899': {  # container Id
                    'Ports': [{'IP': '0.0.0.0',  # we bind on every interfaces
                                'PrivatePort': 80,
                                'PublicPort': 80,
                                'Type': 'tcp'}],
                     'Image': 'image:latest',
                     'Info': {'Id': 'abcdefhjhi1234567899'},
                },
            }}
        with patch.object(mine, 'get', return_value=ps_response):
            ret = mine.get_docker()
            # Sort ifaces since that will change between py2 and py3
            ret['image:latest']['ipv4'][80] = sorted(ret['image:latest']['ipv4'][80])
            self.assertEqual(ret,
                             {'image:latest': {
                                 'ipv4': {80: sorted([
                                     '172.17.42.1:80',
                                     '192.168.0.1:80',
                                 ])}}})

    def test_get_docker_with_container_id(self):
        '''
        Test for Get all mine data for 'docker.ps' and run an
        aggregation.
        '''
        ps_response = {
            'localhost': {
                'host': {
                    'interfaces': {
                        'docker0': {
                            'hwaddr': '88:99:00:00:99:99',
                            'inet': [{'address': '172.17.42.1',
                                      'broadcast': None,
                                      'label': 'docker0',
                                      'netmask': '255.255.0.0'}],
                            'inet6': [{'address': 'ffff::eeee:aaaa:bbbb:8888',
                                       'prefixlen': '64'}],
                            'up': True},
                        'eth0': {'hwaddr': '88:99:00:99:99:99',
                                 'inet': [{'address': '192.168.0.1',
                                           'broadcast': '192.168.0.255',
                                           'label': 'eth0',
                                           'netmask': '255.255.255.0'}],
                                 'inet6': [{'address':
                                            'ffff::aaaa:aaaa:bbbb:8888',
                                            'prefixlen': '64'}],
                                 'up': True},
                    }},
                'abcdefhjhi1234567899': {  # container Id
                                         'Ports': [{'IP': '0.0.0.0',  # we bind on every interfaces
                                                    'PrivatePort': 80,
                                                    'PublicPort': 80,
                                                    'Type': 'tcp'}],
                                         'Image': 'image:latest',
                                         'Info': {'Id': 'abcdefhjhi1234567899'},
                                         },
            }}
        with patch.object(mine, 'get', return_value=ps_response):
            ret = mine.get_docker(with_container_id=True)
            # Sort ifaces since that will change between py2 and py3
            ret['image:latest']['ipv4'][80] = sorted(ret['image:latest']['ipv4'][80])
            self.assertEqual(ret,
                             {'image:latest': {
                                 'ipv4': {80: sorted([
                                     ('172.17.42.1:80', 'abcdefhjhi1234567899'),
                                     ('192.168.0.1:80', 'abcdefhjhi1234567899'),
                                 ])}}})
