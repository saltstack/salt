# -*- coding: utf-8 -*-
'''
unit tests for the saltutil module
'''
# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import skipIf, TestCase
from salttesting.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    call,
    patch)

from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')

# Import Salt Libs
from salt.modules import saltutil


@skipIf(NO_MOCK, NO_MOCK_REASON)
@patch('salt.utils.extmods.sync')
class SaltutilTestCase(TestCase):

    def setUp(self):
        saltutil.__opts__ = {}

    @patch('salt.modules.saltutil.refresh_pillar', return_value=True)
    @patch('salt.modules.saltutil.refresh_modules', return_value=True)
    def test_sync_all_local_refresh(self, mock_ref_modules,
                                    mock_ref_pillar, mock_extmods_sync):
        '''
        Test to ensure sync_all uses base and refreshes modules and
        pillar only once
        '''
        with patch.dict(saltutil.__opts__, {'file_client': 'local'}):
            mock_extmods_sync.return_value = True, False
            # Refresh modules and pillar
            ret = saltutil.sync_all(None, True)
            calls = []
            for r in ret:
                # Rename due to mod not mapping to mod function name
                if r == 'proxymodules':
                    r = 'proxy'
                calls.append(call(saltutil.__opts__,
                                  r,
                                  saltenv=['base']))
            mock_extmods_sync.assert_has_calls(calls, any_order=True)
            mock_ref_modules.assert_called_once()
            mock_ref_pillar.assert_called_once()

    @patch('salt.modules.saltutil.refresh_pillar', return_value=None)
    @patch('salt.modules.saltutil.refresh_modules', return_value=None)
    def test_sync_all_local_no_refresh(self, mock_ref_modules,
                                       mock_ref_pillar, mock_extmods_sync):
        '''
        test to ensure that sync_all doesnt call refreshes more than
        once
        '''
        with patch.dict(saltutil.__opts__, {'file_client': 'local'}):
            mock_extmods_sync.return_value = True, False
            # skip all refresh of modules and pillar
            ret = saltutil.sync_all(None, False)
            calls = []
            for r in ret:
                # rename due to mod not mapping to mod function name
                if r == 'proxymodules':
                    r = 'proxy'
                calls.append(call(saltutil.__opts__,
                                  r,
                                  saltenv=['base']))
            mock_extmods_sync.assert_has_calls(calls, any_order=True)
            mock_ref_modules.assert_not_called()
            mock_ref_pillar.assert_not_called()

    def test_sync_all_master_no_pillar(self, mock_extmods_sync):
        '''
        test to ensure that pillar is skipped during sync_all on master
        '''
        with patch.dict(saltutil.__opts__, {'file_client': 'remote'}):
            mock_extmods_sync.return_value = True, False
            # skip all refresh of modules and pillar
            saltutil.sync_all(None, False)
            # pillar sync shouldnt happen on remote
            pillar_call = call(saltutil.__opts__, 'pillar', saltenv=['base'])
            assert pillar_call not in mock_extmods_sync.call_args_list
