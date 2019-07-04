# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing Libs
from tests.support.case import SSHCase
from tests.support.unit import skipIf

# Import Salt Libs
import salt.utils.platform

import timeout_decorator


@skipIf(salt.utils.platform.is_windows(), 'salt-ssh not available on Windows')
class SSHRawTest(SSHCase):
    '''
    testing salt-ssh with raw calls
    '''
    @timeout_decorator.timeout(60, use_signals=False)
    def test_ssh_raw(self):
        '''
        test salt-ssh with -r argument
        '''
        msg = 'password: foo'
        ret = self.run_function('echo {0}'.format(msg), raw=True)
        self.assertEqual(ret['stdout'], msg + '\n')
