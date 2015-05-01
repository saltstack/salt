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
        ret = "NAME      SIZE  ALLOC   FREE    CAP  DEDUP  HEALTH  ALTROOT\nmyzpool   149G   128K   149G     0%  1.00x  ONLINE  -"
        mock_cmd = MagicMock(return_value=ret)
        with patch.dict(zpool.__salt__, {'cmd.run': mock_cmd}):
            self.assertTrue(zpool.exists('myzpool'))

if __name__ == '__main__':
    from integration import run_tests
    run_tests(ZpoolTestCase, needs_daemon=False)
