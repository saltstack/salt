# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''
# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import skipIf, TestCase
from salttesting.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch
)

from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')

# Import Salt Libs
from salt.modules import scsi
import os


# Globals
scsi.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class ScsiTestCase(TestCase):
    '''
    Test cases for salt.modules.scsi
    '''
    def test_ls_(self):
        '''
        Test for list SCSI devices, with details
        '''
        with patch.dict(scsi.__salt__,
                        {'cmd.run':
                         MagicMock(return_value='[A:a B:b C:c D:d]')}):
            self.assertDictEqual(scsi.ls_(),
                                 {'[A:a':
                                  {'major': 'C', 'lun': 'A:a', 'device': 'B:b',
                                   'model': '', 'minor': 'c', 'size': 'D:d]'}})

    def test_rescan_all(self):
        '''
        Test for list scsi devices
        '''
        mock = MagicMock(side_effect=[False, True])
        with patch.object(os.path, 'isdir', mock):
            self.assertEqual(scsi.rescan_all('host'),
                             'Host host does not exist')

            with patch.dict(scsi.__salt__,
                            {'cmd.run': MagicMock(return_value='A')}):
                self.assertListEqual(scsi.rescan_all('host'), ['A'])


if __name__ == '__main__':
    from integration import run_tests
    run_tests(ScsiTestCase, needs_daemon=False)
