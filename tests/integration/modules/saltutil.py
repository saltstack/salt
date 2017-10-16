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

    def setUp(self):
        self.run_function('saltutil.refresh_pillar')

    # Tests for the wheel function

    def test_wheel_just_function(self):
        '''
        Tests using the saltutil.wheel function when passing only a function.
        '''
        # Wait for the pillar refresh to kick in, so that grains are ready to go
        time.sleep(3)
        ret = self.run_function('saltutil.wheel', ['minions.connected'])
        self.assertIn('minion', ret['return'])
        self.assertIn('sub_minion', ret['return'])

    def test_wheel_with_arg(self):
        '''
        Tests using the saltutil.wheel function when passing a function and an arg.
        '''
        ret = self.run_function('saltutil.wheel', ['key.list', 'minion'])
        self.assertEqual(ret['return'], {})

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
        self.assertIn('pub', ret['return'])
        self.assertIn('priv', ret['return'])


if __name__ == '__main__':
    from integration import run_tests
    run_tests(SaltUtilModuleTest)
