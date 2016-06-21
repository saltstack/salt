# -*- coding: utf-8 -*-
'''
Integration tests for the saltutil module.
'''

# Import Python libs
from __future__ import absolute_import
import time

# Import Salt Testing libs
from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')

# Import Salt libs
import integration


class SaltUtilModuleTest(integration.ModuleCase):
    '''
    Testcase for the saltutil execution module
    '''

    # Tests for the wheel function

    def test_wheel_just_function(self):
        '''
        Tests using the saltutil.wheel function when passing only a function.
        '''
        ret = self.run_function('saltutil.wheel', ['minions.connected'])
        self.assertEqual(ret, ['minion', 'sub_minion'])

    def test_wheel_with_arg(self):
        '''
        Tests using the saltutil.wheel function when passing a function and an arg.
        '''
        ret = self.run_function('saltutil.wheel', ['key.list', 'minion'])
        self.assertEqual(ret, {})

    def test_wheel_no_arg_raise_error(self):
        '''
        Tests using the saltutil.wheel function when passing a function that requires
        an arg, but one isn't supplied.
        '''
        self.assertRaises(TypeError, 'saltutil.wheel', ['key.list'])

    def test_wheel_with_kwarg(self):
        '''
        Tests using the saltutil.wheel function when passing a function and a kwarg.
        This function just generates a key pair, but doesn't do anything with it. We
        just need this for testing purposes.
        '''
        ret = self.run_function('saltutil.wheel', ['key.gen'], keysize=1024)
        self.assertIn('pub', ret)
        self.assertIn('priv', ret)

    def test_kill_job(self):
        '''
        Test to ensure that a long-running job can be killed.
        '''
        # Run job as async
        job_jid = self.run_function('test.sleep', arg=['30'], async=True)
        # Allow for a little time so we don't race the pub
        time.sleep(1) 
        # Execute runner to get job status
        job_status = self.run_function('saltutil.find_job', arg=[job_jid])
        # TODO migrate to assertDictContainsSubset once 2.6 is gone
        self.assertIn('jid', job_status)
        # Kill the job
        job_kill_ret = self.run_function('saltutil.kill_job', arg=[job_jid])
        time.sleep(1)
        # Check again to see if the job is running. It should be gone
        job_kill_status = self.run_function('saltutil.find_job', arg=[job_jid])
        self.assertEqual({}, job_kill_status)

if __name__ == '__main__':
    from integration import run_tests
    run_tests(SaltUtilModuleTest)
