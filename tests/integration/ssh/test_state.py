# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import os
import shutil
import threading
import time
import logging

# Import Salt Testing Libs
from tests.support.runtests import RUNTIME_VARS
from tests.support.case import SSHCase
from tests.support.helpers import flaky

# Import Salt Libs
from salt.ext import six
from salt.ext.six.moves import range  # pylint: disable=redefined-builtin

SSH_SLS = 'ssh_state_tests'
SSH_SLS_FILE = '/tmp/test'

log = logging.getLogger(__name__)


class SSHStateTest(SSHCase):
    '''
    testing the state system with salt-ssh
    '''
    def _check_dict_ret(self, ret, val, exp_ret, equal=True):
        self.assertIsInstance(ret, dict)
        for key, value in ret.items():
            self.assertIsInstance(value, dict)
            if equal:
                self.assertEqual(value[val], exp_ret)
            else:
                self.assertNotEqual(value[val], exp_ret)

    def _check_request(self, empty=False):
        check = self.run_function('state.check_request', wipe=False)
        if empty:
            self.assertFalse(bool(check), 'bool({0}) is not False'.format(check))
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
        # check state.sls_id with test=True
        ret = self.run_function('state.sls_id', ['ssh-file-test', SSH_SLS,
                                                 'test=True'])
        self._check_dict_ret(ret=ret, val='comment',
                             exp_ret='The file /tmp/test is set to be changed\nNote: No changes made, actual changes may\nbe different due to other states.')

        # check state.sls_id without test=True
        ret = self.run_function('state.sls_id', ['ssh-file-test', SSH_SLS])
        self._check_dict_ret(ret=ret, val='__sls__', exp_ret=SSH_SLS)

        # make sure the other id in the state was not run
        self._check_dict_ret(ret=ret, val='__id__',
                             exp_ret='second_id', equal=False)

        check_file = self.run_function('file.file_exists', ['/tmp/test'])
        self.assertTrue(check_file)

    def test_state_sls_wrong_id(self):
        '''
        test state.sls_id when id does not exist
        '''
        # check state.sls_id with test=True
        ret = self.run_function('state.sls_id', ['doesnotexist', SSH_SLS])
        assert 'No matches for ID' in ret

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

        self.assertIsInstance(single, dict)
        for key, value in six.iteritems(single):
            self.assertIsInstance(value, dict)
            self.assertEqual(value['name'], ret_out['name'])
            self.assertEqual(value['result'], ret_out['result'])
            self.assertEqual(value['comment'], ret_out['comment'])

    def test_show_highstate(self):
        '''
        state.show_highstate with salt-ssh
        '''
        high = self.run_function('state.show_highstate')
        destpath = os.path.join(RUNTIME_VARS.TMP, 'testfile')
        self.assertIsInstance(high, dict)
        self.assertIn(destpath, high)
        self.assertEqual(high[destpath]['__env__'], 'base')

    def test_state_high(self):
        '''
        state.high with salt-ssh
        '''
        ret_out = {'name': 'itworked',
                   'result': True,
                   'comment': 'Success!'}

        high = self.run_function('state.high',
                                 ['"{"itworked": {"test": ["succeed_with_changes"]}}"'])

        self.assertIsInstance(high, dict)
        for key, value in six.iteritems(high):
            self.assertIsInstance(value, dict)
            self.assertEqual(value['name'], ret_out['name'])
            self.assertEqual(value['result'], ret_out['result'])
            self.assertEqual(value['comment'], ret_out['comment'])

    def test_show_lowstate(self):
        '''
        state.show_lowstate with salt-ssh
        '''
        low = self.run_function('state.show_lowstate')
        self.assertIsInstance(low, list)
        self.assertIsInstance(low[0], dict)

    def test_state_low(self):
        '''
        state.low with salt-ssh
        '''
        ret_out = {'name': 'itworked',
                   'result': True,
                   'comment': 'Success!'}

        low = self.run_function(
                'state.low',
                ['"{"state": "test", "fun": "succeed_with_changes", "name": "itworked"}"'])

        self.assertIsInstance(low, dict)
        for key, value in six.iteritems(low):
            self.assertIsInstance(value, dict)
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

    @flaky
    def test_state_running(self):
        '''
        test state.running with salt-ssh
        '''
        def _run_in_background():
            self.run_function('state.sls', ['running'], wipe=False)

        bg_thread = threading.Thread(target=_run_in_background)
        bg_thread.start()

        expected = 'The function "state.pkg" is running as'
        state_ret = []
        for _ in range(30):
            time.sleep(5)
            get_sls = self.run_function('state.running', wipe=False)
            state_ret.append(get_sls)
            if expected in ' '.join(get_sls):
                # We found the expected return
                break
        else:
            self.fail(
                    'Did not find \'{0}\' in state.running return: {1}'.format(expected, state_ret)
            )

        # make sure we wait until the earlier state is complete
        future = time.time() + 120
        while True:
            if expected not in ' '.join(self.run_function('state.running', wipe=False)):
                break
            if time.time() > future:
                self.fail('state.pkg is still running overtime. Test did not clean up correctly.')

    def tearDown(self):
        '''
        make sure to clean up any old ssh directories
        '''
        salt_dir = self.run_function('config.get', ['thin_dir'], wipe=False)
        self.assertIsInstance(salt_dir, six.string_types)
        if os.path.exists(salt_dir):
            shutil.rmtree(salt_dir)

        if os.path.exists(SSH_SLS_FILE):
            os.remove(SSH_SLS_FILE)
