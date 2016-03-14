# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Rupesh Tare <rupesht@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.mock import (
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)
from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')

# Import Salt Libs
from salt.modules import mine


# Globals
mine.__salt__ = {}
mine.__opts__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class MineTestCase(TestCase):
    '''
    Test cases for salt.modules.mine
    '''
    def test_get_docker(self):
        '''
        Test for Get all mine data for 'dockerng.ps' and run an
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
            self.assertEqual(mine.get_docker(),
                             {'image:latest': {
                                 'ipv4': {80: [
                                     '172.17.42.1:80',
                                     '192.168.0.1:80',
                                 ]}}})

    def test_get_docker_with_container_id(self):
        '''
        Test for Get all mine data for 'dockerng.ps' and run an
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
            self.assertEqual(mine.get_docker(with_container_id=True),
                             {'image:latest': {
                                 'ipv4': {80: [
                                     ('172.17.42.1:80', 'abcdefhjhi1234567899'),
                                     ('192.168.0.1:80', 'abcdefhjhi1234567899'),
                                 ]}}})


if __name__ == '__main__':
    from integration import run_tests
    run_tests(MineTestCase, needs_daemon=False)
