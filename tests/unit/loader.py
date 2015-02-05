# -*- coding: utf-8 -*-
'''
    unit.loader
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Test Salt's loader
'''

# Import Python libs
from __future__ import absolute_import
import inspect
import tempfile
import shutil
import os.path
import os

# Import Salt Testing libs
from salttesting import TestCase
from salttesting.helpers import ensure_in_syspath

import integration

ensure_in_syspath('../..')

# Import Salt libs
from salt.config import minion_config

from salt.loader import LazyLoader, _module_dirs


class LazyLoaderVirtualEnabledTest(TestCase):
    '''
    Test the base loader of salt.
    '''
    def setUp(self):
        self.opts = _config = minion_config(None)
        self.loader = LazyLoader(_module_dirs(self.opts, 'modules', 'module'),
                         self.opts,
                         tag='modules',
                         )
    def test_basic(self):
        '''
        Ensure that it only loads stuff when needed
        '''
        # make sure it starts empty
        self.assertEqual(self.loader._dict, {})
        # get something, and make sure its a func
        self.assertTrue(inspect.isfunction(self.loader['test.ping']))

        # make sure we only loaded "test" functions
        for key, val in self.loader._dict.iteritems():
            self.assertEqual(key.split('.', 1)[0], 'test')

        # make sure the depends thing worked (double check of the depends testing,
        # since the loader does the calling magically
        self.assertFalse('test.missing_func' in self.loader._dict)

    def test_len_load(self):
        '''
        Since LazyLoader is a MutableMapping, if someone asks for len() we have
        to load all
        '''
        self.assertEqual(self.loader._dict, {})
        len(self.loader)  # force a load all
        self.assertNotEqual(self.loader._dict, {})

    def test_iter_load(self):
        '''
        Since LazyLoader is a MutableMapping, if someone asks to iterate we have
        to load all
        '''
        self.assertEqual(self.loader._dict, {})
        # force a load all
        for key, func in self.loader.iteritems():
            break
        self.assertNotEqual(self.loader._dict, {})

    def test_context(self):
        '''
        Make sure context is shared across modules
        '''
        # make sure it starts empty
        self.assertEqual(self.loader._dict, {})
        # get something, and make sure its a func
        func = self.loader['test.ping']
        func.__globals__['__context__']['foo'] = 'bar'
        self.assertEqual(self.loader['test.echo'].__globals__['__context__']['foo'], 'bar')
        self.assertEqual(self.loader['grains.get'].__globals__['__context__']['foo'], 'bar')

    def test_globals(self):
        func_globals = self.loader['test.ping'].__globals__
        self.assertEqual(func_globals['__grains__'], self.opts.get('grains', {}))
        self.assertEqual(func_globals['__pillar__'], self.opts.get('pillar', {}))
        # the opts passed into modules is at least a subset of the whole opts
        for key, val in func_globals['__opts__'].iteritems():
            self.assertEqual(self.opts[key], val)

    def test_pack(self):
        self.loader.pack['__foo__'] = 'bar'
        func_globals = self.loader['test.ping'].__globals__
        self.assertEqual(func_globals['__foo__'], 'bar')

    def test_virtual(self):
        with self.assertRaises(KeyError):
            self.loader['test_virtual.ping']


class LazyLoaderVirtualDisabledTest(TestCase):
    '''
    Test the loader of salt without __virtual__
    '''
    def setUp(self):
        self.opts = _config = minion_config(None)
        self.loader = LazyLoader(_module_dirs(self.opts, 'modules', 'module'),
                         self.opts,
                         tag='modules',
                         virtual_enable=False,
                         )
    def test_virtual(self):
        self.assertTrue(inspect.isfunction(self.loader['test_virtual.ping']))


class LazyLoaderWhitelistTest(TestCase):
    '''
    Test the loader of salt with a whitelist
    '''
    def setUp(self):
        self.opts = _config = minion_config(None)
        self.loader = LazyLoader(_module_dirs(self.opts, 'modules', 'module'),
                         self.opts,
                         tag='modules',
                         whitelist=['test', 'pillar']
                         )
    def test_whitelist(self):
        self.assertTrue(inspect.isfunction(self.loader['test.ping']))
        self.assertTrue(inspect.isfunction(self.loader['pillar.get']))

        with self.assertRaises(KeyError):
            self.loader['grains.get']

module_template = '''
test_module = True
def test():
    return {count}
'''


class LazyLoaderReloadingTest(TestCase):
    '''
    Test the loader of salt with changing modules
    '''
    module_name = 'loadertest'
    module_key = 'loadertest.test'
    def setUp(self):
        self.opts = _config = minion_config(None)
        self.tmp_dir = tempfile.mkdtemp(dir=integration.TMP)

        self.count = 0

        dirs = _module_dirs(self.opts, 'modules', 'module')
        dirs.append(self.tmp_dir)
        self.loader = LazyLoader(dirs,
                         self.opts,
                         tag='modules',
                         )

    def tearDown(self):
        shutil.rmtree(self.tmp_dir)

    def update_module(self):
        self.count += 1
        with open(self.module_path, 'wb') as fh:
            fh.write(module_template.format(count=self.count))
            fh.flush()
            os.fsync(fh.fileno())  # flush to disk

        # pyc files don't like it when we change the original quickly
        # TODO: don't write them?
        # https://docs.python.org/2/library/sys.html#sys.dont_write_bytecode
        try:
            os.unlink(self.module_path + 'c')
        except OSError:
            pass

    def rm_module(self):
        os.unlink(self.module_path)

    @property
    def module_path(self):
        return os.path.join(self.tmp_dir, '{0}.py'.format(self.module_name))

    def test_load(self):
        # ensure it doesn't exist
        with self.assertRaises(KeyError):
            self.loader[self.module_key]

        self.update_module()
        self.assertTrue(inspect.isfunction(self.loader[self.module_key]))

    def test_reload(self):
        # ensure it doesn't exist
        with self.assertRaises(KeyError):
            self.loader[self.module_key]

        # make sure it updates correctly
        for x in xrange(1, 3):
            self.update_module()
            self.loader.clear()
            self.assertEqual(self.loader[self.module_key](), self.count)

        self.rm_module()
        # make sure that even if we remove the module, its still loaded until a clear
        self.assertEqual(self.loader[self.module_key](), self.count)
        self.loader.clear()
        with self.assertRaises(KeyError):
            self.loader[self.module_key]
