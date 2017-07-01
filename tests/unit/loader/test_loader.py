# -*- coding: utf-8 -*-
'''
    unit.loader
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Test Salt's loader
'''

# Import Python libs
from __future__ import absolute_import
import inspect
import logging
import tempfile
import shutil
import os
import collections
import sys
import imp
import copy

# Import Salt Testing libs
from tests.support.unit import TestCase
from tests.support.mock import patch
from tests.support.paths import TMP

# Import Salt libs
import salt.config
import salt.utils
# pylint: disable=import-error,no-name-in-module,redefined-builtin
import salt.ext.six as six
from salt.ext.six.moves import range
# pylint: enable=no-name-in-module,redefined-builtin

from salt.loader import LazyLoader, _module_dirs, grains, utils, proxy, minion_mods

log = logging.getLogger(__name__)


def remove_bytecode(module_path):
    paths = [module_path + 'c']
    if hasattr(imp, 'get_tag'):
        modname, ext = os.path.splitext(module_path.split(os.sep)[-1])
        paths.append(
            os.path.join(os.path.dirname(module_path),
                         '__pycache__',
                         '{}.{}.pyc'.format(modname, imp.get_tag())))
    for path in paths:
        if os.path.exists(path):
            os.unlink(path)


loader_template = '''
import os
from salt.utils.decorators import depends

@depends('os')
def loaded():
    return True

@depends('non_existantmodulename')
def not_loaded():
    return True
'''


class LazyLoaderTest(TestCase):
    '''
    Test the loader
    '''
    module_name = 'lazyloadertest'

    @classmethod
    def setUpClass(cls):
        cls.opts = salt.config.minion_config(None)
        cls.opts['grains'] = grains(cls.opts)
        if not os.path.isdir(TMP):
            os.makedirs(TMP)

    def setUp(self):
        # Setup the module
        self.module_dir = tempfile.mkdtemp(dir=TMP)
        self.module_file = os.path.join(self.module_dir,
                                        '{0}.py'.format(self.module_name))
        with salt.utils.fopen(self.module_file, 'w') as fh:
            fh.write(loader_template)
            fh.flush()
            os.fsync(fh.fileno())

        # Invoke the loader
        self.loader = LazyLoader([self.module_dir], copy.deepcopy(self.opts), tag='module')

    def tearDown(self):
        shutil.rmtree(self.module_dir)
        if os.path.isdir(self.module_dir):
            shutil.rmtree(self.module_dir)
        del self.module_dir
        del self.module_file
        del self.loader

    @classmethod
    def tearDownClass(cls):
        del cls.opts

    def test_depends(self):
        '''
        Test that the depends decorator works properly
        '''
        # Make sure depends correctly allowed a function to load. If this
        # results in a KeyError, the decorator is broken.
        self.assertTrue(
            inspect.isfunction(
                self.loader[self.module_name + '.loaded']
            )
        )
        # Make sure depends correctly kept a function from loading
        self.assertTrue(self.module_name + '.not_loaded' not in self.loader)


class LazyLoaderVirtualEnabledTest(TestCase):
    '''
    Test the base loader of salt.
    '''
    @classmethod
    def setUpClass(cls):
        cls.opts = salt.config.minion_config(None)
        cls.opts['disable_modules'] = ['pillar']
        cls.opts['grains'] = grains(cls.opts)

    def setUp(self):
        self.loader = LazyLoader(_module_dirs(copy.deepcopy(self.opts), 'modules', 'module'),
                                 copy.deepcopy(self.opts),
                                 tag='module')

    def tearDown(self):
        del self.loader

    @classmethod
    def tearDownClass(cls):
        del cls.opts

    def test_basic(self):
        '''
        Ensure that it only loads stuff when needed
        '''
        # make sure it starts empty
        self.assertEqual(self.loader._dict, {})
        # get something, and make sure its a func
        self.assertTrue(inspect.isfunction(self.loader['test.ping']))

        # make sure we only loaded "test" functions
        for key, val in six.iteritems(self.loader._dict):
            self.assertEqual(key.split('.', 1)[0], 'test')

        # make sure the depends thing worked (double check of the depends testing,
        # since the loader does the calling magically
        self.assertFalse('test.missing_func' in self.loader._dict)

    def test_badkey(self):
        with self.assertRaises(KeyError):
            self.loader[None]  # pylint: disable=W0104

        with self.assertRaises(KeyError):
            self.loader[1]  # pylint: disable=W0104

    def test_disable(self):
        self.assertNotIn('pillar.items', self.loader)

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
        for key, func in six.iteritems(self.loader):
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
        with patch.dict(func.__globals__['__context__'], {'foo': 'bar'}):
            self.assertEqual(self.loader['test.echo'].__globals__['__context__']['foo'], 'bar')
            self.assertEqual(self.loader['grains.get'].__globals__['__context__']['foo'], 'bar')

    def test_globals(self):
        func_globals = self.loader['test.ping'].__globals__
        self.assertEqual(func_globals['__grains__'], self.opts.get('grains', {}))
        self.assertEqual(func_globals['__pillar__'], self.opts.get('pillar', {}))
        # the opts passed into modules is at least a subset of the whole opts
        for key, val in six.iteritems(func_globals['__opts__']):
            if key in salt.config.DEFAULT_MASTER_OPTS and key not in salt.config.DEFAULT_MINION_OPTS:
                # We loaded the minion opts, but somewhere in the code, the master options got pulled in
                # Let's just not check for equality since the option won't even exist in the loaded
                # minion options
                continue
            if key not in salt.config.DEFAULT_MASTER_OPTS and key not in salt.config.DEFAULT_MINION_OPTS:
                # This isn't even a default configuration setting, lets carry on
                continue
            self.assertEqual(self.opts[key], val)

    def test_pack(self):
        self.loader.pack['__foo__'] = 'bar'
        func_globals = self.loader['test.ping'].__globals__
        self.assertEqual(func_globals['__foo__'], 'bar')

    def test_virtual(self):
        self.assertNotIn('test_virtual.ping', self.loader)


class LazyLoaderVirtualDisabledTest(TestCase):
    '''
    Test the loader of salt without __virtual__
    '''
    @classmethod
    def setUpClass(cls):
        cls.opts = salt.config.minion_config(None)
        cls.opts['grains'] = grains(cls.opts)

    def setUp(self):
        self.loader = LazyLoader(_module_dirs(copy.deepcopy(self.opts), 'modules', 'module'),
                                 copy.deepcopy(self.opts),
                                 tag='module',
                                 virtual_enable=False)

    def tearDown(self):
        del self.loader

    @classmethod
    def tearDownClass(cls):
        del cls.opts

    def test_virtual(self):
        self.assertTrue(inspect.isfunction(self.loader['test_virtual.ping']))


class LazyLoaderWhitelistTest(TestCase):
    '''
    Test the loader of salt with a whitelist
    '''
    @classmethod
    def setUpClass(cls):
        cls.opts = salt.config.minion_config(None)
        cls.opts['grains'] = grains(cls.opts)

    def setUp(self):
        self.loader = LazyLoader(_module_dirs(copy.deepcopy(self.opts), 'modules', 'module'),
                                 copy.deepcopy(self.opts),
                                 tag='module',
                                 whitelist=['test', 'pillar'])

    def tearDown(self):
        del self.loader

    @classmethod
    def tearDownClass(cls):
        del cls.opts

    def test_whitelist(self):
        self.assertTrue(inspect.isfunction(self.loader['test.ping']))
        self.assertTrue(inspect.isfunction(self.loader['pillar.get']))

        self.assertNotIn('grains.get', self.loader)


module_template = '''
__load__ = ['test', 'test_alias']
__func_alias__ = dict(test_alias='working_alias')
from salt.utils.decorators import depends

def test():
    return {count}

def test_alias():
    return True

def test2():
    return True

@depends('non_existantmodulename')
def test3():
    return True

@depends('non_existantmodulename', fallback_function=test)
def test4():
    return True
'''


class LazyLoaderReloadingTest(TestCase):
    '''
    Test the loader of salt with changing modules
    '''
    module_name = 'loadertest'
    module_key = 'loadertest.test'

    @classmethod
    def setUpClass(cls):
        cls.opts = salt.config.minion_config(None)
        cls.opts['grains'] = grains(cls.opts)
        if not os.path.isdir(TMP):
            os.makedirs(TMP)

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(dir=TMP)

        self.count = 0
        opts = copy.deepcopy(self.opts)
        dirs = _module_dirs(opts, 'modules', 'module')
        dirs.append(self.tmp_dir)
        self.utils = utils(opts)
        self.proxy = proxy(opts)
        self.minion_mods = minion_mods(opts)
        self.loader = LazyLoader(dirs,
                                 opts,
                                 tag='module',
                                 pack={'__utils__': self.utils,
                                       '__proxy__': self.proxy,
                                       '__salt__': self.minion_mods})

    def tearDown(self):
        shutil.rmtree(self.tmp_dir)
        for attrname in ('tmp_dir', 'utils', 'proxy', 'loader', 'minion_mods', 'utils'):
            try:
                delattr(self, attrname)
            except AttributeError:
                continue

    @classmethod
    def tearDownClass(cls):
        del cls.opts

    def update_module(self):
        self.count += 1
        with salt.utils.fopen(self.module_path, 'wb') as fh:
            fh.write(
                salt.utils.to_bytes(
                    module_template.format(count=self.count)
                )
            )
            fh.flush()
            os.fsync(fh.fileno())  # flush to disk

        # pyc files don't like it when we change the original quickly
        # since the header bytes only contain the timestamp (granularity of seconds)
        # TODO: don't write them? Is *much* slower on re-load (~3x)
        # https://docs.python.org/2/library/sys.html#sys.dont_write_bytecode
        remove_bytecode(self.module_path)

    def rm_module(self):
        os.unlink(self.module_path)
        remove_bytecode(self.module_path)

    @property
    def module_path(self):
        return os.path.join(self.tmp_dir, '{0}.py'.format(self.module_name))

    def test_alias(self):
        '''
        Make sure that you can access alias-d modules
        '''
        # ensure it doesn't exist
        self.assertNotIn(self.module_key, self.loader)

        self.update_module()
        self.assertNotIn('{0}.test_alias'.format(self.module_name), self.loader)
        self.assertTrue(inspect.isfunction(self.loader['{0}.working_alias'.format(self.module_name)]))

    def test_clear(self):
        self.assertTrue(inspect.isfunction(self.loader['test.ping']))
        self.update_module()  # write out out custom module
        self.loader.clear()  # clear the loader dict

        # force a load of our module
        self.assertTrue(inspect.isfunction(self.loader[self.module_key]))

        # make sure we only loaded our custom module
        # which means that we did correctly refresh the file mapping
        for k, v in six.iteritems(self.loader._dict):
            self.assertTrue(k.startswith(self.module_name))

    def test_load(self):
        # ensure it doesn't exist
        self.assertNotIn(self.module_key, self.loader)

        self.update_module()
        self.assertTrue(inspect.isfunction(self.loader[self.module_key]))

    def test__load__(self):
        '''
        If a module specifies __load__ we should only load/expose those modules
        '''
        self.update_module()

        # ensure it doesn't exist
        self.assertNotIn(self.module_key + '2', self.loader)

    def test__load__and_depends(self):
        '''
        If a module specifies __load__ we should only load/expose those modules
        '''
        self.update_module()
        # ensure it doesn't exist
        self.assertNotIn(self.module_key + '3', self.loader)
        self.assertNotIn(self.module_key + '4', self.loader)

    def test_reload(self):
        # ensure it doesn't exist
        self.assertNotIn(self.module_key, self.loader)

        # make sure it updates correctly
        for x in range(1, 3):
            self.update_module()
            self.loader.clear()
            self.assertEqual(self.loader[self.module_key](), self.count)

        self.rm_module()
        # make sure that even if we remove the module, its still loaded until a clear
        self.assertEqual(self.loader[self.module_key](), self.count)
        self.loader.clear()
        self.assertNotIn(self.module_key, self.loader)


virtual_aliases = ('loadertest2', 'loadertest3')
virtual_alias_module_template = '''
__virtual_aliases__ = {0}

def test():
    return True
'''.format(virtual_aliases)


class LazyLoaderVirtualAliasTest(TestCase):
    '''
    Test the loader of salt with changing modules
    '''
    module_name = 'loadertest'

    @classmethod
    def setUpClass(cls):
        cls.opts = salt.config.minion_config(None)
        cls.opts['grains'] = grains(cls.opts)
        if not os.path.isdir(TMP):
            os.makedirs(TMP)

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(dir=TMP)
        opts = copy.deepcopy(self.opts)
        dirs = _module_dirs(opts, 'modules', 'module')
        dirs.append(self.tmp_dir)
        self.utils = utils(opts)
        self.proxy = proxy(opts)
        self.minion_mods = minion_mods(opts)
        self.loader = LazyLoader(dirs,
                                 opts,
                                 tag='module',
                                 pack={'__utils__': self.utils,
                                       '__proxy__': self.proxy,
                                       '__salt__': self.minion_mods})

    def tearDown(self):
        del self.tmp_dir
        del self.utils
        del self.proxy
        del self.minion_mods
        del self.loader

    @classmethod
    def tearDownClass(cls):
        del cls.opts

    def update_module(self):
        with salt.utils.fopen(self.module_path, 'wb') as fh:
            fh.write(salt.utils.to_bytes(virtual_alias_module_template))
            fh.flush()
            os.fsync(fh.fileno())  # flush to disk

        # pyc files don't like it when we change the original quickly
        # since the header bytes only contain the timestamp (granularity of seconds)
        # TODO: don't write them? Is *much* slower on re-load (~3x)
        # https://docs.python.org/2/library/sys.html#sys.dont_write_bytecode
        remove_bytecode(self.module_path)

    @property
    def module_path(self):
        return os.path.join(self.tmp_dir, '{0}.py'.format(self.module_name))

    def test_virtual_alias(self):
        '''
        Test the __virtual_alias__ feature
        '''
        self.update_module()

        mod_names = [self.module_name] + list(virtual_aliases)
        for mod_name in mod_names:
            func_name = '.'.join((mod_name, 'test'))
            log.debug('Running %s (dict attribute)', func_name)
            self.assertTrue(self.loader[func_name]())
            log.debug('Running %s (loader attribute)', func_name)
            self.assertTrue(getattr(self.loader, mod_name).test())


submodule_template = '''
from __future__ import absolute_import

import {0}.lib

def test():
    return ({count}, {0}.lib.test())
'''

submodule_lib_template = '''
def test():
    return {count}
'''


class LazyLoaderSubmodReloadingTest(TestCase):
    '''
    Test the loader of salt with changing modules
    '''
    module_name = 'loadertestsubmod'
    module_key = 'loadertestsubmod.test'

    @classmethod
    def setUpClass(cls):
        cls.opts = salt.config.minion_config(None)
        cls.opts['grains'] = grains(cls.opts)
        if not os.path.isdir(TMP):
            os.makedirs(TMP)

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(dir=TMP)
        os.makedirs(self.module_dir)

        self.count = 0
        self.lib_count = 0

        opts = copy.deepcopy(self.opts)
        dirs = _module_dirs(opts, 'modules', 'module')
        dirs.append(self.tmp_dir)
        self.utils = utils(opts)
        self.proxy = proxy(opts)
        self.minion_mods = minion_mods(opts)
        self.loader = LazyLoader(dirs,
                                 opts,
                                 tag='module',
                                 pack={'__utils__': self.utils,
                                       '__proxy__': self.proxy,
                                       '__salt__': self.minion_mods}
                                 )

    def tearDown(self):
        shutil.rmtree(self.tmp_dir)
        del self.tmp_dir
        del self.utils
        del self.proxy
        del self.minion_mods
        del self.loader

    @classmethod
    def tearDownClass(cls):
        del cls.opts

    def update_module(self):
        self.count += 1
        with salt.utils.fopen(self.module_path, 'wb') as fh:
            fh.write(
                salt.utils.to_bytes(
                    submodule_template.format(self.module_name, count=self.count)
                )
            )
            fh.flush()
            os.fsync(fh.fileno())  # flush to disk

        # pyc files don't like it when we change the original quickly
        # since the header bytes only contain the timestamp (granularity of seconds)
        # TODO: don't write them? Is *much* slower on re-load (~3x)
        # https://docs.python.org/2/library/sys.html#sys.dont_write_bytecode
        remove_bytecode(self.module_path)

    def rm_module(self):
        os.unlink(self.module_path)
        remove_bytecode(self.module_path)

    def update_lib(self):
        self.lib_count += 1
        for modname in list(sys.modules):
            if modname.startswith(self.module_name):
                del sys.modules[modname]
        with salt.utils.fopen(self.lib_path, 'wb') as fh:
            fh.write(
                salt.utils.to_bytes(
                    submodule_lib_template.format(count=self.lib_count)
                )
            )
            fh.flush()
            os.fsync(fh.fileno())  # flush to disk

        # pyc files don't like it when we change the original quickly
        # since the header bytes only contain the timestamp (granularity of seconds)
        # TODO: don't write them? Is *much* slower on re-load (~3x)
        # https://docs.python.org/2/library/sys.html#sys.dont_write_bytecode
        remove_bytecode(self.lib_path)

    def rm_lib(self):
        for modname in list(sys.modules):
            if modname.startswith(self.module_name):
                del sys.modules[modname]
        os.unlink(self.lib_path)
        remove_bytecode(self.lib_path)

    @property
    def module_dir(self):
        return os.path.join(self.tmp_dir, self.module_name)

    @property
    def module_path(self):
        return os.path.join(self.module_dir, '__init__.py')

    @property
    def lib_path(self):
        return os.path.join(self.module_dir, 'lib.py')

    def test_basic(self):
        # ensure it doesn't exist
        self.assertNotIn(self.module_key, self.loader)

        self.update_module()
        self.update_lib()
        self.loader.clear()
        self.assertIn(self.module_key, self.loader)

    def test_reload(self):
        # ensure it doesn't exist
        self.assertNotIn(self.module_key, self.loader)

        # update both the module and the lib
        for x in range(1, 3):
            self.update_lib()
            self.update_module()
            self.loader.clear()
            self.assertNotIn(self.module_key, self.loader._dict)
            self.assertIn(self.module_key, self.loader)
            self.assertEqual(self.loader[self.module_key](), (self.count, self.lib_count))

        # update just the module
        for x in range(1, 3):
            self.update_module()
            self.loader.clear()
            self.assertNotIn(self.module_key, self.loader._dict)
            self.assertIn(self.module_key, self.loader)
            self.assertEqual(self.loader[self.module_key](), (self.count, self.lib_count))

        # update just the lib
        for x in range(1, 3):
            self.update_lib()
            self.loader.clear()
            self.assertNotIn(self.module_key, self.loader._dict)
            self.assertIn(self.module_key, self.loader)
            self.assertEqual(self.loader[self.module_key](), (self.count, self.lib_count))

        self.rm_module()
        # make sure that even if we remove the module, its still loaded until a clear
        self.assertEqual(self.loader[self.module_key](), (self.count, self.lib_count))
        self.loader.clear()
        self.assertNotIn(self.module_key, self.loader)

    def test_reload_missing_lib(self):
        # ensure it doesn't exist
        self.assertNotIn(self.module_key, self.loader)

        # update both the module and the lib
        self.update_module()
        self.update_lib()
        self.loader.clear()
        self.assertEqual(self.loader[self.module_key](), (self.count, self.lib_count))

        # remove the lib, this means we should fail to load the module next time
        self.rm_lib()
        self.loader.clear()
        self.assertNotIn(self.module_key, self.loader)


mod_template = '''
def test():
    return ({val})
'''


class LazyLoaderModulePackageTest(TestCase):
    '''
    Test the loader of salt with changing modules
    '''
    module_name = 'loadertestmodpkg'
    module_key = 'loadertestmodpkg.test'

    @classmethod
    def setUpClass(cls):
        cls.opts = salt.config.minion_config(None)
        cls.opts['grains'] = grains(cls.opts)
        if not os.path.isdir(TMP):
            os.makedirs(TMP)

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(dir=TMP)

        dirs = _module_dirs(copy.deepcopy(self.opts), 'modules', 'module')
        dirs.append(self.tmp_dir)
        self.loader = LazyLoader(dirs,
                                 copy.deepcopy(self.opts),
                                 tag='module')

    def tearDown(self):
        shutil.rmtree(self.tmp_dir)
        del self.tmp_dir
        del self.loader

    @classmethod
    def tearDownClass(cls):
        del cls.opts

    def update_pyfile(self, pyfile, contents):
        dirname = os.path.dirname(pyfile)
        if not os.path.exists(dirname):
            os.makedirs(dirname)
        with salt.utils.fopen(pyfile, 'wb') as fh:
            fh.write(salt.utils.to_bytes(contents))
            fh.flush()
            os.fsync(fh.fileno())  # flush to disk

        # pyc files don't like it when we change the original quickly
        # since the header bytes only contain the timestamp (granularity of seconds)
        # TODO: don't write them? Is *much* slower on re-load (~3x)
        # https://docs.python.org/2/library/sys.html#sys.dont_write_bytecode
        remove_bytecode(pyfile)

    def rm_pyfile(self, pyfile):
        os.unlink(pyfile)
        remove_bytecode(pyfile)

    def update_module(self, relative_path, contents):
        self.update_pyfile(os.path.join(self.tmp_dir, relative_path), contents)

    def rm_module(self, relative_path):
        self.rm_pyfile(os.path.join(self.tmp_dir, relative_path))

    def test_module(self):
        # ensure it doesn't exist
        self.assertNotIn('foo', self.loader)
        self.assertNotIn('foo.test', self.loader)
        self.update_module('foo.py', mod_template.format(val=1))
        self.loader.clear()
        self.assertIn('foo.test', self.loader)
        self.assertEqual(self.loader['foo.test'](), 1)

    def test_package(self):
        # ensure it doesn't exist
        self.assertNotIn('foo', self.loader)
        self.assertNotIn('foo.test', self.loader)
        self.update_module('foo/__init__.py', mod_template.format(val=2))
        self.loader.clear()
        self.assertIn('foo.test', self.loader)
        self.assertEqual(self.loader['foo.test'](), 2)

    def test_module_package_collision(self):
        # ensure it doesn't exist
        self.assertNotIn('foo', self.loader)
        self.assertNotIn('foo.test', self.loader)
        self.update_module('foo.py', mod_template.format(val=3))
        self.loader.clear()
        self.assertIn('foo.test', self.loader)
        self.assertEqual(self.loader['foo.test'](), 3)

        self.update_module('foo/__init__.py', mod_template.format(val=4))
        self.loader.clear()
        self.assertIn('foo.test', self.loader)
        self.assertEqual(self.loader['foo.test'](), 4)


deep_init_base = '''
from __future__ import absolute_import
import {0}.top_lib
import {0}.top_lib.mid_lib
import {0}.top_lib.mid_lib.bot_lib

def top():
    return {0}.top_lib.test()

def mid():
    return {0}.top_lib.mid_lib.test()

def bot():
    return {0}.top_lib.mid_lib.bot_lib.test()
'''


class LazyLoaderDeepSubmodReloadingTest(TestCase):
    module_name = 'loadertestsubmoddeep'
    libs = ('top_lib', 'mid_lib', 'bot_lib')

    @classmethod
    def setUpClass(cls):
        cls.opts = salt.config.minion_config(None)
        cls.opts['grains'] = grains(cls.opts)
        if not os.path.isdir(TMP):
            os.makedirs(TMP)

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(dir=TMP)
        os.makedirs(self.module_dir)

        self.lib_count = collections.defaultdict(int)  # mapping of path -> count

        # bootstrap libs
        with salt.utils.fopen(os.path.join(self.module_dir, '__init__.py'), 'w') as fh:
            # No .decode() needed here as deep_init_base is defined as str and
            # not bytes.
            fh.write(deep_init_base.format(self.module_name))
            fh.flush()
            os.fsync(fh.fileno())  # flush to disk

        self.lib_paths = {}
        dir_path = self.module_dir
        for lib_name in self.libs:
            dir_path = os.path.join(dir_path, lib_name)
            self.lib_paths[lib_name] = dir_path
            os.makedirs(dir_path)
            self.update_lib(lib_name)

        opts = copy.deepcopy(self.opts)
        dirs = _module_dirs(opts, 'modules', 'module')
        dirs.append(self.tmp_dir)
        self.utils = utils(opts)
        self.proxy = proxy(opts)
        self.minion_mods = minion_mods(opts)
        self.loader = LazyLoader(dirs,
                                 copy.deepcopy(opts),
                                 tag='module',
                                 pack={'__utils__': self.utils,
                                       '__proxy__': self.proxy,
                                       '__salt__': self.minion_mods}
                                 )
        self.assertIn('{0}.top'.format(self.module_name), self.loader)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir)
        del self.tmp_dir
        del self.lib_paths
        del self.utils
        del self.proxy
        del self.minion_mods
        del self.loader
        del self.lib_count

    @classmethod
    def tearDownClass(cls):
        del cls.opts

    @property
    def module_dir(self):
        return os.path.join(self.tmp_dir, self.module_name)

    def update_lib(self, lib_name):
        for modname in list(sys.modules):
            if modname.startswith(self.module_name):
                del sys.modules[modname]
        path = os.path.join(self.lib_paths[lib_name], '__init__.py')
        self.lib_count[lib_name] += 1
        with salt.utils.fopen(path, 'wb') as fh:
            fh.write(
                salt.utils.to_bytes(
                    submodule_lib_template.format(count=self.lib_count[lib_name])
                )
            )
            fh.flush()
            os.fsync(fh.fileno())  # flush to disk

        # pyc files don't like it when we change the original quickly
        # since the header bytes only contain the timestamp (granularity of seconds)
        # TODO: don't write them? Is *much* slower on re-load (~3x)
        # https://docs.python.org/2/library/sys.html#sys.dont_write_bytecode
        remove_bytecode(path)

    def test_basic(self):
        self.assertIn('{0}.top'.format(self.module_name), self.loader)

    def _verify_libs(self):
        for lib in self.libs:
            self.assertEqual(self.loader['{0}.{1}'.format(self.module_name, lib.replace('_lib', ''))](),
                             self.lib_count[lib])

    def test_reload(self):
        '''
        Make sure that we can reload all libraries of arbitrary depth
        '''
        self._verify_libs()

        # update them all
        for lib in self.libs:
            for x in range(5):
                self.update_lib(lib)
                self.loader.clear()
                self._verify_libs()
