# -*- coding: utf-8 -*-
'''
    tests.unit.test_module_virtual_returns
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
'''

# Import Python libs
from __future__ import absolute_import
import os
import imp
import sys
from contextlib import contextmanager

# Import 3rd-party libs
import salt.ext.six as six

# Import Salt Testing libs
from tests.support.unit import TestCase, skipIf
from tests.support.paths import CODE_DIR
from tests.support.mock import NO_MOCK, NO_MOCK_REASON, patch

# Import salt libs
import salt.utils
import salt.config
import salt.loader

SUFFIXES_MAP = {}
for (suffix, mode, kind) in salt.loader.SUFFIXES:
    SUFFIXES_MAP[suffix] = (suffix, mode, kind)


@skipIf(NO_MOCK, NO_MOCK_REASON)
class BadLoaderModuleVirtualFunctionReturnsTestCase(TestCase):
    '''
    Unit test case for testing bad returns on loader modules
    '''
    maxDiff = None

    @classmethod
    def setUpClass(cls):
        ctx = {}
        opts = salt.config.DEFAULT_MINION_OPTS
        opts['ext_pillar'] = []
        opts['master_tops'] = {}
        grains = salt.loader.grains(opts)
        utils = salt.loader.utils(opts, context=ctx)
        funcs = salt.loader.minion_mods(opts, context=ctx, utils=utils)
        cls.loader_module_globals = {
            '__opts__': opts,
            '__salt__': funcs,
            '__utils__': utils,
            '__grains__': grains,
            '__active_provider_name__': None
        }

    @classmethod
    def tearDownClass(cls):
        del cls.loader_module_globals

    @contextmanager
    def patch_module(self, loader_module):
        loader_module_name = loader_module.__name__
        loader_module_globals = getattr(self, 'loader_module_globals', None)
        loader_module_blacklisted_dunders = getattr(self, 'loader_module_blacklisted_dunders', ())
        #if loader_module_globals is None:
        #    loader_module_globals = {}
        #elif callable(loader_module_globals):
        #    loader_module_globals = loader_module_globals()
        #else:
        #    loader_module_globals = copy.deepcopy(loader_module_globals)

        salt_dunders = (
            '__opts__', '__salt__', '__runner__', '__context__', '__utils__',
            '__ext_pillar__', '__thorium__', '__states__', '__serializers__', '__ret__',
            '__grains__', '__pillar__', '__sdb__',
            # Proxy is commented out on purpose since some code in salt expects a NameError
            # and is most of the time not a required dunder
            '__proxy__'
        )
        for dunder_name in salt_dunders:
            if dunder_name not in loader_module_globals:
                if dunder_name in loader_module_blacklisted_dunders:
                    continue
                loader_module_globals[dunder_name] = {}

        for key in loader_module_globals:
            if not hasattr(loader_module, key):
                if key in salt_dunders:
                    setattr(loader_module, key, {})
                else:
                    setattr(loader_module, key, None)

        if loader_module_globals:
            patcher = patch.multiple(loader_module, **loader_module_globals)
            patcher.start()

        yield loader_module

        if loader_module_globals:
            patcher.stop()
            del loader_module_globals

    def get_loader_modules_for_path(self, path):
        for fname in os.listdir(path):
            if not fname.endswith('.py'):
                continue
            if fname == '__init__.py':
                continue
            with salt.utils.fopen(os.path.join(path, fname)) as rfh:
                if 'def __virtual__():' not in rfh.read():
                    continue
            yield os.path.join(path, fname)

    @contextmanager
    def load_module(self, modpath):
        relmodpath = os.path.relpath(modpath, CODE_DIR)
        no_ext, ext = os.path.splitext(relmodpath)
        modnamespace = no_ext.replace(os.sep, '.')
        with salt.utils.fopen(modpath) as rfh:
            mod = imp.load_module(modnamespace, rfh, modpath, SUFFIXES_MAP[ext])
            with self.patch_module(mod):
                yield mod
        sys.modules.pop(modnamespace, None)
        del mod

    def run_test_for_path(self, path):
        failures = []
        import_errors = []
        for modpath in self.get_loader_modules_for_path(path):
            try:
                with self.load_module(modpath) as mod:
                    virtual_return = mod.__virtual__()
                    if isinstance(virtual_return, (tuple, bool, six.string_types)):
                        continue
                    failures.append((os.path.relpath(modpath, CODE_DIR), virtual_return))
            except ImportError as exc:
                import_errors.append((os.path.relpath(modpath, CODE_DIR), str(exc)))

        if failures:
            errmsg = '\n\nThe following modules \'__virtual__()\' call returns are invalid:\n\n'
            for modpath, returned in failures:
                errmsg += '  {}.__virtual__() returned {}\n'.format(modpath, returned)
            self.assertEqual(failures, [], errmsg)
        if import_errors:
            errmsg = '\n\nThe following modules are not gatting external library imports:\n\n'
            for modpath, exc in import_errors:
                errmsg += '  {} raised an import error when loading: {}\n'.format(modpath, exc)
            self.assertEqual(import_errors, [], errmsg)

    def test_minion_mods(self):
        self.run_test_for_path(os.path.join(CODE_DIR, 'salt', 'modules'))

    def test_engines(self):
        self.run_test_for_path(os.path.join(CODE_DIR, 'salt', 'engines'))

    def test_proxy(self):
        self.run_test_for_path(os.path.join(CODE_DIR, 'salt', 'proxy'))

    def test_returners(self):
        self.run_test_for_path(os.path.join(CODE_DIR, 'salt', 'returners'))

    #def test_utils(self):
    #    self.run_test_for_path(os.path.join(CODE_DIR, 'salt', 'utils'))

    def test_pillars(self):
        self.run_test_for_path(os.path.join(CODE_DIR, 'salt', 'pillar'))

    def test_tops(self):
        self.run_test_for_path(os.path.join(CODE_DIR, 'salt', 'tops'))

    def test_wheels(self):
        self.run_test_for_path(os.path.join(CODE_DIR, 'salt', 'wheel'))

    def test_outputters(self):
        self.run_test_for_path(os.path.join(CODE_DIR, 'salt', 'output'))

    def test_serializers(self):
        self.run_test_for_path(os.path.join(CODE_DIR, 'salt', 'serializers'))

    def test_auth(self):
        self.run_test_for_path(os.path.join(CODE_DIR, 'salt', 'auth'))

    def test_fileserver(self):
        self.run_test_for_path(os.path.join(CODE_DIR, 'salt', 'fileserver'))

    def test_roster(self):
        self.run_test_for_path(os.path.join(CODE_DIR, 'salt', 'roster'))

    def test_thorium(self):
        self.run_test_for_path(os.path.join(CODE_DIR, 'salt', 'thorium'))

    def test_states(self):
        self.run_test_for_path(os.path.join(CODE_DIR, 'salt', 'states'))

    def test_beacons(self):
        self.run_test_for_path(os.path.join(CODE_DIR, 'salt', 'beacons'))

    def test_search(self):
        self.run_test_for_path(os.path.join(CODE_DIR, 'salt', 'search'))

    def test_log_handlers(self):
        self.run_test_for_path(os.path.join(CODE_DIR, 'salt', 'log', 'handlers'))

    def test_renderers(self):
        self.run_test_for_path(os.path.join(CODE_DIR, 'salt', 'renderers'))

    def test_grains(self):
        self.run_test_for_path(os.path.join(CODE_DIR, 'salt', 'grains'))

    def test_runners(self):
        self.run_test_for_path(os.path.join(CODE_DIR, 'salt', 'runners'))

    def test_queues(self):
        self.run_test_for_path(os.path.join(CODE_DIR, 'salt', 'queues'))

    def test_sdb(self):
        self.run_test_for_path(os.path.join(CODE_DIR, 'salt', 'sdb'))

    def test_spm_pkgdb(self):
        self.run_test_for_path(os.path.join(CODE_DIR, 'salt', 'spm', 'pkgdb'))

    def test_spm_pkgfiles(self):
        self.run_test_for_path(os.path.join(CODE_DIR, 'salt', 'spm', 'pkgfiles'))

    def test_clouds(self):
        self.run_test_for_path(os.path.join(CODE_DIR, 'salt', 'cloud', 'clouds'))

    def test_netapi(self):
        self.run_test_for_path(os.path.join(CODE_DIR, 'salt', 'netapi'))

    def test_executors(self):
        self.run_test_for_path(os.path.join(CODE_DIR, 'salt', 'executors'))

    def test_cache(self):
        self.run_test_for_path(os.path.join(CODE_DIR, 'salt', 'cache'))
