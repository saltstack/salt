# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals
import os

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.paths import TMP
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
import salt.modules.beacons as beacons
from salt.utils.event import SaltEvent

SOCK_DIR = os.path.join(TMP, 'test-socks')


@skipIf(NO_MOCK, NO_MOCK_REASON)
class BeaconsTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.modules.beacons
    '''
    def setup_loader_modules(self):
        return {beacons: {}}

    def test_delete(self):
        '''
        Test deleting a beacon.
        '''
        comm1 = 'Deleted beacon: ps.'
        event_returns = [
                         {'complete': True,
                          'tag': '/salt/minion/minion_beacons_delete_complete',
                          'beacons': {}},
                        ]

        with patch.dict(beacons.__opts__, {'beacons': {'ps': [{'processes': {'salt-master': 'stopped', 'apache2': 'stopped'}}]}, 'sock_dir': SOCK_DIR}):
            mock = MagicMock(return_value=True)
            with patch.dict(beacons.__salt__, {'event.fire': mock}):
                with patch.object(SaltEvent, 'get_event', side_effect=event_returns):
                    self.assertDictEqual(beacons.delete('ps'),
                                         {'comment': comm1, 'result': True})

    def test_add(self):
        '''
        Test adding a beacon
        '''
        comm1 = 'Added beacon: ps.'
        event_returns = [{'complete': True,
                          'tag': '/salt/minion/minion_beacons_list_complete',
                          'beacons': {}},
                         {'complete': True,
                          'tag': '/salt/minion/minion_beacons_list_available_complete',
                          'beacons': ['ps']},
                         {'complete': True,
                          'valid': True,
                          'vcomment': '',
                          'tag': '/salt/minion/minion_beacons_list_complete'},
                         {'complete': True,
                          'tag': '/salt/minion/minion_beacon_add_complete',
                          'beacons': {'ps': [{'processes': {'salt-master': 'stopped', 'apache2': 'stopped'}}]}}]

        with patch.dict(beacons.__opts__, {'beacons': {}, 'sock_dir': SOCK_DIR}):
            mock = MagicMock(return_value=True)
            with patch.dict(beacons.__salt__, {'event.fire': mock}):
                with patch.object(SaltEvent, 'get_event', side_effect=event_returns):
                    self.assertDictEqual(beacons.add('ps', [{'processes': {'salt-master': 'stopped', 'apache2': 'stopped'}}]),
                                         {'comment': comm1, 'result': True})

    def test_save(self):
        '''
        Test saving beacons.
        '''
        comm1 = 'Beacons saved to {0}beacons.conf.'.format(TMP + os.sep)
        with patch.dict(beacons.__opts__, {'config_dir': '', 'beacons': {},
                                           'default_include': TMP + os.sep,
                                           'sock_dir': SOCK_DIR}):

            mock = MagicMock(return_value=True)
            with patch.dict(beacons.__salt__, {'event.fire': mock}):
                _ret_value = {'complete': True, 'beacons': {}}
                with patch.object(SaltEvent, 'get_event', return_value=_ret_value):
                    self.assertDictEqual(beacons.save(),
                                         {'comment': comm1, 'result': True})

    def test_disable(self):
        '''
        Test disabling beacons
        '''
        comm1 = 'Disabled beacons on minion.'
        event_returns = [{'complete': True,
                          'tag': '/salt/minion/minion_beacons_disabled_complete',
                          'beacons': {'enabled': False,
                                      'ps': [{'processes': {'salt-master': 'stopped',
                                                            'apache2': 'stopped'}}]}}]

        with patch.dict(beacons.__opts__, {'beacons': {}, 'sock_dir': SOCK_DIR}):
            mock = MagicMock(return_value=True)
            with patch.dict(beacons.__salt__, {'event.fire': mock}):
                with patch.object(SaltEvent, 'get_event', side_effect=event_returns):
                    self.assertDictEqual(beacons.disable(),
                                         {'comment': comm1, 'result': True})

    def test_enable(self):
        '''
        Test enabling beacons
        '''
        comm1 = 'Enabled beacons on minion.'
        event_returns = [{'complete': True,
                          'tag': '/salt/minion/minion_beacon_enabled_complete',
                          'beacons': {'enabled': True,
                                      'ps': [{'processes': {'salt-master': 'stopped',
                                                            'apache2': 'stopped'}}]}}]

        with patch.dict(beacons.__opts__, {'beacons': {}, 'sock_dir': SOCK_DIR}):
            mock = MagicMock(return_value=True)
            with patch.dict(beacons.__salt__, {'event.fire': mock}):
                with patch.object(SaltEvent, 'get_event', side_effect=event_returns):
                    self.assertDictEqual(beacons.enable(),
                                         {'comment': comm1, 'result': True})
