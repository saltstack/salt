# -*- coding: utf-8 -*-
'''
salt-ssh testing
'''
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import os
import shutil

# Import salt testing libs
from tests.support.case import SSHCase


class SSHTest(SSHCase):
    '''
    Test general salt-ssh functionality
    '''
    def test_ping(self):
        '''
        Test a simple ping
        '''
        ret = self.run_function('test.ping')
        self.assertTrue(ret, 'Ping did not return true')

    def test_thin_dir(self):
        '''
        test to make sure thin_dir is created
        and salt-call file is included
        '''
        thin_dir = self.run_function('config.get', ['thin_dir'], wipe=False)
        os.path.isdir(thin_dir)
        os.path.exists(os.path.join(thin_dir, 'salt-call'))
        os.path.exists(os.path.join(thin_dir, 'running_data'))

    def tearDown(self):
        '''
        make sure to clean up any old ssh directories
        '''
        salt_dir = self.run_function('config.get', ['thin_dir'], wipe=False)
        if os.path.exists(salt_dir):
            shutil.rmtree(salt_dir)
