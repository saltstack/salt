# -*- coding: utf-8 -*-
'''
    :codeauthor: Rahul Handay <rahulha@saltstack.com>
'''

# Import Python Libs
from __future__ import absolute_import, unicode_literals, print_function

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
import salt.states.network as network

import logging
log = logging.getLogger(__name__)


class MockNetwork(object):
    '''
        Mock network class
    '''
    def __init__(self):
        pass

    @staticmethod
    def interfaces():
        '''
            Mock interface method
        '''
        return {'salt': {'up': 1}}


class MockGrains(object):
    '''
        Mock Grains class
    '''
    def __init__(self):
        pass

    @staticmethod
    def grains(lis, bol):
        '''
            Mock grains method
        '''
        return {'A': 'B'}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class NetworkTestCase(TestCase, LoaderModuleMockMixin):
    '''
        Validate the network state
    '''
    def setup_loader_modules(self):
        return {network: {}}

    def test_managed(self):
        '''
            Test to ensure that the named interface is configured properly
        '''
        with patch('salt.states.network.salt.utils.network', MockNetwork()), \
                patch('salt.states.network.salt.loader', MockGrains()):
            ret = {'name': 'salt',
                   'changes': {},
                   'result': False,
                   'comment': ''}

            change = {'interface': '--- \n+++ \n@@ -1 +1 @@\n-A\n+B',
                      'status': 'Interface salt restart to validate'}

            mock = MagicMock(side_effect=[AttributeError, 'A', 'A', 'A', 'A', 'A'])
            with patch.dict(network.__salt__, {"ip.get_interface": mock}):
                self.assertDictEqual(network.managed('salt',
                                                     'stack', test='a'), ret)

                mock = MagicMock(return_value='B')
                with patch.dict(network.__salt__, {"ip.build_interface": mock}):
                    mock = MagicMock(side_effect=AttributeError)
                    with patch.dict(network.__salt__, {"ip.get_bond": mock}):
                        self.assertDictEqual(network.managed('salt',
                                                             'bond',
                                                             test='a'), ret)

                    ret.update({'comment': 'Interface salt is set to be'
                                ' updated:\n--- \n+++ \n@@ -1 +1 @@\n-A\n+B',
                                'result': None})
                    self.assertDictEqual(network.managed('salt', 'stack',
                                                         test='a'), ret)

                    mock = MagicMock(return_value=True)
                    with patch.dict(network.__salt__, {"ip.down": mock}):
                        with patch.dict(network.__salt__, {"ip.up": mock}):
                            ret.update({'comment': 'Interface salt updated.',
                                        'result': True,
                                        'changes': change})
                            self.assertDictEqual(network.managed('salt', 'stack'),
                                                 ret)

                            with patch.dict(network.__grains__, {"A": True}):
                                with patch.dict(network.__salt__,
                                                {"saltutil.refresh_modules": mock}
                                                ):
                                    ret.update({'result': True,
                                                'changes': {'interface': '--- \n+'
                                                            '++ \n@@ -1 +1 @@\n-A'
                                                            '\n+B',
                                                            'status': 'Interface'
                                                            ' salt down'}})
                                    self.assertDictEqual(network.managed('salt',
                                                                         'stack',
                                                                         False),
                                                         ret)

    def test_routes(self):
        '''
            Test to manage network interface static routes.
        '''
        ret = {'name': 'salt',
               'changes': {},
               'result': False,
               'comment': ''}

        mock = MagicMock(side_effect=[AttributeError, False, False, "True",
                                      False, False])
        with patch.dict(network.__salt__, {"ip.get_routes": mock}):
            self.assertDictEqual(network.routes('salt'), ret)

            mock = MagicMock(side_effect=[False, True, '', True, True])
            with patch.dict(network.__salt__, {"ip.build_routes": mock}):
                ret.update({'result': True,
                            'comment': 'Interface salt routes are up to date.'
                            })
                self.assertDictEqual(network.routes('salt', test='a'), ret)

                ret.update({'comment': 'Interface salt routes are'
                            ' set to be added.',
                            'result': None})
                self.assertDictEqual(network.routes('salt', test='a'), ret)

                ret.update({'comment': 'Interface salt routes are set to be'
                            ' updated:\n--- \n+++ \n@@ -1,4 +0,0 @@\n-T\n-r'
                            '\n-u\n-e'})
                self.assertDictEqual(network.routes('salt', test='a'), ret)

                mock = MagicMock(side_effect=[AttributeError, True])
                with patch.dict(network.__salt__,
                                {"ip.apply_network_settings": mock}):
                    ret.update({'changes': {'network_routes':
                                            'Added interface salt routes.'},
                                'comment': '',
                                'result': False})
                    self.assertDictEqual(network.routes('salt'), ret)

                    ret.update({'changes': {'network_routes':
                                            'Added interface salt routes.'},
                                'comment': 'Interface salt routes added.',
                                'result': True})
                    self.assertDictEqual(network.routes('salt'), ret)

    def test_system(self):
        '''
            Test to ensure that global network settings
            are configured properly
        '''
        ret = {'name': 'salt',
               'changes': {},
               'result': False,
               'comment': ''}

        with patch.dict(network.__opts__, {"test": True}):
            mock = MagicMock(side_effect=[AttributeError, False, False, 'As'])
            with patch.dict(network.__salt__,
                            {"ip.get_network_settings": mock}):
                self.assertDictEqual(network.system('salt'), ret)

                mock = MagicMock(side_effect=[False, True, ''])
                with patch.dict(network.__salt__,
                                {"ip.build_network_settings": mock}):
                    ret.update({'comment': 'Global network settings'
                                ' are up to date.',
                                'result': True})
                    self.assertDictEqual(network.system('salt'), ret)

                    ret.update({'comment': 'Global network settings are set to'
                                ' be added.',
                                'result': None})
                    self.assertDictEqual(network.system('salt'), ret)

                    ret.update({'comment': 'Global network settings are set to'
                                ' be updated:\n--- \n+++ \n@@ -1,2 +0,0'
                                ' @@\n-A\n-s'})
                    self.assertDictEqual(network.system('salt'), ret)

        with patch.dict(network.__opts__, {"test": False}):
            mock = MagicMock(side_effect=[False, False])
            with patch.dict(network.__salt__,
                            {"ip.get_network_settings": mock}):
                mock = MagicMock(side_effect=[True, True])
                with patch.dict(network.__salt__,
                                {"ip.build_network_settings": mock}):
                    mock = MagicMock(side_effect=[AttributeError, True])
                    with patch.dict(network.__salt__,
                                    {"ip.apply_network_settings": mock}):
                        ret.update({'changes': {'network_settings':
                                                'Added global network'
                                                ' settings.'},
                                    'comment': '',
                                    'result': False})
                        self.assertDictEqual(network.system('salt'), ret)

                        ret.update({'changes': {'network_settings':
                                                'Added global network'
                                                ' settings.'},
                                    'comment': 'Global network settings'
                                    ' are up to date.',
                                    'result': True})
                        self.assertDictEqual(network.system('salt'), ret)
