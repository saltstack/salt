# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import
import os
import shutil

# Import Salt Testing Libs
from tests.support.case import SSHCase

SSH_SLS = 'ssh_state_tests'


class SSHStateTest(SSHCase):
    '''
    testing the state system with salt-ssh
    '''
    def _check_dict_ret(self, ret, val, exp_ret):
        for key, value in ret.items():
            self.assertEqual(value[val], exp_ret)

    def _check_request(self, empty=False):
        check = self.run_function('state.check_request', wipe=False)
        if empty:
            self.assertFalse(bool(check))
        else:
            self._check_dict_ret(ret=check['default']['test_run']['local']['return'],
                       val='__sls__', exp_ret=SSH_SLS)

    def test_state_apply(self):
        '''
        test state.apply with salt-ssh
        '''
        ret = self.run_function('state.apply', [SSH_SLS])
        self._check_dict_ret(ret=ret, val='__sls__', exp_ret=SSH_SLS)

        check_file = self.run_function('file.file_exists', ['/tmp/test'])
        self.assertTrue(check_file)

    def test_state_request_check_clear(self):
        '''
        test state.request system with salt-ssh
        while also checking and clearing request
        '''
        request = self.run_function('state.request', [SSH_SLS], wipe=False)
        self._check_dict_ret(ret=request, val='__sls__', exp_ret=SSH_SLS)

        self._check_request()

        clear = self.run_function('state.clear_request', wipe=False)
        self._check_request(empty=True)

    def test_state_run_request(self):
        '''
        test state.request system with salt-ssh
        while also running the request later
        '''
        request = self.run_function('state.request', [SSH_SLS], wipe=False)
        self._check_dict_ret(ret=request, val='__sls__', exp_ret=SSH_SLS)

        run = self.run_function('state.run_request', wipe=False)

        check_file = self.run_function('file.file_exists', ['/tmp/test'], wipe=False)
        self.assertTrue(check_file)

    def tearDown(self):
        '''
        make sure to clean up any old ssh directories
        '''
        salt_dir = self.run_function('config.get', ['thin_dir'], wipe=False)
        if os.path.exists(salt_dir):
            shutil.rmtree(salt_dir)
