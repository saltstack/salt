# -*- coding: utf-8 -*-
'''
Integration tests for the saltutil module.
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import os
import time
import textwrap
import threading
import shutil
import datetime

# Import Salt Testing libs
from tests.support.runtests import RUNTIME_VARS
from tests.support.case import ModuleCase
from tests.support.helpers import flaky
from tests.support.unit import skipIf

# Import Salt Libs
import salt.config
import salt.defaults.events
import salt.utils.event
import salt.utils.files
import salt.utils.stringutils
import salt.utils.files


class SaltUtilModuleTest(ModuleCase):
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


@skipIf(True, "WAR ROOM TEMPORARY SKIP")
class SaltUtilSyncModuleTest(ModuleCase):
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
                           'clouds': [],
                           'grains': [],
                           'beacons': [],
                           'utils': [],
                           'returners': [],
                           'modules': ['modules.mantest',
                                       'modules.override_test',
                                       'modules.runtests_decorators',
                                       'modules.runtests_helpers',
                                       'modules.salttest'],
                           'renderers': [],
                           'log_handlers': [],
                           'matchers': [],
                           'states': [],
                           'sdb': [],
                           'proxymodules': [],
                           'output': [],
                           'thorium': [],
                           'serializers': [],
                           'executors': []}
        ret = self.run_function('saltutil.sync_all')
        print(ret)
        self.assertEqual(ret, expected_return)

    def test_sync_all_whitelist(self):
        '''
        Test syncing all ModuleCase with whitelist
        '''
        expected_return = {'engines': [],
                           'clouds': [],
                           'grains': [],
                           'beacons': [],
                           'utils': [],
                           'returners': [],
                           'modules': ['modules.salttest'],
                           'renderers': [],
                           'log_handlers': [],
                           'matchers': [],
                           'states': [],
                           'sdb': [],
                           'proxymodules': [],
                           'output': [],
                           'thorium': [],
                           'serializers': [],
                           'executors': []}
        ret = self.run_function('saltutil.sync_all', extmod_whitelist={'modules': ['salttest']})
        self.assertEqual(ret, expected_return)

    def test_sync_all_blacklist(self):
        '''
        Test syncing all ModuleCase with blacklist
        '''
        expected_return = {'engines': [],
                           'clouds': [],
                           'grains': [],
                           'beacons': [],
                           'utils': [],
                           'returners': [],
                           'modules': ['modules.mantest',
                                       'modules.override_test',
                                       'modules.runtests_helpers',
                                       'modules.salttest'],
                           'renderers': [],
                           'log_handlers': [],
                           'matchers': [],
                           'states': [],
                           'sdb': [],
                           'proxymodules': [],
                           'output': [],
                           'thorium': [],
                           'serializers': [],
                           'executors': []}
        ret = self.run_function('saltutil.sync_all', extmod_blacklist={'modules': ['runtests_decorators']})
        self.assertEqual(ret, expected_return)

    def test_sync_all_blacklist_and_whitelist(self):
        '''
        Test syncing all ModuleCase with whitelist and blacklist
        '''
        expected_return = {'engines': [],
                           'clouds': [],
                           'grains': [],
                           'beacons': [],
                           'utils': [],
                           'returners': [],
                           'modules': [],
                           'renderers': [],
                           'log_handlers': [],
                           'matchers': [],
                           'states': [],
                           'sdb': [],
                           'proxymodules': [],
                           'output': [],
                           'thorium': [],
                           'serializers': [],
                           'executors': []}
        ret = self.run_function('saltutil.sync_all', extmod_whitelist={'modules': ['runtests_decorators']},
                                extmod_blacklist={'modules': ['runtests_decorators']})
        self.assertEqual(ret, expected_return)


@skipIf(True, 'Pillar refresh test is flaky. Skipping for now.')
class SaltUtilSyncPillarTest(ModuleCase):
    '''
    Testcase for the saltutil sync pillar module
    '''

    class WaitForEvent(threading.Thread):
        def __init__(self, opts, event_tag):
            self.__eventer = salt.utils.event.get_event(
                'minion', opts=opts, listen=True)
            self.__event_tag = event_tag
            self.__event_complete = False

            threading.Thread.__init__(self)

        def run(self):
            if self.__eventer.get_event(tag=self.__event_tag, wait=30):
                self.__event_complete = True

        def is_complete(self):
            return self.__event_complete

    @flaky
    def test_pillar_refresh(self):
        '''
        test pillar refresh module
        '''
        pillar_key = 'itworked'

        pre_pillar = self.run_function('pillar.raw')
        self.assertNotIn(pillar_key, pre_pillar.get(pillar_key, 'didnotwork'))

        with salt.utils.files.fopen(os.path.join(RUNTIME_VARS.TMP_PILLAR_TREE, 'add_pillar.sls'), 'w') as fp:
            fp.write(salt.utils.stringutils.to_str(
                '{0}: itworked'.format(pillar_key)
            ))

        with salt.utils.files.fopen(os.path.join(RUNTIME_VARS.TMP_PILLAR_TREE, 'top.sls'), 'w') as fp:
            fp.write(textwrap.dedent('''\
                     base:
                       '*':
                         - add_pillar
                     '''))

        self.run_function('saltutil.refresh_pillar')

        pillar = False
        timeout = time.time() + 30
        while not pillar:
            post_pillar = self.run_function('pillar.raw')
            try:
                self.assertIn(pillar_key, post_pillar.get(pillar_key, 'didnotwork'))
                pillar = True
            except AssertionError:
                if time.time() > timeout:
                    self.assertIn(pillar_key, post_pillar.get(pillar_key, 'didnotwork'))
                continue

        post_pillar = self.run_function('pillar.raw')
        self.assertIn(pillar_key, post_pillar.get(pillar_key, 'didnotwork'))

    def test_pillar_refresh_sync(self):
        '''
        test pillar refresh module with sync enabled
        '''
        pillar_key = 'itworked_sync'

        pre_pillar = self.run_function('pillar.raw')
        self.assertNotIn(pillar_key, pre_pillar.get(pillar_key, 'didnotwork_sync'))

        with salt.utils.files.fopen(os.path.join(RUNTIME_VARS.TMP_PILLAR_TREE, 'add_pillar_sync.sls'), 'w') as fp:
            fp.write(salt.utils.stringutils.to_str(
                '{0}: itworked_sync'.format(pillar_key)
            ))

        with salt.utils.files.fopen(os.path.join(RUNTIME_VARS.TMP_PILLAR_TREE, 'top.sls'), 'w') as fp:
            fp.write(textwrap.dedent('''\
                     base:
                       '*':
                         - add_pillar_sync
                     '''))

        opts = self.run_function('test.get_opts')
        wait = self.WaitForEvent(
            opts, salt.defaults.events.MINION_PILLAR_COMPLETE)
        wait.start()
        kwargs = {'async': False}
        self.run_function('saltutil.refresh_pillar', **kwargs)
        while wait.is_alive():
            time.sleep(1)
        self.assertTrue(wait.is_complete())

        pillar = False
        timeout = time.time() + 30
        while not pillar:
            post_pillar = self.run_function('pillar.raw')
            try:
                self.assertIn(pillar_key, post_pillar.get(
                    pillar_key, 'didnotwork_sync'))
                pillar = True
            except AssertionError:
                if time.time() > timeout:
                    self.assertIn(pillar_key, post_pillar.get(
                        pillar_key, 'didnotwork_sync'))
                continue

        post_pillar = self.run_function('pillar.raw')
        self.assertIn(pillar_key, post_pillar.get(
            pillar_key, 'didnotwork_sync'))

    def tearDown(self):
        for filename in os.listdir(RUNTIME_VARS.TMP_PILLAR_TREE):
            os.remove(os.path.join(RUNTIME_VARS.TMP_PILLAR_TREE, filename))


class SaltUtilClearCacheTest(ModuleCase):
    '''
    Testcase for the saltutil clear cache module
    '''
    def setUp(self):
        '''
        Creates a temporary directory for this test class
        '''
        self.tmp_dir = os.path.join(self.master_opts['cachedir'], 'SaltUtilClearCacheTest')
        os.makedirs(self.tmp_dir)

    def tearDown(self):
        '''
        Recursively deletes the temporary directory created for this test scenario
        '''
        shutil.rmtree(self.tmp_dir)

    def createDummyCachedFile(self, filename, mtime=time.time()):
        target_file = os.path.join(self.tmp_dir, filename)
        with salt.utils.files.fopen(target_file, 'a'):
            os.utime(target_file, (int(mtime), int(mtime)))
        return target_file

    def test_clear_cache_files_older_than_seven_days(self):
        old_file = self.createDummyCachedFile('old', time.time() - datetime.timedelta(days=10).total_seconds())
        new_file = self.createDummyCachedFile('new')
        self.run_function('saltutil.clear_cache', days=7)
        self.assertFalse(os.path.exists(old_file))
        self.assertTrue(os.path.exists(new_file))
