# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import os
import shutil
import threading
import time

# Import Salt Testing Libs
from tests.support.case import SSHCase
from tests.support.paths import TMP

# Import Salt Libs
from salt.ext import six
from salt.ext.six.moves import range  # pylint: disable=redefined-builtin

SSH_SLS = 'ssh_state_tests'
SSH_SLS_FILE = '/tmp/test'


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

    def test_state_sls_id(self):
        '''
        test state.sls_id with salt-ssh
        '''
        ret = self.run_function('state.sls_id', ['ssh-file-test', SSH_SLS])
        self._check_dict_ret(ret=ret, val='__sls__', exp_ret=SSH_SLS)

        check_file = self.run_function('file.file_exists', ['/tmp/test'])
        self.assertTrue(check_file)

    def test_state_show_sls(self):
        '''
        test state.show_sls with salt-ssh
        '''
        ret = self.run_function('state.show_sls', [SSH_SLS])
        self._check_dict_ret(ret=ret, val='__sls__', exp_ret=SSH_SLS)

        check_file = self.run_function('file.file_exists', [SSH_SLS_FILE], wipe=False)
        self.assertFalse(check_file)

    def test_state_show_top(self):
        '''
        test state.show_top with salt-ssh
        '''
        ret = self.run_function('state.show_top')
        self.assertEqual(ret, {'base': ['core', 'master_tops_test']})

    def test_state_single(self):
        '''
        state.single with salt-ssh
        '''
        ret_out = {'name': 'itworked',
                   'result': True,
                   'comment': 'Success!'}

        single = self.run_function('state.single',
                                   ['test.succeed_with_changes name=itworked'])

        for key, value in six.iteritems(single):
            self.assertEqual(value['name'], ret_out['name'])
            self.assertEqual(value['result'], ret_out['result'])
            self.assertEqual(value['comment'], ret_out['comment'])

    def test_show_highstate(self):
        '''
        state.show_highstate with salt-ssh
        '''
        high = self.run_function('state.show_highstate')
        destpath = os.path.join(TMP, 'testfile')
        self.assertTrue(isinstance(high, dict))
        self.assertTrue(destpath in high)
        self.assertEqual(high[destpath]['__env__'], 'base')

    def test_state_high(self):
        '''
        state.high with salt-ssh
        '''
        ret_out = {'name': 'itworked',
                   'result': True,
                   'comment': 'Success!'}

        high = self.run_function('state.high', ['"{"itworked": {"test": ["succeed_with_changes"]}}"'])

        for key, value in six.iteritems(high):
            self.assertEqual(value['name'], ret_out['name'])
            self.assertEqual(value['result'], ret_out['result'])
            self.assertEqual(value['comment'], ret_out['comment'])

    def test_show_lowstate(self):
        '''
        state.show_lowstate with salt-ssh
        '''
        low = self.run_function('state.show_lowstate')
        self.assertTrue(isinstance(low, list))
        self.assertTrue(isinstance(low[0], dict))

    def test_state_low(self):
        '''
        state.low with salt-ssh
        '''
        ret_out = {'name': 'itworked',
                   'result': True,
                   'comment': 'Success!'}

        low = self.run_function('state.low', ['"{"state": "test", "fun": "succeed_with_changes", "name": "itworked"}"'])

        for key, value in six.iteritems(low):
            self.assertEqual(value['name'], ret_out['name'])
            self.assertEqual(value['result'], ret_out['result'])
            self.assertEqual(value['comment'], ret_out['comment'])

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

        check_file = self.run_function('file.file_exists', [SSH_SLS_FILE], wipe=False)
        self.assertTrue(check_file)

    def test_state_running(self):
        '''
        test state.running with salt-ssh
        '''
        def _run_in_background():
            self.run_function('state.sls', ['running'], wipe=False)

        bg_thread = threading.Thread(target=_run_in_background)
        bg_thread.start()

        expected = 'The function "state.pkg" is running as'
        for _ in range(3):
            time.sleep(5)
            get_sls = self.run_function('state.running', wipe=False)
            try:
                self.assertIn(expected, ' '.join(get_sls))
            except AssertionError:
                pass
            else:
                # We found the expected return
                break
        else:
            self.fail(
                'Did not find \'{0}\' in state.running return'.format(expected)
            )

        # make sure we wait until the earlier state is complete
        future = time.time() + 120
        while True:
            if time.time() > future:
                break
            if expected not in ' '.join(self.run_function('state.running', wipe=False)):
                break

    def tearDown(self):
        '''
        make sure to clean up any old ssh directories
        '''
        salt_dir = self.run_function('config.get', ['thin_dir'], wipe=False)
        if os.path.exists(salt_dir):
            shutil.rmtree(salt_dir)

        if os.path.exists(SSH_SLS_FILE):
            os.remove(SSH_SLS_FILE)
