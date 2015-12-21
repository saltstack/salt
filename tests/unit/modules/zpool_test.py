# -*- coding: utf-8 -*-
'''
    :codeauthor: Nitin Madhok <nmadhok@clemson.edu>`

    tests.unit.modules.zpool_test
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~
'''

# Import Python libs
from __future__ import absolute_import

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

# Import Salt Execution module to test
from salt.modules import zpool

# Globals
zpool.__salt__ = {}


# Skip this test case if we don't have access to mock!
@skipIf(NO_MOCK, NO_MOCK_REASON)
class ZpoolTestCase(TestCase):
    '''
    This class contains a set of functions that test salt.modules.zpool module
    '''

    @patch('salt.modules.zpool._check_zpool', MagicMock(return_value='/sbin/zpool'))
    def test_exists_success(self):
        '''
        Tests successful return of exists function
        '''
        ret = {}
        ret['stdout'] = "NAME      SIZE  ALLOC   FREE    CAP  DEDUP  HEALTH  ALTROOT\nmyzpool   149G   128K   149G     0%  1.00x  ONLINE  -"
        ret['stderr'] = ""
        ret['retcode'] = 0
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zpool.__salt__, {'cmd.run_all': mock_cmd}):
            self.assertTrue(zpool.exists('myzpool'))

    @patch('salt.modules.zpool._check_zpool', MagicMock(return_value='/sbin/zpool'))
    def test_exists_failure(self):
        '''
        Tests failure return of exists function
        '''
        ret = {}
        ret['stdout'] = ""
        ret['stderr'] = "cannot open 'mypool': no such pool"
        ret['retcode'] = 1
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zpool.__salt__, {'cmd.run_all': mock_cmd}):
            self.assertFalse(zpool.exists('myzpool'))

    @patch('salt.modules.zpool._check_zpool', MagicMock(return_value='/sbin/zpool'))
    def test_healthy_success(self):
        '''
        Tests successful return of healthy function
        '''
        ret = {}
        ret['stdout'] = "all pools are healthy"
        ret['stderr'] = ""
        ret['retcode'] = 0
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zpool.__salt__, {'cmd.run_all': mock_cmd}):
            self.assertTrue(zpool.healthy())

    @patch('salt.modules.zpool._check_zpool', MagicMock(return_value='/sbin/zpool'))
    def test_status(self):
        '''
        Tests successful return of status function
        '''
        ret = {}
        ret['stdout'] = "\n".join([
            "  pool: mypool",
            " state: ONLINE",
            "  scan: scrub repaired 0 in 0h6m with 0 errors on Mon Dec 21 02:06:17 2015",
            "config:",
            "",
            "        NAME        STATE     READ WRITE CKSUM",
            "        mypool      ONLINE       0     0     0",
            "          mirror-0  ONLINE       0     0     0",
            "            c2t0d0  ONLINE       0     0     0",
            "            c2t1d0  ONLINE       0     0     0",
            "",
            "errors: No known data errors",
        ])
        ret['stderr'] = ""
        ret['retcode'] = 0
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zpool.__salt__, {'cmd.run_all': mock_cmd}):
            ret = zpool.status()
            self.assertEqual('ONLINE', ret['mypool']['state'])

if __name__ == '__main__':
    from integration import run_tests
    run_tests(ZpoolTestCase, needs_daemon=False)
