# -*- coding: utf-8 -*-
'''
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
    :codeauthor: Nick Wang <nwang@suse.com>
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

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
        mock_cmd = MagicMock(return_value='Salt:Stack True master/minion \
        UpToDate/UpToDate True None 50 50 666 888')
        with patch.dict(drbd.__salt__, {'cmd.run': mock_cmd}):
            assert drbd.overview() == ret

        ret = {'connection state': 'True',
               'device': 'Stack',
               'local disk state': 'UpToDate',
               'local role': 'master',
               'minor number': 'Salt',
               'partner disk state': 'partner',
               'partner role': 'minion',
               'synched': '5050',
               'synchronisation: ': 'syncbar'}
        mock_cmd = MagicMock(return_value='Salt:Stack True master/minion \
        UpToDate/partner syncbar None 50 50')
        with patch.dict(drbd.__salt__, {'cmd.run': mock_cmd}):
            assert drbd.overview() == ret

        ret = {'connection state': 'True',
               'device': 'Stack',
               'local disk state': 'UpToDate',
               'local role': 'master',
               'minor number': 'Salt',
               'partner disk state': 'partner',
               'partner role': 'master',
               'synched': '6050',
               'synchronisation: ': 'syncbar'}
        mock_cmd = MagicMock(return_value='Salt:Stack True master(2*) \
        UpToDate/partner syncbar None 60 50')
        with patch.dict(drbd.__salt__, {'cmd.run': mock_cmd}):
            assert drbd.overview() == ret

        ret = {'connection state': 'True',
               'device': 'Stack',
               'local disk state': 'UpToDate',
               'local role': 'master',
               'minor number': 'Salt',
               'partner disk state': 'UpToDate',
               'partner role': 'minion'}
        mock_cmd = MagicMock(return_value='Salt:Stack True master/minion \
        UpToDate(2*)')
        with patch.dict(drbd.__salt__, {'cmd.run': mock_cmd}):
            assert drbd.overview() == ret

    def test_status(self):
        '''
        Test if it shows status of the DRBD resources via drbdadm
        '''
        ret = [{'local role': 'Primary',
                'local volumes': [{'disk': 'UpToDate'}],
                'peer nodes': [{'peer volumes': [{'done': '96.47',
                    'peer-disk': 'Inconsistent', 'replication': 'SyncSource'}],
                'peernode name': 'opensuse-node2',
                'role': 'Secondary'}],
                'resource name': 'single'}]

        fake = {}
        fake['stdout'] = '''
single role:Primary
  disk:UpToDate
  opensuse-node2 role:Secondary
    replication:SyncSource peer-disk:Inconsistent done:96.47
'''
        fake['stderr'] = ""
        fake['retcode'] = 0

        mock_cmd = MagicMock(return_value=fake)

        with patch.dict(drbd.__salt__, {'cmd.run_all': mock_cmd}):
            assert drbd.status() == ret

        ret = [{'local role': 'Primary',
                'local volumes': [{'disk': 'UpToDate', 'volume': '0'},
                                  {'disk': 'UpToDate', 'volume': '1'}
                                 ],
                'peer nodes': [{'peer volumes': [{'peer-disk': 'UpToDate', 'volume': '0'},
                                                 {'peer-disk': 'UpToDate', 'volume': '1'}
                                                ],
                                'peernode name': 'node2',
                                'role': 'Secondary'},
                               {'peer volumes': [{'peer-disk': 'UpToDate', 'volume': '0'},
                                                 {'peer-disk': 'UpToDate', 'volume': '1'}
                                                ],
                                'peernode name': 'node3',
                                'role': 'Secondary'}
                              ],
                'resource name': 'test'},
               {'local role': 'Primary',
                'local volumes': [{'disk': 'UpToDate', 'volume': '0'},
                                  {'disk': 'UpToDate', 'volume': '1'}
                                 ],
                'peer nodes': [{'peer volumes': [{'peer-disk': 'UpToDate', 'volume': '0'},
                                                 {'peer-disk': 'UpToDate', 'volume': '1'}
                                                ],
                                'peernode name': 'node2',
                                'role': 'Secondary'},
                               {'peer volumes': [{'peer-disk': 'UpToDate', 'volume': '0'},
                                                 {'peer-disk': 'UpToDate', 'volume': '1'}
                                                ],
                                'peernode name': 'node3',
                                'role': 'Secondary'}
                              ],
                'resource name': 'res'}
              ]

        fake = {}
        fake['stdout'] = '''
test role:Primary
  volume:0 disk:UpToDate
  volume:1 disk:UpToDate
  node2 role:Secondary
    volume:0 peer-disk:UpToDate
    volume:1 peer-disk:UpToDate
  node3 role:Secondary
    volume:0 peer-disk:UpToDate
    volume:1 peer-disk:UpToDate

res role:Primary
  volume:0 disk:UpToDate
  volume:1 disk:UpToDate
  node2 role:Secondary
    volume:0 peer-disk:UpToDate
    volume:1 peer-disk:UpToDate
  node3 role:Secondary
    volume:0 peer-disk:UpToDate
    volume:1 peer-disk:UpToDate

'''
        fake['stderr'] = ""
        fake['retcode'] = 0

        mock_cmd = MagicMock(return_value=fake)

        with patch.dict(drbd.__salt__, {'cmd.run_all': mock_cmd}):
            assert drbd.status() == ret

        ret = {'Unknown parser': ' single role:Primary'}
        fake = {}
        fake['stdout'] = '''
 single role:Primary
'''
        fake['stderr'] = ""
        fake['retcode'] = 0

        mock_cmd = MagicMock(return_value=fake)

        with patch.dict(drbd.__salt__, {'cmd.run_all': mock_cmd}):
            assert drbd.status() == ret
