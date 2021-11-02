"""
    tests.unit.test_loader
    ~~~~~~~~~~~~~~~~~~~~~~

    Test Salt's loader
"""

import collections
import compileall
import copy
import imp
import inspect
import logging
import os
import shutil
import sys
import tempfile
import textwrap

import pytest
import salt.config
import salt.loader
import salt.loader.context
import salt.loader.lazy
import salt.utils.files
import salt.utils.stringutils
from tests.support.case import ModuleCase
from tests.support.mock import MagicMock, patch
from tests.support.runtests import RUNTIME_VARS
from tests.support.unit import TestCase

log = logging.getLogger(__name__)


def remove_bytecode(module_path):
    paths = [module_path + "c"]
    if hasattr(imp, "get_tag"):
        modname, ext = os.path.splitext(module_path.split(os.sep)[-1])
        paths.append(
            os.path.join(
                os.path.dirname(module_path),
                "__pycache__",
                "{}.{}.pyc".format(modname, imp.get_tag()),
            )
        )
    for path in paths:
        if os.path.exists(path):
            os.unlink(path)


loader_template = """
import os
from salt.utils.decorators import depends

@depends('os')
def loaded():
    return True

@depends('non_existantmodulename')
def not_loaded():
    return True
"""


class LazyLoaderTest(TestCase):
    """
    Test the loader
    """

    module_name = "lazyloadertest"

    @classmethod
    def setUpClass(cls):
        cls.opts = salt.config.minion_config(None)
        cls.opts["grains"] = salt.loader.grains(cls.opts)
        if not os.path.isdir(RUNTIME_VARS.TMP):
            os.makedirs(RUNTIME_VARS.TMP)
        cls.utils = salt.loader.utils(cls.opts)
        cls.proxy = salt.loader.proxy(cls.opts)
        cls.funcs = salt.loader.minion_mods(cls.opts, utils=cls.utils, proxy=cls.proxy)

    def setUp(self):
        # Setup the module
        self.module_dir = tempfile.mkdtemp(dir=RUNTIME_VARS.TMP)
        self.addCleanup(shutil.rmtree, self.module_dir, ignore_errors=True)
        self.module_file = os.path.join(
            self.module_dir, "{}.py".format(self.module_name)
        )
        with salt.utils.files.fopen(self.module_file, "w") as fh:
            fh.write(salt.utils.stringutils.to_str(loader_template))
            fh.flush()
            os.fsync(fh.fileno())

        # Invoke the loader
        self.loader = salt.loader.lazy.LazyLoader(
            [self.module_dir],
            copy.deepcopy(self.opts),
            pack={
                "__utils__": self.utils,
                "__salt__": self.funcs,
                "__proxy__": self.proxy,
            },
            tag="module",
        )

    def tearDown(self):
        del self.module_dir
        del self.module_file
        del self.loader

    @classmethod
    def tearDownClass(cls):
        del cls.opts
        del cls.funcs
        del cls.utils
        del cls.proxy

    @pytest.mark.slow_test
    def test_depends(self):
        """
        Test that the depends decorator works properly
        """
        # Make sure depends correctly allowed a function to load. If this
        # results in a KeyError, the decorator is broken.
        self.assertTrue(
            isinstance(
                self.loader[self.module_name + ".loaded"], salt.loader.lazy.LoadedFunc
            )
        )
        # Make sure depends correctly kept a function from loading
        self.assertTrue(self.module_name + ".not_loaded" not in self.loader)


loader_template_module = """
import my_utils

def run():
    return my_utils.run()
"""

loader_template_utils = """
def run():
    return True
"""


class LazyLoaderUtilsTest(TestCase):
    """
    Test the loader
    """

    module_name = "lazyloaderutilstest"
    utils_name = "my_utils"

    @classmethod
    def setUpClass(cls):
        cls.opts = salt.config.minion_config(None)
        cls.opts["grains"] = salt.loader.grains(cls.opts)
        if not os.path.isdir(RUNTIME_VARS.TMP):
            os.makedirs(RUNTIME_VARS.TMP)

    def setUp(self):
        # Setup the module
        self.module_dir = tempfile.mkdtemp(dir=RUNTIME_VARS.TMP)
        self.module_file = os.path.join(
            self.module_dir, "{}.py".format(self.module_name)
        )
        with salt.utils.files.fopen(self.module_file, "w") as fh:
            fh.write(salt.utils.stringutils.to_str(loader_template_module))
            fh.flush()
            os.fsync(fh.fileno())

        self.utils_dir = tempfile.mkdtemp(dir=RUNTIME_VARS.TMP)
        self.utils_file = os.path.join(self.utils_dir, "{}.py".format(self.utils_name))
        with salt.utils.files.fopen(self.utils_file, "w") as fh:
            fh.write(salt.utils.stringutils.to_str(loader_template_utils))
            fh.flush()
            os.fsync(fh.fileno())

    def tearDown(self):
        shutil.rmtree(self.module_dir)
        if os.path.isdir(self.module_dir):
            shutil.rmtree(self.module_dir)
        shutil.rmtree(self.utils_dir)
        if os.path.isdir(self.utils_dir):
            shutil.rmtree(self.utils_dir)
        del self.module_dir
        del self.module_file
        del self.utils_dir
        del self.utils_file

        if self.module_name in sys.modules:
            del sys.modules[self.module_name]
        if self.utils_name in sys.modules:
            del sys.modules[self.utils_name]

    @classmethod
    def tearDownClass(cls):
        del cls.opts

    def test_utils_found(self):
        """
        Test that the extra module directory is available for imports
        """
        loader = salt.loader.LazyLoader(
            [self.module_dir],
            copy.deepcopy(self.opts),
            tag="module",
            extra_module_dirs=[self.utils_dir],
        )
        self.assertTrue(
            isinstance(loader[self.module_name + ".run"], salt.loader.lazy.LoadedFunc)
        )
        self.assertTrue(loader[self.module_name + ".run"]())

    def test_utils_not_found(self):
        """
        Test that the extra module directory is not available for imports
        """
        loader = salt.loader.LazyLoader(
            [self.module_dir], copy.deepcopy(self.opts), tag="module"
        )
        self.assertTrue(self.module_name + ".run" not in loader)


class LazyLoaderVirtualEnabledTest(TestCase):
    """
    Test the base loader of salt.
    """

    @classmethod
    def setUpClass(cls):
        cls.opts = salt.config.minion_config(None)
        cls.opts["disable_modules"] = ["pillar"]
        cls.opts["grains"] = salt.loader.grains(cls.opts)
        cls.utils = salt.loader.utils(copy.deepcopy(cls.opts))
        cls.proxy = salt.loader.proxy(cls.opts)
        cls.funcs = salt.loader.minion_mods(cls.opts, utils=cls.utils, proxy=cls.proxy)

    def setUp(self):
        self.loader = salt.loader.LazyLoader(
            salt.loader._module_dirs(copy.deepcopy(self.opts), "modules", "module"),
            copy.deepcopy(self.opts),
            pack={
                "__utils__": self.utils,
                "__salt__": self.funcs,
                "__proxy__": self.proxy,
            },
            tag="module",
        )

    def tearDown(self):
        del self.loader

    @classmethod
    def tearDownClass(cls):
        del cls.opts
        del cls.funcs
        del cls.utils
        del cls.proxy

    @pytest.mark.slow_test
    def test_basic(self):
        """
        Ensure that it only loads stuff when needed
        """
        # make sure it starts empty
        self.assertEqual(self.loader._dict, {})
        # get something, and make sure its a func
        self.assertTrue(inspect.isfunction(self.loader["test.ping"].func))

        # make sure we only loaded "test" functions
        for key, val in self.loader._dict.items():
            self.assertEqual(key.split(".", 1)[0], "test")

        # make sure the depends thing worked (double check of the depends testing,
        # since the loader does the calling magically
        self.assertFalse("test.missing_func" in self.loader._dict)

    def test_badkey(self):
        with self.assertRaises(KeyError):
            self.loader[None]  # pylint: disable=W0104

        with self.assertRaises(KeyError):
            self.loader[1]  # pylint: disable=W0104

    @pytest.mark.slow_test
    def test_disable(self):
        self.assertNotIn("pillar.items", self.loader)

    @pytest.mark.slow_test
    def test_len_load(self):
        """
        Since LazyLoader is a MutableMapping, if someone asks for len() we have
        to load all
        """
        self.assertEqual(self.loader._dict, {})
        len(self.loader)  # force a load all
        self.assertNotEqual(self.loader._dict, {})

    @pytest.mark.slow_test
    def test_iter_load(self):
        """
        Since LazyLoader is a MutableMapping, if someone asks to iterate we have
        to load all
        """
        self.assertEqual(self.loader._dict, {})
        # force a load all
        for key, func in self.loader.items():
            break
        self.assertNotEqual(self.loader._dict, {})

    def test_context(self):
        """
        Make sure context is shared across modules
        """
        # make sure it starts empty
        self.assertEqual(self.loader._dict, {})
        # get something, and make sure its a func
        func = self.loader["test.ping"]
        with salt.loader.context.loader_context(self.loader):
            with patch.dict(func.__globals__["__context__"], {"foo": "bar"}):
                self.assertEqual(
                    self.loader["test.echo"].__globals__["__context__"]["foo"], "bar"
                )
                self.assertEqual(
                    self.loader["grains.get"].__globals__["__context__"]["foo"], "bar"
                )

    def test_globals(self):
        with salt.loader.context.loader_context(self.loader):
            func_globals = self.loader["test.ping"].__globals__
            self.assertEqual(
                func_globals["__grains__"].value(), self.opts.get("grains", {})
            )
            self.assertEqual(
                func_globals["__pillar__"].value(), self.opts.get("pillar", {})
            )
            # the opts passed into modules is at least a subset of the whole opts
            for key, val in func_globals["__opts__"].items():
                if (
                    key in salt.config.DEFAULT_MASTER_OPTS
                    and key not in salt.config.DEFAULT_MINION_OPTS
                ):
                    # We loaded the minion opts, but somewhere in the code, the master options got pulled in
                    # Let's just not check for equality since the option won't even exist in the loaded
                    # minion options
                    continue
                if (
                    key not in salt.config.DEFAULT_MASTER_OPTS
                    and key not in salt.config.DEFAULT_MINION_OPTS
                ):
                    # This isn't even a default configuration setting, lets carry on
                    continue
                self.assertEqual(self.opts[key], val)

    def test_pack(self):
        with salt.loader.context.loader_context(self.loader):
            self.loader.pack["__foo__"] = "bar"
            func_globals = self.loader["test.ping"].__globals__
            self.assertEqual(func_globals["__foo__"].value(), "bar")

    @pytest.mark.slow_test
    def test_virtual(self):
        self.assertNotIn("test_virtual.ping", self.loader)


class LazyLoaderVirtualDisabledTest(TestCase):
    """
    Test the loader of salt without __virtual__
    """

    @classmethod
    def setUpClass(cls):
        cls.opts = salt.config.minion_config(None)
        cls.opts["grains"] = salt.loader.grains(cls.opts)
        cls.utils = salt.loader.utils(copy.deepcopy(cls.opts))
        cls.proxy = salt.loader.proxy(cls.opts)
        cls.funcs = salt.loader.minion_mods(cls.opts, utils=cls.utils, proxy=cls.proxy)

    def setUp(self):
        self.loader = salt.loader.LazyLoader(
            salt.loader._module_dirs(copy.deepcopy(self.opts), "modules", "module"),
            copy.deepcopy(self.opts),
            tag="module",
            pack={
                "__utils__": self.utils,
                "__salt__": self.funcs,
                "__proxy__": self.proxy,
            },
            virtual_enable=False,
        )

    def tearDown(self):
        del self.loader

    @classmethod
    def tearDownClass(cls):
        del cls.opts
        del cls.utils
        del cls.funcs
        del cls.proxy

    @pytest.mark.slow_test
    def test_virtual(self):
        self.assertTrue(
            isinstance(self.loader["test_virtual.ping"], salt.loader.lazy.LoadedFunc)
        )


class LazyLoaderWhitelistTest(TestCase):
    """
    Test the loader of salt with a whitelist
    """

    @classmethod
    def setUpClass(cls):
        cls.opts = salt.config.minion_config(None)
        cls.opts["grains"] = salt.loader.grains(cls.opts)
        cls.utils = salt.loader.utils(copy.deepcopy(cls.opts))
        cls.proxy = salt.loader.proxy(cls.opts)
        cls.funcs = salt.loader.minion_mods(cls.opts, utils=cls.utils, proxy=cls.proxy)

    def setUp(self):
        self.loader = salt.loader.LazyLoader(
            salt.loader._module_dirs(copy.deepcopy(self.opts), "modules", "module"),
            copy.deepcopy(self.opts),
            tag="module",
            pack={
                "__utils__": self.utils,
                "__salt__": self.funcs,
                "__proxy__": self.proxy,
            },
            whitelist=["test", "pillar"],
        )

    def tearDown(self):
        del self.loader

    @classmethod
    def tearDownClass(cls):
        del cls.opts
        del cls.funcs
        del cls.utils
        del cls.proxy

    @pytest.mark.slow_test
    def test_whitelist(self):
        self.assertTrue(inspect.isfunction(self.loader["test.ping"].func))
        self.assertTrue(inspect.isfunction(self.loader["pillar.get"].func))

        self.assertNotIn("grains.get", self.loader)


class LazyLoaderGrainsBlacklistTest(TestCase):
    """
    Test the loader of grains with a blacklist
    """

    def setUp(self):
        self.opts = salt.config.minion_config(None)

    def tearDown(self):
        del self.opts

    @pytest.mark.slow_test
    def test_whitelist(self):
        opts = copy.deepcopy(self.opts)
        opts["grains_blacklist"] = ["master", "os*", "ipv[46]"]

        grains = salt.loader.grains(opts)
        self.assertNotIn("master", grains)
        self.assertNotIn("os", {g[:2] for g in list(grains)})
        self.assertNotIn("ipv4", grains)
        self.assertNotIn("ipv6", grains)


class LazyLoaderSingleItem(TestCase):
    """
    Test loading a single item via the _load() function
    """

    @classmethod
    def setUpClass(cls):
        cls.opts = salt.config.minion_config(None)
        cls.opts["grains"] = salt.loader.grains(cls.opts)
        cls.utils = salt.loader.utils(copy.deepcopy(cls.opts))
        cls.proxy = salt.loader.proxy(cls.opts)
        cls.funcs = salt.loader.minion_mods(cls.opts, utils=cls.utils, proxy=cls.proxy)

    @classmethod
    def tearDownClass(cls):
        del cls.opts
        del cls.funcs
        del cls.utils
        del cls.proxy

    def setUp(self):
        self.loader = salt.loader.LazyLoader(
            salt.loader._module_dirs(copy.deepcopy(self.opts), "modules", "module"),
            copy.deepcopy(self.opts),
            pack={
                "__utils__": self.utils,
                "__salt__": self.funcs,
                "__proxy__": self.proxy,
            },
            tag="module",
        )

    def tearDown(self):
        del self.loader

    def test_single_item_no_dot(self):
        """
        Checks that a KeyError is raised when the function key does not contain a '.'
        """
        key = "testing_no_dot"
        expected = "The key '{}' should contain a '.'".format(key)
        with self.assertRaises(KeyError) as err:
            inspect.isfunction(self.loader["testing_no_dot"])

        result = err.exception.args[0]
        assert result == expected, result


module_template = """
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
"""


class LazyLoaderReloadingTest(TestCase):
    """
    Test the loader of salt with changing modules
    """

    module_name = "loadertest"
    module_key = "loadertest.test"

    @classmethod
    def setUpClass(cls):
        cls.opts = salt.config.minion_config(None)
        cls.opts["grains"] = salt.loader.grains(cls.opts)
        if not os.path.isdir(RUNTIME_VARS.TMP):
            os.makedirs(RUNTIME_VARS.TMP)

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(dir=RUNTIME_VARS.TMP)
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)

        self.count = 0
        opts = copy.deepcopy(self.opts)
        dirs = salt.loader._module_dirs(opts, "modules", "module")
        dirs.append(self.tmp_dir)
        self.utils = salt.loader.utils(opts)
        self.proxy = salt.loader.proxy(opts)
        self.minion_mods = salt.loader.minion_mods(opts)
        self.loader = salt.loader.LazyLoader(
            dirs,
            opts,
            tag="module",
            pack={
                "__utils__": self.utils,
                "__proxy__": self.proxy,
                "__salt__": self.minion_mods,
            },
        )

    def tearDown(self):
        for attrname in ("tmp_dir", "utils", "proxy", "loader", "minion_mods", "utils"):
            try:
                delattr(self, attrname)
            except AttributeError:
                continue

    @classmethod
    def tearDownClass(cls):
        del cls.opts

    def update_module(self):
        self.count += 1
        with salt.utils.files.fopen(self.module_path, "wb") as fh:
            fh.write(
                salt.utils.stringutils.to_bytes(
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
        return os.path.join(self.tmp_dir, "{}.py".format(self.module_name))

    @pytest.mark.slow_test
    def test_alias(self):
        """
        Make sure that you can access alias-d modules
        """
        # ensure it doesn't exist
        self.assertNotIn(self.module_key, self.loader)

        self.update_module()
        self.assertNotIn("{}.test_alias".format(self.module_name), self.loader)
        self.assertTrue(
            isinstance(
                self.loader["{}.working_alias".format(self.module_name)],
                salt.loader.lazy.LoadedFunc,
            )
        )
        self.assertTrue(
            inspect.isfunction(
                self.loader["{}.working_alias".format(self.module_name)].func
            )
        )

    @pytest.mark.slow_test
    def test_clear(self):
        self.assertTrue(
            isinstance(self.loader["test.ping"], salt.loader.lazy.LoadedFunc)
        )
        self.assertTrue(inspect.isfunction(self.loader["test.ping"].func))
        self.update_module()  # write out out custom module
        self.loader.clear()  # clear the loader dict

        # force a load of our module
        self.assertTrue(
            isinstance(self.loader[self.module_key], salt.loader.lazy.LoadedFunc)
        )
        self.assertTrue(inspect.isfunction(self.loader[self.module_key].func))

        # make sure we only loaded our custom module
        # which means that we did correctly refresh the file mapping
        for k, v in self.loader._dict.items():
            self.assertTrue(k.startswith(self.module_name))

    @pytest.mark.slow_test
    def test_load(self):
        # ensure it doesn't exist
        self.assertNotIn(self.module_key, self.loader)

        self.update_module()
        self.assertTrue(
            isinstance(self.loader[self.module_key], salt.loader.lazy.LoadedFunc)
        )
        self.assertTrue(inspect.isfunction(self.loader[self.module_key].func))

    @pytest.mark.slow_test
    def test__load__(self):
        """
        If a module specifies __load__ we should only load/expose those modules
        """
        self.update_module()

        # ensure it doesn't exist
        self.assertNotIn(self.module_key + "2", self.loader)

    @pytest.mark.slow_test
    def test__load__and_depends(self):
        """
        If a module specifies __load__ we should only load/expose those modules
        """
        self.update_module()
        # ensure it doesn't exist
        self.assertNotIn(self.module_key + "3", self.loader)
        self.assertNotIn(self.module_key + "4", self.loader)

    @pytest.mark.slow_test
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

    def test_wrong_bytecode(self):
        """
        Checks to make sure we don't even try to load .pyc files that are for a different Python
        This should pass (the load should fail) all the time because we don't run Salt on Py 3.4 anymore
        """
        test_module_name = "test_module.cpython-34"
        filemap_save = copy.deepcopy(self.loader.file_mapping)
        self.loader.file_mapping = {
            test_module_name: (
                "/temp/path/does/not/matter/here/__pycache__/"
                + test_module_name
                + ".pyc",
                ".pyc",
                0,
            )
        }

        self.assertFalse(self.loader._load_module(test_module_name))

        self.loader.file_mapping = copy.deepcopy(filemap_save)


virtual_aliases = ("loadertest2", "loadertest3")
virtual_alias_module_template = """
__virtual_aliases__ = {}

def test():
    return True
""".format(
    virtual_aliases
)


class LazyLoaderVirtualAliasTest(TestCase):
    """
    Test the loader of salt with changing modules
    """

    module_name = "loadertest"

    @classmethod
    def setUpClass(cls):
        cls.opts = salt.config.minion_config(None)
        cls.opts["grains"] = salt.loader.grains(cls.opts)
        if not os.path.isdir(RUNTIME_VARS.TMP):
            os.makedirs(RUNTIME_VARS.TMP)

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(dir=RUNTIME_VARS.TMP)
        opts = copy.deepcopy(self.opts)
        dirs = salt.loader._module_dirs(opts, "modules", "module")
        dirs.append(self.tmp_dir)
        self.utils = salt.loader.utils(opts)
        self.proxy = salt.loader.proxy(opts)
        self.minion_mods = salt.loader.minion_mods(opts)
        self.loader = salt.loader.LazyLoader(
            dirs,
            opts,
            tag="module",
            pack={
                "__utils__": self.utils,
                "__proxy__": self.proxy,
                "__salt__": self.minion_mods,
            },
        )

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
        with salt.utils.files.fopen(self.module_path, "wb") as fh:
            fh.write(salt.utils.stringutils.to_bytes(virtual_alias_module_template))
            fh.flush()
            os.fsync(fh.fileno())  # flush to disk

        # pyc files don't like it when we change the original quickly
        # since the header bytes only contain the timestamp (granularity of seconds)
        # TODO: don't write them? Is *much* slower on re-load (~3x)
        # https://docs.python.org/2/library/sys.html#sys.dont_write_bytecode
        remove_bytecode(self.module_path)

    @property
    def module_path(self):
        return os.path.join(self.tmp_dir, "{}.py".format(self.module_name))

    @pytest.mark.slow_test
    def test_virtual_alias(self):
        """
        Test the __virtual_alias__ feature
        """
        self.update_module()

        mod_names = [self.module_name] + list(virtual_aliases)
        for mod_name in mod_names:
            func_name = ".".join((mod_name, "test"))
            log.debug("Running %s (dict attribute)", func_name)
            self.assertTrue(self.loader[func_name]())
            log.debug("Running %s (loader attribute)", func_name)
            self.assertTrue(getattr(self.loader, mod_name).test())


submodule_template = """
from __future__ import absolute_import

import {0}.lib

def test():
    return ({count}, {0}.lib.test())
"""

submodule_lib_template = """
def test():
    return {count}
"""


class LazyLoaderSubmodReloadingTest(TestCase):
    """
    Test the loader of salt with changing modules
    """

    module_name = "loadertestsubmod"
    module_key = "loadertestsubmod.test"

    @classmethod
    def setUpClass(cls):
        cls.opts = salt.config.minion_config(None)
        cls.opts["grains"] = salt.loader.grains(cls.opts)
        if not os.path.isdir(RUNTIME_VARS.TMP):
            os.makedirs(RUNTIME_VARS.TMP)

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(dir=RUNTIME_VARS.TMP)
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        os.makedirs(self.module_dir)

        self.count = 0
        self.lib_count = 0

        opts = copy.deepcopy(self.opts)
        dirs = salt.loader._module_dirs(opts, "modules", "module")
        dirs.append(self.tmp_dir)
        self.utils = salt.loader.utils(opts)
        self.proxy = salt.loader.proxy(opts)
        self.minion_mods = salt.loader.minion_mods(opts)
        self.loader = salt.loader.LazyLoader(
            dirs,
            opts,
            tag="module",
            pack={
                "__utils__": self.utils,
                "__proxy__": self.proxy,
                "__salt__": self.minion_mods,
            },
        )

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
        self.count += 1
        with salt.utils.files.fopen(self.module_path, "wb") as fh:
            fh.write(
                salt.utils.stringutils.to_bytes(
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
        with salt.utils.files.fopen(self.lib_path, "wb") as fh:
            fh.write(
                salt.utils.stringutils.to_bytes(
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
        return os.path.join(self.module_dir, "__init__.py")

    @property
    def lib_path(self):
        return os.path.join(self.module_dir, "lib.py")

    @pytest.mark.slow_test
    def test_basic(self):
        # ensure it doesn't exist
        self.assertNotIn(self.module_key, self.loader)

        self.update_module()
        self.update_lib()
        self.loader.clear()
        self.assertIn(self.module_key, self.loader)

    @pytest.mark.slow_test
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
            self.assertEqual(
                self.loader[self.module_key](), (self.count, self.lib_count)
            )

        # update just the module
        for x in range(1, 3):
            self.update_module()
            self.loader.clear()
            self.assertNotIn(self.module_key, self.loader._dict)
            self.assertIn(self.module_key, self.loader)
            self.assertEqual(
                self.loader[self.module_key](), (self.count, self.lib_count)
            )

        # update just the lib
        for x in range(1, 3):
            self.update_lib()
            self.loader.clear()
            self.assertNotIn(self.module_key, self.loader._dict)
            self.assertIn(self.module_key, self.loader)
            self.assertEqual(
                self.loader[self.module_key](), (self.count, self.lib_count)
            )

        self.rm_module()
        # make sure that even if we remove the module, its still loaded until a clear
        self.assertEqual(self.loader[self.module_key](), (self.count, self.lib_count))
        self.loader.clear()
        self.assertNotIn(self.module_key, self.loader)

    @pytest.mark.slow_test
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


mod_template = """
def test():
    return ({val})
"""


class LazyLoaderModulePackageTest(TestCase):
    """
    Test the loader of salt with changing modules
    """

    module_name = "loadertestmodpkg"
    module_key = "loadertestmodpkg.test"

    @classmethod
    def setUpClass(cls):
        cls.opts = salt.config.minion_config(None)
        cls.opts["grains"] = salt.loader.grains(cls.opts)
        if not os.path.isdir(RUNTIME_VARS.TMP):
            os.makedirs(RUNTIME_VARS.TMP)
        cls.utils = salt.loader.utils(copy.deepcopy(cls.opts))
        cls.proxy = salt.loader.proxy(cls.opts)
        cls.funcs = salt.loader.minion_mods(cls.opts, utils=cls.utils, proxy=cls.proxy)

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(dir=RUNTIME_VARS.TMP)
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)

        dirs = salt.loader._module_dirs(copy.deepcopy(self.opts), "modules", "module")
        dirs.append(self.tmp_dir)
        self.loader = salt.loader.LazyLoader(
            dirs,
            copy.deepcopy(self.opts),
            pack={
                "__utils__": self.utils,
                "__salt__": self.funcs,
                "__proxy__": self.proxy,
            },
            tag="module",
        )

    def tearDown(self):
        del self.tmp_dir
        del self.loader

    @classmethod
    def tearDownClass(cls):
        del cls.opts
        del cls.funcs
        del cls.utils
        del cls.proxy

    def update_pyfile(self, pyfile, contents):
        dirname = os.path.dirname(pyfile)
        if not os.path.exists(dirname):
            os.makedirs(dirname)
        with salt.utils.files.fopen(pyfile, "wb") as fh:
            fh.write(salt.utils.stringutils.to_bytes(contents))
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

    @pytest.mark.slow_test
    def test_module(self):
        # ensure it doesn't exist
        self.assertNotIn("foo", self.loader)
        self.assertNotIn("foo.test", self.loader)
        self.update_module("foo.py", mod_template.format(val=1))
        self.loader.clear()
        self.assertIn("foo.test", self.loader)
        self.assertEqual(self.loader["foo.test"](), 1)

    @pytest.mark.slow_test
    def test_package(self):
        # ensure it doesn't exist
        self.assertNotIn("foo", self.loader)
        self.assertNotIn("foo.test", self.loader)
        self.update_module("foo/__init__.py", mod_template.format(val=2))
        self.loader.clear()
        self.assertIn("foo.test", self.loader)
        self.assertEqual(self.loader["foo.test"](), 2)

    @pytest.mark.slow_test
    def test_module_package_collision(self):
        # ensure it doesn't exist
        self.assertNotIn("foo", self.loader)
        self.assertNotIn("foo.test", self.loader)
        self.update_module("foo.py", mod_template.format(val=3))
        self.loader.clear()
        self.assertIn("foo.test", self.loader)
        self.assertEqual(self.loader["foo.test"](), 3)

        self.update_module("foo/__init__.py", mod_template.format(val=4))
        self.loader.clear()
        self.assertIn("foo.test", self.loader)
        self.assertEqual(self.loader["foo.test"](), 4)


deep_init_base = """
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
"""


class LazyLoaderDeepSubmodReloadingTest(TestCase):
    module_name = "loadertestsubmoddeep"
    libs = ("top_lib", "mid_lib", "bot_lib")

    @classmethod
    def setUpClass(cls):
        cls.opts = salt.config.minion_config(None)
        cls.opts["grains"] = salt.loader.grains(cls.opts)
        if not os.path.isdir(RUNTIME_VARS.TMP):
            os.makedirs(RUNTIME_VARS.TMP)

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(dir=RUNTIME_VARS.TMP)
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        os.makedirs(self.module_dir)

        self.lib_count = collections.defaultdict(int)  # mapping of path -> count

        # bootstrap libs
        with salt.utils.files.fopen(
            os.path.join(self.module_dir, "__init__.py"), "w"
        ) as fh:
            # No .decode() needed here as deep_init_base is defined as str and
            # not bytes.
            fh.write(
                salt.utils.stringutils.to_str(deep_init_base.format(self.module_name))
            )
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
        dirs = salt.loader._module_dirs(opts, "modules", "module")
        dirs.append(self.tmp_dir)
        self.utils = salt.loader.utils(opts)
        self.proxy = salt.loader.proxy(opts)
        self.minion_mods = salt.loader.minion_mods(opts)
        self.loader = salt.loader.LazyLoader(
            dirs,
            copy.deepcopy(opts),
            tag="module",
            pack={
                "__utils__": self.utils,
                "__proxy__": self.proxy,
                "__salt__": self.minion_mods,
            },
        )
        self.assertIn("{}.top".format(self.module_name), self.loader)

    def tearDown(self):
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
        path = os.path.join(self.lib_paths[lib_name], "__init__.py")
        self.lib_count[lib_name] += 1
        with salt.utils.files.fopen(path, "wb") as fh:
            fh.write(
                salt.utils.stringutils.to_bytes(
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

    @pytest.mark.slow_test
    def test_basic(self):
        self.assertIn("{}.top".format(self.module_name), self.loader)

    def _verify_libs(self):
        for lib in self.libs:
            self.assertEqual(
                self.loader[
                    "{}.{}".format(self.module_name, lib.replace("_lib", ""))
                ](),
                self.lib_count[lib],
            )

    @pytest.mark.slow_test
    def test_reload(self):
        """
        Make sure that we can reload all libraries of arbitrary depth
        """
        self._verify_libs()

        # update them all
        for lib in self.libs:
            for x in range(5):
                self.update_lib(lib)
                self.loader.clear()
                self._verify_libs()


class LoaderMultipleGlobalTest(ModuleCase):
    """
    Tests when using multiple lazyloaders
    """

    def setUp(self):
        opts = salt.config.minion_config(None)
        self.loader1 = salt.loader.LazyLoader(
            salt.loader._module_dirs(copy.deepcopy(opts), "modules", "module"),
            copy.deepcopy(opts),
            pack={},
            tag="module",
            loaded_base_name="salt.loader1",
        )
        self.loader2 = salt.loader.LazyLoader(
            salt.loader._module_dirs(copy.deepcopy(opts), "modules", "module"),
            copy.deepcopy(opts),
            pack={},
            tag="module",
            loaded_base_name="salt.loader2",
        )

    def tearDown(self):
        del self.loader1
        del self.loader2

    def test_loader_globals(self):
        """
        Test to ensure loaders do not edit
        each others loader's namespace
        """
        self.loader1.pack["__foo__"] = "bar1"
        func1 = self.loader1["test.ping"]

        self.loader2.pack["__foo__"] = "bar2"
        func2 = self.loader2["test.ping"]
        token = salt.loader.context.loader_ctxvar.set(self.loader1)
        try:
            assert func1.__globals__["__foo__"].value() == "bar1"
        finally:
            salt.loader.context.loader_ctxvar.reset(token)
        token = salt.loader.context.loader_ctxvar.set(self.loader2)
        try:
            assert func2.__globals__["__foo__"].value() == "bar2"
        finally:
            salt.loader.context.loader_ctxvar.reset(token)


class LoaderCleanupTest(ModuleCase):
    """
    Tests the loader cleanup procedures
    """

    def setUp(self):
        opts = salt.config.minion_config(None)
        self.loader1 = salt.loader.LazyLoader(
            salt.loader._module_dirs(copy.deepcopy(opts), "modules", "module"),
            copy.deepcopy(opts),
            pack={},
            tag="module",
            loaded_base_name="salt.test",
        )

    def tearDown(self):
        del self.loader1

    def test_loader_clean_modules(self):
        loaded_base_name = self.loader1.loaded_base_name
        self.loader1.clean_modules()

        for name in list(sys.modules):
            if name.startswith(loaded_base_name):
                self.fail(
                    "Found a real module reference in sys.modules matching {!r}".format(
                        loaded_base_name
                    )
                )
                break


class LoaderGlobalsTest(ModuleCase):
    """
    Test all of the globals that the loader is responsible for adding to modules

    This shouldn't be done here, but should rather be done per module type (in the cases where they are used)
    so they can check ALL globals that they have (or should have) access to.

    This is intended as a shorter term way of testing these so we don't break the loader
    """

    def _verify_globals(self, mod_dict):
        """
        Verify that the globals listed in the doc string (from the test) are in these modules
        """
        # find the globals
        global_vars = {}
        for val in mod_dict.values():
            # only find salty globals
            if val.__module__.startswith("salt.loaded"):
                if hasattr(val, "__globals__"):
                    if hasattr(val, "__wrapped__") or "__wrapped__" in val.__globals__:
                        global_vars[val.__module__] = sys.modules[
                            val.__module__
                        ].__dict__
                    else:
                        global_vars[val.__module__] = val.__globals__

        # if we couldn't find any, then we have no modules -- so something is broken
        self.assertNotEqual(global_vars, {}, msg="No modules were loaded.")

        # get the names of the globals you should have
        func_name = inspect.stack()[1][3]
        names = next(
            iter(salt.utils.yaml.safe_load(getattr(self, func_name).__doc__).values())
        )

        # Now, test each module!
        for item in global_vars.values():
            for name in names:
                self.assertIn(name, list(item.keys()))

    def test_auth(self):
        """
        Test that auth mods have:
            - __pillar__
            - __grains__
            - __salt__
            - __context__
        """
        self._verify_globals(salt.loader.auth(self.master_opts))

    def test_runners(self):
        """
        Test that runners have:
            - __pillar__
            - __salt__
            - __opts__
            - __grains__
            - __context__
        """
        self._verify_globals(salt.loader.runner(self.master_opts))

    def test_returners(self):
        """
        Test that returners have:
            - __salt__
            - __opts__
            - __pillar__
            - __grains__
            - __context__
        """
        self._verify_globals(salt.loader.returners(self.master_opts, {}))

    def test_pillars(self):
        """
        Test that pillars have:
            - __salt__
            - __opts__
            - __pillar__
            - __grains__
            - __context__
        """
        self._verify_globals(salt.loader.pillars(self.master_opts, {}))

    def test_tops(self):
        """
        Test that tops have: []
        """
        self._verify_globals(salt.loader.tops(self.master_opts))

    def test_outputters(self):
        """
        Test that outputters have:
            - __opts__
            - __pillar__
            - __grains__
            - __context__
        """
        self._verify_globals(salt.loader.outputters(self.master_opts))

    def test_serializers(self):
        """
        Test that serializers have: []
        """
        self._verify_globals(salt.loader.serializers(self.master_opts))

    @pytest.mark.slow_test
    def test_states(self):
        """
        Test that states have:
            - __pillar__
            - __salt__
            - __opts__
            - __grains__
            - __context__
        """
        opts = salt.config.minion_config(None)
        opts["grains"] = salt.loader.grains(opts)
        utils = salt.loader.utils(opts)
        proxy = salt.loader.proxy(opts)
        funcs = salt.loader.minion_mods(opts, utils=utils, proxy=proxy)
        self._verify_globals(salt.loader.states(opts, funcs, utils, {}, proxy=proxy))

    def test_renderers(self):
        """
        Test that renderers have:
            - __salt__    # Execution functions (i.e. __salt__['test.echo']('foo'))
            - __grains__  # Grains (i.e. __grains__['os'])
            - __pillar__  # Pillar data (i.e. __pillar__['foo'])
            - __opts__    # Minion configuration options
            - __context__ # Context dict shared amongst all modules of the same type
        """
        self._verify_globals(salt.loader.render(self.master_opts, {}))


class RawModTest(TestCase):
    """
    Test the interface of raw_mod
    """

    def setUp(self):
        self.opts = salt.config.minion_config(None)

    def tearDown(self):
        del self.opts

    @pytest.mark.slow_test
    def test_basic(self):
        testmod = salt.loader.raw_mod(self.opts, "test", None)
        for k, v in testmod.items():
            self.assertEqual(k.split(".")[0], "test")

    def test_bad_name(self):
        testmod = salt.loader.raw_mod(self.opts, "module_we_do_not_have", None)
        self.assertEqual(testmod, {})


class NetworkUtilsTestCase(ModuleCase):
    def test_is_private(self):
        mod = salt.loader.raw_mod(self.minion_opts, "network", None)
        self.assertTrue(mod["network.is_private"]("10.0.0.1"), True)

    def test_is_loopback(self):
        mod = salt.loader.raw_mod(self.minion_opts, "network", None)
        self.assertTrue(mod["network.is_loopback"]("127.0.0.1"), True)


class LazyLoaderOptimizationOrderTest(TestCase):
    """
    Test the optimization order priority in the loader (PY3)
    """

    module_name = "lazyloadertest"
    module_content = textwrap.dedent(
        """\
        # -*- coding: utf-8 -*-
        from __future__ import absolute_import

        def test():
            return True
        """
    )

    @classmethod
    def setUpClass(cls):
        cls.opts = salt.config.minion_config(None)
        cls.opts["grains"] = salt.loader.grains(cls.opts)
        cls.utils = salt.loader.utils(copy.deepcopy(cls.opts))
        cls.proxy = salt.loader.proxy(cls.opts)
        cls.funcs = salt.loader.minion_mods(cls.opts, utils=cls.utils, proxy=cls.proxy)

    @classmethod
    def tearDownClass(cls):
        del cls.opts
        del cls.funcs
        del cls.utils
        del cls.proxy

    def setUp(self):
        # Setup the module
        self.module_dir = tempfile.mkdtemp(dir=RUNTIME_VARS.TMP)
        self.addCleanup(shutil.rmtree, self.module_dir, ignore_errors=True)
        self.module_file = os.path.join(
            self.module_dir, "{}.py".format(self.module_name)
        )

    def tearDown(self):
        try:
            delattr(self, "loader")
        except AttributeError:
            pass

    def _get_loader(self, order=None):
        opts = copy.deepcopy(self.opts)
        if order is not None:
            opts["optimization_order"] = order
        # Return a loader
        return salt.loader.LazyLoader(
            [self.module_dir],
            opts,
            pack={
                "__utils__": self.utils,
                "__salt__": self.funcs,
                "__proxy__": self.proxy,
            },
            tag="module",
        )

    def _get_module_filename(self):
        # The act of referencing the loader entry forces the module to be
        # loaded by the LazyDict.
        mod_fullname = self.loader[next(iter(self.loader))].__module__
        return sys.modules[mod_fullname].__file__

    def _expected(self, optimize=0):
        return "lazyloadertest.cpython-{}{}{}.pyc".format(
            sys.version_info[0],
            sys.version_info[1],
            "" if not optimize else ".opt-{}".format(optimize),
        )

    def _write_module_file(self):
        with salt.utils.files.fopen(self.module_file, "w") as fh:
            fh.write(self.module_content)
            fh.flush()
            os.fsync(fh.fileno())

    def _byte_compile(self):
        compileall.compile_file(self.module_file, quiet=1, optimize=0)
        compileall.compile_file(self.module_file, quiet=1, optimize=1)
        compileall.compile_file(self.module_file, quiet=1, optimize=2)

    def _test_optimization_order(self, order):
        self._write_module_file()
        self._byte_compile()

        # Clean up the original file so that we can be assured we're only
        # loading the byte-compiled files(s).
        os.remove(self.module_file)

        self.loader = self._get_loader(order)
        filename = self._get_module_filename()
        basename = os.path.basename(filename)
        assert basename == self._expected(order[0]), basename

        # Remove the file and make a new loader. We should now load the
        # byte-compiled file with an optimization level matching the 2nd
        # element of the order list.
        os.remove(filename)
        self.loader = self._get_loader(order)
        filename = self._get_module_filename()
        basename = os.path.basename(filename)
        assert basename == self._expected(order[1]), basename

        # Remove the file and make a new loader. We should now load the
        # byte-compiled file with an optimization level matching the 3rd
        # element of the order list.
        os.remove(filename)
        self.loader = self._get_loader(order)
        filename = self._get_module_filename()
        basename = os.path.basename(filename)
        assert basename == self._expected(order[2]), basename

    def test_optimization_order(self):
        """
        Test the optimization_order config param
        """
        self._test_optimization_order([0, 1, 2])
        self._test_optimization_order([0, 2, 1])
        self._test_optimization_order([1, 2, 0])
        self._test_optimization_order([1, 0, 2])
        self._test_optimization_order([2, 0, 1])
        self._test_optimization_order([2, 1, 0])

    def test_load_source_file(self):
        """
        Make sure that .py files are preferred over .pyc files
        """
        self._write_module_file()
        self._byte_compile()
        self.loader = self._get_loader()
        filename = self._get_module_filename()
        basename = os.path.basename(filename)
        expected = "lazyloadertest.py"
        assert basename == expected, basename


class LoaderLoadCachedGrainsTest(TestCase):
    """
    Test how the loader works with cached grains
    """

    @classmethod
    def setUpClass(cls):
        cls.opts = salt.config.minion_config(None)
        if not os.path.isdir(RUNTIME_VARS.TMP):
            os.makedirs(RUNTIME_VARS.TMP)

    def setUp(self):
        self.cache_dir = tempfile.mkdtemp(dir=RUNTIME_VARS.TMP)
        self.addCleanup(shutil.rmtree, self.cache_dir, ignore_errors=True)

        self.opts["cachedir"] = self.cache_dir
        self.opts["grains_cache"] = True
        self.opts["grains"] = salt.loader.grains(self.opts)

    @pytest.mark.slow_test
    def test_osrelease_info_has_correct_type(self):
        """
        Make sure osrelease_info is tuple after caching
        """
        grains = salt.loader.grains(self.opts)
        osrelease_info = grains["osrelease_info"]
        assert isinstance(osrelease_info, tuple), osrelease_info


class LazyLoaderRefreshFileMappingTest(TestCase):
    """
    Test that _refresh_file_mapping is called using acquiring LazyLoader._lock
    """

    @classmethod
    def setUpClass(cls):
        cls.opts = salt.config.minion_config(None)
        cls.opts["grains"] = salt.loader.grains(cls.opts)
        cls.utils = salt.loader.utils(copy.deepcopy(cls.opts))
        cls.proxy = salt.loader.proxy(cls.opts)
        cls.funcs = salt.loader.minion_mods(cls.opts, utils=cls.utils, proxy=cls.proxy)

    def setUp(self):
        class LazyLoaderMock(salt.loader.LazyLoader):
            pass

        self.LOADER_CLASS = LazyLoaderMock

    def __init_loader(self):
        return self.LOADER_CLASS(
            salt.loader._module_dirs(copy.deepcopy(self.opts), "modules", "module"),
            copy.deepcopy(self.opts),
            tag="module",
            pack={
                "__utils__": self.utils,
                "__salt__": self.funcs,
                "__proxy__": self.proxy,
            },
        )

    @classmethod
    def tearDownClass(cls):
        del cls.opts
        del cls.utils
        del cls.funcs
        del cls.proxy

    def test_lazyloader_refresh_file_mapping_called_with_lock_at___init__(self):
        func_mock = MagicMock()
        lock_mock = MagicMock()
        lock_mock.__enter__ = MagicMock()
        self.LOADER_CLASS._refresh_file_mapping = func_mock
        with patch("threading.RLock", MagicMock(return_value=lock_mock)):
            loader = self.__init_loader()
        lock_mock.__enter__.assert_called()
        func_mock.assert_called()
        assert len(func_mock.call_args_list) == len(lock_mock.__enter__.call_args_list)
        del loader

    def test_lazyloader_zip_modules(self):
        self.opts["enable_zip_modules"] = True
        try:
            loader = self.__init_loader()
            assert ".zip" in loader.suffix_map
            assert ".zip" in loader.suffix_order
        finally:
            self.opts["enable_zip_modules"] = False
        loader = self.__init_loader()
        assert ".zip" not in loader.suffix_map
        assert ".zip" not in loader.suffix_order

    def test_lazyloader_pyx_modules(self):
        self.opts["cython_enable"] = True
        try:
            loader = self.__init_loader()
            # Don't assert if the current environment has no pyximport
            if salt.loader.lazy.pyximport is not None:
                assert ".pyx" in loader.suffix_map
                assert ".pyx" in loader.suffix_order
        finally:
            self.opts["cython_enable"] = False
        loader = self.__init_loader()
        assert ".pyx" not in loader.suffix_map
        assert ".pyx" not in loader.suffix_order
