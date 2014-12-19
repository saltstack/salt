# -*- coding: utf-8 -*-
'''
    :codeauthor: Nitin Madhok <nmadhok@clemson.edu>`

    tests.unit.modules.zfs_test
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~
'''

# Import Salt Execution module to test
from salt.modules import zfs

# Import Salt Testing libs
from salttesting import skipIf, TestCase
from salttesting.helpers import ensure_in_syspath

# Import Mock libraries
from salttesting.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON,
)

ensure_in_syspath('../../')

# Globals
zfs.__salt__ = {}


# Skip this test case if we don't have access to mock!
@skipIf(NO_MOCK, NO_MOCK_REASON)
class ZfsTestCase(TestCase):
    '''
    This class contains a set of functions that test salt.modules.zfs module
    '''

    @patch('os.path.exists', MagicMock(return_value=True))
    def test_exists_success(self):
        '''
        Tests successful return of exists function
        '''
        ret = "NAME        USED  AVAIL  REFER  MOUNTPOINT\nmyzpool/mydataset    30K   157G    30K  /myzpool/mydataset"
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zfs.__salt__, {'cmd.run': mock_cmd}):
            self.assertEqual(zfs.exists('myzpool/mydataset'), True)

    @patch('os.path.exists', MagicMock(return_value=False))
    def test_exists_failure(self):
        '''
        Tests unsuccessful return of exists function
        '''
        ret = "cannot open 'myzpool/mydataset': dataset does not exist"
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zfs.__salt__, {'cmd.run': mock_cmd}):
            self.assertEqual(zfs.exists('myzpool/mydataset'), False)

if __name__ == '__main__':
    from integration import run_tests
    run_tests(ZfsTestCase, needs_daemon=False)
