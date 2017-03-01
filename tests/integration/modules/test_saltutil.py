# -*- coding: utf-8 -*-
'''
Integration tests for the saltutil module.
'''

# Import Python libs
from __future__ import absolute_import
import time

# Import Salt Testing libs
import tests.integration as integration


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


class SaltUtilSyncModuleTest(integration.ModuleCase):
    '''
    Testcase for the saltutil sync execution module
    '''

    def setUp(self):
        whitelist = {'modules': [], }
        self.run_function('saltutil.sync_all', extmod_whitelist=whitelist)

    def tearDown(self):
        self.run_function('saltutil.sync_all')

    def test_sync_all(self):
        '''
        Test syncing all ModuleCase
        '''
        expected_return = {'engines': [],
                           'grains': [],
                           'beacons': [],
                           'utils': [],
                           'returners': [],
                           'modules': ['modules.override_test',
                                       'modules.runtests_decorators',
                                       'modules.runtests_helpers',
                                       'modules.salttest'],
                           'renderers': [],
                           'log_handlers': [],
                           'states': [],
                           'sdb': [],
                           'proxymodules': [],
                           'output': []}
        ret = self.run_function('saltutil.sync_all')
        self.assertEqual(ret, expected_return)

    def test_sync_all_whitelist(self):
        '''
        Test syncing all ModuleCase with whitelist
        '''
        expected_return = {'engines': [],
                           'grains': [],
                           'beacons': [],
                           'utils': [],
                           'returners': [],
                           'modules': ['modules.salttest'],
                           'renderers': [],
                           'log_handlers': [],
                           'states': [],
                           'sdb': [],
                           'proxymodules': [],
                           'output': []}
        ret = self.run_function('saltutil.sync_all', extmod_whitelist={'modules': ['salttest']})
        self.assertEqual(ret, expected_return)

    def test_sync_all_blacklist(self):
        '''
        Test syncing all ModuleCase with blacklist
        '''
        expected_return = {'engines': [],
                           'grains': [],
                           'beacons': [],
                           'utils': [],
                           'returners': [],
                           'modules': ['modules.override_test',
                                       'modules.runtests_helpers',
                                       'modules.salttest'],
                           'renderers': [],
                           'log_handlers': [],
                           'states': [],
                           'sdb': [],
                           'proxymodules': [],
                           'output': []}
        ret = self.run_function('saltutil.sync_all', extmod_blacklist={'modules': ['runtests_decorators']})
        self.assertEqual(ret, expected_return)

    def test_sync_all_blacklist_and_whitelist(self):
        '''
        Test syncing all ModuleCase with whitelist and blacklist
        '''
        expected_return = {'engines': [],
                           'grains': [],
                           'beacons': [],
                           'utils': [],
                           'returners': [],
                           'modules': [],
                           'renderers': [],
                           'log_handlers': [],
                           'states': [],
                           'sdb': [],
                           'proxymodules': [],
                           'output': []}
        ret = self.run_function('saltutil.sync_all', extmod_whitelist={'modules': ['runtests_decorators']},
                                extmod_blacklist={'modules': ['runtests_decorators']})
        self.assertEqual(ret, expected_return)
