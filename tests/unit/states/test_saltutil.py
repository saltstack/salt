# -*- coding: utf-8 -*-
'''
    Tests for the saltutil state
'''
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch
)

# Import Salt Libs
import salt.states.saltutil as saltutil


@skipIf(NO_MOCK, NO_MOCK_REASON)
class Saltutil(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.states.saltutil
    '''
    def setup_loader_modules(self):
        return {saltutil: {'__opts__': {'test': False}}}

    def test_saltutil_sync_all_nochange(self):
        sync_output =   {
                            "clouds": [],
                            "engines": [],
                            "grains": [],
                            "beacons": [],
                            "utils": [],
                            "returners": [],
                            "modules": [],
                            "renderers": [],
                            "log_handlers": [],
                            "thorium": [],
                            "states": [],
                            "sdb": [],
                            "proxymodules": [],
                            "output": [],
                            "pillar": []
                        }
        state_id = 'somename'
        state_result = {'changes': {},
                        'comment': 'No updates to sync',
                        'name': 'somename',
                        'result': True
                       }

        mock_moduleout = MagicMock(return_value=sync_output)
        with patch.dict(saltutil.__salt__, {'saltutil.sync_all': mock_moduleout}):
            result = saltutil.sync_all(state_id, refresh=True)
            self.assertEqual(result, state_result)

    def  test_saltutil_sync_all_test(self):
        sync_output =   {
                            "clouds": [],
                            "engines": [],
                            "grains": [],
                            "beacons": [],
                            "utils": [],
                            "returners": [],
                            "modules": [],
                            "renderers": [],
                            "log_handlers": [],
                            "thorium": [],
                            "states": [],
                            "sdb": [],
                            "proxymodules": [],
                            "output": [],
                            "pillar": []
                        }
        state_id = 'somename'
        state_result = {'changes': {},
                        'comment': 'saltutil.sync_all would have been run',
                        'name': 'somename',
                        'result': None
                       }

        mock_moduleout = MagicMock(return_value=sync_output)
        with patch.dict(saltutil.__salt__, {'saltutil.sync_all': mock_moduleout}):
            with patch.dict(saltutil.__opts__, {"test": True}):
                result = saltutil.sync_all(state_id, refresh=True)
                self.assertEqual(result, state_result)


    def test_saltutil_sync_all_change(self):
        sync_output =   {
                            "clouds": [],
                            "engines": [],
                            "grains": [],
                            "beacons": [],
                            "utils": [],
                            "returners": [],
                            "modules": ["modules.file"],
                            "renderers": [],
                            "log_handlers": [],
                            "thorium": [],
                            "states": ["states.saltutil", "states.ssh_auth"],
                            "sdb": [],
                            "proxymodules": [],
                            "output": [],
                            "pillar": []
                        }
        state_id = 'somename'
        state_result = {'changes': {'modules': ['modules.file'],
                                    'states': ['states.saltutil', 'states.ssh_auth']},
                        'comment': 'Sync performed',
                        'name': 'somename',
                        'result': True
                       }

        mock_moduleout = MagicMock(return_value=sync_output)
        with patch.dict(saltutil.__salt__, {'saltutil.sync_all': mock_moduleout}):
            result = saltutil.sync_all(state_id, refresh=True)
            self.assertEqual(result, state_result)
