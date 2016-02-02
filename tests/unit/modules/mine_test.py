# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Rupesh Tare <rupesht@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import
import copy

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)
from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')

# Import Salt Libs
import salt.utils
from salt.modules import mine


# Globals
mine.__salt__ = {}
mine.__opts__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class MineTestCase(TestCase):
    '''
    Test cases for salt.modules.mine
    '''
    def test_update(self):
        '''
        Test for Execute the configured functions
        '''
        with patch.dict(mine.__salt__,
                        {'config.merge': MagicMock(return_value={'A': 'B'}),
                         'data.update': MagicMock(return_value='A'),
                         'A': MagicMock(return_value='B')}):
            with patch.dict(mine.__opts__, {'file_client': 'local',
                                            'id': 'id'}):
                self.assertEqual(mine.update(True), 'A')

                with patch.object(mine, '_mine_send', return_value='A'):
                    self.assertEqual(mine.update(True), 'A')

    def test_send(self):
        '''
        Test for Send a specific function to the mine.
        '''

        self.assertFalse(mine.send('func'))

        with patch.dict(mine.__salt__, {'func': 'func'}):
            with patch.object(salt.utils,
                              'arg_lookup', return_value={'A': 'B'}):
                with patch.object(copy, 'deepcopy', return_value='A'):
                    with patch.object(salt.utils,
                                      'format_call', return_value='A'):
                        self.assertFalse(mine.send('func'), 'C')

        with patch.dict(mine.__salt__, {'A': MagicMock(),
                                        'data.update':
                                        MagicMock(return_value='update'),
                                        'data.getval':
                                        MagicMock(return_value='old')}):
            with patch.object(salt.utils,
                              'arg_lookup', return_value={'A': 'B'}):
                with patch.object(copy, 'deepcopy', return_value='A'):
                    with patch.object(salt.utils,
                                      'format_call',
                                      return_value={'args': 'a'}):
                        with patch.dict(mine.__opts__,
                                        {'file_client': 'local'}):
                            self.assertEqual(mine.send('0',
                                                       mine_function='A'),
                                             'update')

        with patch.dict(mine.__salt__, {'A': MagicMock(),
                                        'data.update':
                                        MagicMock(return_value='update'),
                                        'data.getval':
                                        MagicMock(return_value='old')}):
            with patch.object(salt.utils,
                              'arg_lookup', return_value={'A': 'B'}):
                with patch.object(copy, 'deepcopy', return_value='A'):
                    with patch.object(salt.utils,
                                      'format_call',
                                      return_value={'args': 'a'}):
                        with patch.dict(mine.__opts__,
                                        {'file_client': 'local1',
                                         'id': 'id'}):
                            with patch.object(mine,
                                              '_mine_send',
                                              return_value='A'):
                                self.assertEqual(mine.send('0',
                                                           mine_function='A'),
                                                 'A')

    def test_get(self):
        '''
        Test for Get data from the mine
         based on the target, function and expr_form
        '''
        with patch.dict(mine.__salt__, {'match.glob': MagicMock(),
                                        'match.pcre': MagicMock(),
                                        'match.list': MagicMock(),
                                        'match.grain': MagicMock(),
                                        'match.grain_pcre': MagicMock(),
                                        'match.ipcidr': MagicMock(),
                                        'match.compound': MagicMock(),
                                        'match.pillar': MagicMock(),
                                        'match.pillar_pcre': MagicMock(),
                                        'data.getval':
                                        MagicMock(return_value={})}):
            with patch.dict(mine.__opts__, {'file_client': 'local',
                                            'id': 'id'}):
                self.assertEqual(mine.get('tgt', 'fun'), {})

        with patch.dict(mine.__opts__, {'file_client': 'local1', 'id': 'id'}):
            with patch.object(mine, '_mine_get', return_value='A'):
                self.assertEqual(mine.get('tgt', 'fun'), 'A')

    def test_delete(self):
        '''
        Test for Remove specific function contents of
        minion. Returns True on success.
        '''
        with patch.dict(mine.__opts__, {'file_client': 'local', 'id': 'id'}):
            with patch.dict(mine.__salt__,
                            {'data.getval':
                             MagicMock(return_value={'A': 'B'}),
                             'data.update':
                             MagicMock(return_value='A')}):
                self.assertEqual(mine.delete('fun'), 'A')

        with patch.dict(mine.__opts__, {'file_client': 'local1', 'id': 'id'}):
            with patch.object(mine, '_mine_send', return_value='A'):
                self.assertEqual(mine.delete('fun'), 'A')

    def test_flush(self):
        '''
        Test for Remove all mine contents of minion. Returns True on success.
        '''
        with patch.dict(mine.__opts__, {'file_client': 'local'}):
            with patch.dict(mine.__salt__,
                            {'data.update':
                             MagicMock(return_value='A')}):
                self.assertEqual(mine.flush(), 'A')

        with patch.dict(mine.__opts__, {'file_client': 'local1', 'id': 'id'}):
            with patch.object(mine, '_mine_send', return_value='A'):
                self.assertEqual(mine.flush(), 'A')

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
