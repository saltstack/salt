# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''

# Import Python libs
from __future__ import absolute_import

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
import salt.modules.drbd as drbd


@skipIf(NO_MOCK, NO_MOCK_REASON)
class DrbdTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.modules.drbd
    '''
    def setup_loader_modules(self):
        return {drbd: {}}

    # 'overview' function tests: 1

    def test_overview(self):
        '''
        Test if it shows status of the DRBD devices
        '''
        ret = {'connection state': 'True',
               'device': 'Stack',
               'fs': 'None',
               'local disk state': 'UpToDate',
               'local role': 'master',
               'minor number': 'Salt',
               'mountpoint': 'True',
               'partner disk state': 'UpToDate',
               'partner role': 'minion',
               'percent': '888',
               'remains': '666',
               'total size': '50',
               'used': '50'}
        mock = MagicMock(return_value='Salt:Stack True master/minion \
        UpToDate/UpToDate True None 50 50 666 888')
        with patch.dict(drbd.__salt__, {'cmd.run': mock}):
            self.assertDictEqual(drbd.overview(), ret)

        ret = {'connection state': 'True',
               'device': 'Stack',
               'local disk state': 'UpToDate',
               'local role': 'master',
               'minor number': 'Salt',
               'partner disk state': 'partner',
               'partner role': 'minion',
               'synched': '5050',
               'synchronisation: ': 'syncbar'}
        mock = MagicMock(return_value='Salt:Stack True master/minion \
        UpToDate/partner syncbar None 50 50')
        with patch.dict(drbd.__salt__, {'cmd.run': mock}):
            self.assertDictEqual(drbd.overview(), ret)
