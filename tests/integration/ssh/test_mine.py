# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.case import SSHCase
from tests.support.unit import skipIf

# Import Salt Libs
import salt.utils


@skipIf(salt.utils.is_windows(), 'salt-ssh not available on Windows')
class SSHMineTest(SSHCase):
    '''
    testing salt-ssh with mine
    '''
    def test_ssh_mine_get(self):
        '''
        test salt-ssh with mine
        '''
        ret = self.run_function('mine.get', ['localhost test.arg'], wipe=False)
        self.assertEqual(ret['localhost']['args'], ['itworked'])
