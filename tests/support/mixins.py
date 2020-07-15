# -*- coding: utf-8 -*-
"""
    :codeauthor: Pedro Algarvio (pedro@algarvio.me)

    =============
    Class Mix-Ins
    =============

    Some reusable class Mixins
"""
from __future__ import absolute_import, print_function

import atexit
import copy
import functools
import logging
import multiprocessing
import os
import pprint
import subprocess
import sys
import tempfile
import time
import types

import salt.config
import salt.exceptions
import salt.utils.event
import salt.utils.files
import salt.utils.functools
import salt.utils.path
import salt.utils.process
import salt.utils.stringutils
import salt.utils.yaml
import salt.version
from salt._compat import ElementTree as etree
from salt.ext import six
from salt.ext.six.moves import zip
from salt.ext.six.moves.queue import Empty
from salt.utils.immutabletypes import freeze
from salt.utils.verify import verify_env
from tests.support.mock import patch
from tests.support.paths import CODE_DIR
from tests.support.runtests import RUNTIME_VARS

try:
    from salt.utils.odict import OrderedDict
except ImportError:
    from collections import OrderedDict

log = logging.getLogger(__name__)


class CheckShellBinaryNameAndVersionMixin(object):
    """
    Simple class mix-in to subclass in companion to :class:`ShellCase<tests.support.case.ShellCase>` which
    adds a test case to verify proper version report from Salt's CLI tools.
    """

    _call_binary_ = None
    _call_binary_expected_version_ = None

    def test_version_includes_binary_name(self):
        if getattr(self, "_call_binary_", None) is None:
            self.skipTest("'_call_binary_' not defined.")

        if self._call_binary_expected_version_ is None:
            # Late import
            self._call_binary_expected_version_ = salt.version.__version__

        out = "\n".join(self.run_script(self._call_binary_, "--version"))
        # Assert that the binary name is in the output
        try:
            self.assertIn(self._call_binary_, out)
        except AssertionError:
            # We might have generated the CLI scripts in which case we replace '-' with '_'
            alternate_binary_name = self._call_binary_.replace("-", "_")
            errmsg = "Neither '{}' or '{}' were found as part of the binary name in:\n'{}'".format(
                self._call_binary_, alternate_binary_name, out
            )
            self.assertIn(alternate_binary_name, out, msg=errmsg)

        # Assert that the version is in the output
        self.assertIn(self._call_binary_expected_version_, out)


class AdaptedConfigurationTestCaseMixin(object):

    __slots__ = ()

    @staticmethod
    def get_temp_config(config_for, **config_overrides):
        rootdir = config_overrides.get(
            "root_dir", tempfile.mkdtemp(dir=RUNTIME_VARS.TMP)
        )
        conf_dir = config_overrides.pop("conf_dir", os.path.join(rootdir, "conf"))
        for key in ("cachedir", "pki_dir", "sock_dir"):
            if key not in config_overrides:
                config_overrides[key] = key
        if "log_file" not in config_overrides:
            config_overrides["log_file"] = "logs/{}.log".format(config_for)
        if "user" not in config_overrides:
            config_overrides["user"] = RUNTIME_VARS.RUNNING_TESTS_USER
        config_overrides["root_dir"] = rootdir

        cdict = AdaptedConfigurationTestCaseMixin.get_config(
            config_for, from_scratch=True
        )

        if config_for in ("master", "client_config"):
            rdict = salt.config.apply_master_config(config_overrides, cdict)
        if config_for == "minion":
            rdict = salt.config.apply_minion_config(config_overrides, cdict)

        verify_env(
            [
                os.path.join(rdict["pki_dir"], "minions"),
                os.path.join(rdict["pki_dir"], "minions_pre"),
                os.path.join(rdict["pki_dir"], "minions_rejected"),
                os.path.join(rdict["pki_dir"], "minions_denied"),
                os.path.join(rdict["cachedir"], "jobs"),
                os.path.join(rdict["cachedir"], "tokens"),
                os.path.join(rdict["root_dir"], "cache", "tokens"),
                os.path.join(rdict["pki_dir"], "accepted"),
                os.path.join(rdict["pki_dir"], "rejected"),
                os.path.join(rdict["pki_dir"], "pending"),
                os.path.dirname(rdict["log_file"]),
                rdict["sock_dir"],
                conf_dir,
            ],
            RUNTIME_VARS.RUNNING_TESTS_USER,
            root_dir=rdict["root_dir"],
        )

        rdict["conf_file"] = os.path.join(conf_dir, config_for)
        with salt.utils.files.fopen(rdict["conf_file"], "w") as wfh:
            salt.utils.yaml.safe_dump(rdict, wfh, default_flow_style=False)
        return rdict

    @staticmethod
    def get_config(config_for, from_scratch=False):
        if from_scratch:
            if config_for in ("master", "syndic_master", "mm_master", "mm_sub_master"):
                return salt.config.master_config(
                    AdaptedConfigurationTestCaseMixin.get_config_file_path(config_for)
                )
            elif config_for in ("minion", "sub_minion"):
                return salt.config.minion_config(
                    AdaptedConfigurationTestCaseMixin.get_config_file_path(config_for)
                )
            elif config_for in ("syndic",):
                return salt.config.syndic_config(
                    AdaptedConfigurationTestCaseMixin.get_config_file_path(config_for),
                    AdaptedConfigurationTestCaseMixin.get_config_file_path("minion"),
                )
            elif config_for == "client_config":
                return salt.config.client_config(
                    AdaptedConfigurationTestCaseMixin.get_config_file_path("master")
                )

        if config_for not in RUNTIME_VARS.RUNTIME_CONFIGS:
            if config_for in ("master", "syndic_master", "mm_master", "mm_sub_master"):
                RUNTIME_VARS.RUNTIME_CONFIGS[config_for] = freeze(
                    salt.config.master_config(
                        AdaptedConfigurationTestCaseMixin.get_config_file_path(
                            config_for
                        )
                    )
                )
            elif config_for in ("minion", "sub_minion"):
                RUNTIME_VARS.RUNTIME_CONFIGS[config_for] = freeze(
                    salt.config.minion_config(
                        AdaptedConfigurationTestCaseMixin.get_config_file_path(
                            config_for
                        )
                    )
                )
            elif config_for in ("syndic",):
                RUNTIME_VARS.RUNTIME_CONFIGS[config_for] = freeze(
                    salt.config.syndic_config(
                        AdaptedConfigurationTestCaseMixin.get_config_file_path(
                            config_for
                        ),
                        AdaptedConfigurationTestCaseMixin.get_config_file_path(
                            "minion"
                        ),
                    )
                )
            elif config_for == "client_config":
                RUNTIME_VARS.RUNTIME_CONFIGS[config_for] = freeze(
                    salt.config.client_config(
                        AdaptedConfigurationTestCaseMixin.get_config_file_path("master")
                    )
                )
        return RUNTIME_VARS.RUNTIME_CONFIGS[config_for]

    @property
    def config_dir(self):
        return RUNTIME_VARS.TMP_CONF_DIR

    def get_config_dir(self):
        log.warning("Use the config_dir attribute instead of calling get_config_dir()")
        return self.config_dir

    @staticmethod
    def get_config_file_path(filename):
        if filename == "master":
            return os.path.join(RUNTIME_VARS.TMP_CONF_DIR, filename)
        if filename == "minion":
            return os.path.join(RUNTIME_VARS.TMP_MINION_CONF_DIR, filename)
        if filename == "syndic_master":
            return os.path.join(RUNTIME_VARS.TMP_SYNDIC_MASTER_CONF_DIR, "master")
        if filename == "syndic":
            return os.path.join(RUNTIME_VARS.TMP_SYNDIC_MINION_CONF_DIR, "minion")
        if filename == "sub_minion":
            return os.path.join(RUNTIME_VARS.TMP_SUB_MINION_CONF_DIR, "minion")
        if filename == "mm_master":
            return os.path.join(RUNTIME_VARS.TMP_MM_CONF_DIR, "master")
        if filename == "mm_sub_master":
            return os.path.join(RUNTIME_VARS.TMP_MM_SUB_CONF_DIR, "master")
        if filename == "mm_minion":
            return os.path.join(RUNTIME_VARS.TMP_MM_MINION_CONF_DIR, "minion")
        if filename == "mm_sub_minion":
            return os.path.join(RUNTIME_VARS.TMP_MM_SUB_MINION_CONF_DIR, "minion")
        return os.path.join(RUNTIME_VARS.TMP_CONF_DIR, filename)

    @property
    def master_opts(self):
        """
        Return the options used for the master
        """
        return self.get_config("master")

    @property
    def minion_opts(self):
        """
        Return the options used for the minion
        """
        return self.get_config("minion")

    @property
    def sub_minion_opts(self):
        """
        Return the options used for the sub_minion
        """
        return self.get_config("sub_minion")

    @property
    def mm_master_opts(self):
        """
        Return the options used for the multimaster master
        """
        return self.get_config("mm_master")

    @property
    def mm_sub_master_opts(self):
        """
        Return the options used for the multimaster sub-master
        """
        return self.get_config("mm_sub_master")

    @property
    def mm_minion_opts(self):
        """
        Return the options used for the minion
        """
        return self.get_config("mm_minion")


class SaltClientTestCaseMixin(AdaptedConfigurationTestCaseMixin):
    """
    Mix-in class that provides a ``client`` attribute which returns a Salt
    :class:`LocalClient<salt:salt.client.LocalClient>`.

    .. code-block:: python

        class LocalClientTestCase(TestCase, SaltClientTestCaseMixin):

            def test_check_pub_data(self):
                just_minions = {'minions': ['m1', 'm2']}
                jid_no_minions = {'jid': '1234', 'minions': []}
                valid_pub_data = {'minions': ['m1', 'm2'], 'jid': '1234'}

                self.assertRaises(EauthAuthenticationError,
                                  self.client._check_pub_data, None)
                self.assertDictEqual({},
                    self.client._check_pub_data(just_minions),
                    'Did not handle lack of jid correctly')

                self.assertDictEqual(
                    {},
                    self.client._check_pub_data({'jid': '0'}),
                    'Passing JID of zero is not handled gracefully')
    """

    _salt_client_config_file_name_ = "master"

    @property
    def client(self):
        # Late import
        import salt.client

        if "runtime_client" not in RUNTIME_VARS.RUNTIME_CONFIGS:
            mopts = self.get_config(
                self._salt_client_config_file_name_, from_scratch=True
            )
            RUNTIME_VARS.RUNTIME_CONFIGS[
                "runtime_client"
            ] = salt.client.get_local_client(mopts=mopts)
        return RUNTIME_VARS.RUNTIME_CONFIGS["runtime_client"]


class SaltMultimasterClientTestCaseMixin(AdaptedConfigurationTestCaseMixin):
    """
    Mix-in class that provides a ``clients`` attribute which returns a list of Salt
    :class:`LocalClient<salt:salt.client.LocalClient>`.

    .. code-block:: python

        class LocalClientTestCase(TestCase, SaltMultimasterClientTestCaseMixin):

            def test_check_pub_data(self):
                just_minions = {'minions': ['m1', 'm2']}
                jid_no_minions = {'jid': '1234', 'minions': []}
                valid_pub_data = {'minions': ['m1', 'm2'], 'jid': '1234'}

                for client in self.clients:
                    self.assertRaises(EauthAuthenticationError,
                                      client._check_pub_data, None)
                    self.assertDictEqual({},
                        client._check_pub_data(just_minions),
                        'Did not handle lack of jid correctly')

                    self.assertDictEqual(
                        {},
                        client._check_pub_data({'jid': '0'}),
                        'Passing JID of zero is not handled gracefully')
    """

    _salt_client_config_file_name_ = "master"

    @property
    def clients(self):
        # Late import
        import salt.client

        if "runtime_clients" not in RUNTIME_VARS.RUNTIME_CONFIGS:
            RUNTIME_VARS.RUNTIME_CONFIGS["runtime_clients"] = OrderedDict()

        runtime_clients = RUNTIME_VARS.RUNTIME_CONFIGS["runtime_clients"]
        for master_id in ("mm-master", "mm-sub-master"):
            if master_id in runtime_clients:
                continue
            mopts = self.get_config(master_id.replace("-", "_"), from_scratch=True)
            runtime_clients[master_id] = salt.client.get_local_client(mopts=mopts)
        return runtime_clients


class ShellCaseCommonTestsMixin(CheckShellBinaryNameAndVersionMixin):

    _call_binary_expected_version_ = salt.version.__version__

    def test_salt_with_git_version(self):
        if getattr(self, "_call_binary_", None) is None:
            self.skipTest("'_call_binary_' not defined.")
        from salt.version import __version_info__, SaltStackVersion

        git = salt.utils.path.which("git")
        if not git:
            self.skipTest("The git binary is not available")
        opts = {
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
            "cwd": CODE_DIR,
        }
        if not salt.utils.platform.is_windows():
            opts["close_fds"] = True
        # Let's get the output of git describe
        process = subprocess.Popen(
            [git, "describe", "--tags", "--first-parent", "--match", "v[0-9]*"], **opts
        )
        out, err = process.communicate()
        if process.returncode != 0:
            process = subprocess.Popen(
                [git, "describe", "--tags", "--match", "v[0-9]*"], **opts
            )
            out, err = process.communicate()
        if not out:
            self.skipTest(
                "Failed to get the output of 'git describe'. "
                "Error: '{0}'".format(salt.utils.stringutils.to_str(err))
            )

        parsed_version = SaltStackVersion.parse(out)

        if parsed_version.info < __version_info__:
            self.skipTest(
                "We're likely about to release a new version. This test "
                "would fail. Parsed('{0}') < Expected('{1}')".format(
                    parsed_version.info, __version_info__
                )
            )
        elif parsed_version.info != __version_info__:
            self.skipTest(
                "In order to get the proper salt version with the "
                "git hash you need to update salt's local git "
                "tags. Something like: 'git fetch --tags' or "
                "'git fetch --tags upstream' if you followed "
                "salt's contribute documentation. The version "
                "string WILL NOT include the git hash."
            )
        out = "\n".join(self.run_script(self._call_binary_, "--version"))
        self.assertIn(parsed_version.string, out)


class _FixLoaderModuleMockMixinMroOrder(type):
    """
    This metaclass will make sure that LoaderModuleMockMixin will always come as the first
    base class in order for LoaderModuleMockMixin.setUp to actually run
    """

    def __new__(mcs, cls_name, cls_bases, cls_dict):
        if cls_name == "LoaderModuleMockMixin":
            return super(_FixLoaderModuleMockMixinMroOrder, mcs).__new__(
                mcs, cls_name, cls_bases, cls_dict
            )
        bases = list(cls_bases)
        for idx, base in enumerate(bases):
            if base.__name__ == "LoaderModuleMockMixin":
                bases.insert(0, bases.pop(idx))
                break

        # Create the class instance
        instance = super(_FixLoaderModuleMockMixinMroOrder, mcs).__new__(
            mcs, cls_name, tuple(bases), cls_dict
        )

        # Apply our setUp function decorator
        instance.setUp = LoaderModuleMockMixin.__setup_loader_modules_mocks__(
            instance.setUp
        )
        return instance


class LoaderModuleMockMixin(
    six.with_metaclass(_FixLoaderModuleMockMixinMroOrder, object)
):
    """
    This class will setup salt loader dunders.

    Please check `set_up_loader_mocks` above
    """

    # Define our setUp function decorator
    @staticmethod
    def __setup_loader_modules_mocks__(setup_func):
        @functools.wraps(setup_func)
        def wrapper(self):
            loader_modules_configs = self.setup_loader_modules()
            if not isinstance(loader_modules_configs, dict):
                raise RuntimeError(
                    "{}.setup_loader_modules() must return a dictionary where the keys are the "
                    "modules that require loader mocking setup and the values, the global module "
                    "variables for each of the module being mocked. For example '__salt__', "
                    "'__opts__', etc.".format(self.__class__.__name__)
                )

            salt_dunders = (
                "__opts__",
                "__salt__",
                "__runner__",
                "__context__",
                "__utils__",
                "__ext_pillar__",
                "__thorium__",
                "__states__",
                "__serializers__",
                "__ret__",
                "__grains__",
                "__pillar__",
                "__sdb__",
                # Proxy is commented out on purpose since some code in salt expects a NameError
                # and is most of the time not a required dunder
                # '__proxy__'
            )

            for module, module_globals in six.iteritems(loader_modules_configs):
                if not isinstance(module, types.ModuleType):
                    raise RuntimeError(
                        "The dictionary keys returned by {}.setup_loader_modules() "
                        "must be an imported module, not {}".format(
                            self.__class__.__name__, type(module)
                        )
                    )
                if not isinstance(module_globals, dict):
                    raise RuntimeError(
                        "The dictionary values returned by {}.setup_loader_modules() "
                        "must be a dictionary, not {}".format(
                            self.__class__.__name__, type(module_globals)
                        )
                    )

                module_blacklisted_dunders = module_globals.pop(
                    "blacklisted_dunders", ()
                )

                minion_funcs = {}
                if (
                    "__salt__" in module_globals
                    and module_globals["__salt__"] == "autoload"
                ):
                    if "__opts__" not in module_globals:
                        raise RuntimeError(
                            "You must provide '__opts__' on the {} module globals dictionary "
                            "to auto load the minion functions".format(module.__name__)
                        )
                    import salt.loader

                    ctx = {}
                    if "__utils__" not in module_globals:
                        utils = salt.loader.utils(
                            module_globals["__opts__"],
                            context=module_globals.get("__context__") or ctx,
                        )
                        module_globals["__utils__"] = utils
                    minion_funcs = salt.loader.minion_mods(
                        module_globals["__opts__"],
                        context=module_globals.get("__context__") or ctx,
                        utils=module_globals.get("__utils__"),
                    )
                    module_globals["__salt__"] = minion_funcs

                for dunder_name in salt_dunders:
                    if dunder_name not in module_globals:
                        if dunder_name in module_blacklisted_dunders:
                            continue
                        module_globals[dunder_name] = {}

                sys_modules = module_globals.pop("sys.modules", None)
                if sys_modules is not None:
                    if not isinstance(sys_modules, dict):
                        raise RuntimeError(
                            "'sys.modules' must be a dictionary not: {}".format(
                                type(sys_modules)
                            )
                        )
                    patcher = patch.dict(sys.modules, sys_modules)
                    patcher.start()

                    def cleanup_sys_modules(patcher, sys_modules):
                        patcher.stop()
                        del patcher
                        del sys_modules

                    self.addCleanup(cleanup_sys_modules, patcher, sys_modules)

                for key in module_globals:
                    if not hasattr(module, key):
                        if key in salt_dunders:
                            setattr(module, key, {})
                        else:
                            setattr(module, key, None)

                if module_globals:
                    patcher = patch.multiple(module, **module_globals)
                    patcher.start()

                    def cleanup_module_globals(patcher, module_globals):
                        patcher.stop()
                        del patcher
                        del module_globals

                    self.addCleanup(cleanup_module_globals, patcher, module_globals)

                if minion_funcs:
                    # Since we autoloaded the minion_funcs, let's namespace the functions with the globals
                    # used to patch above
                    import salt.utils

                    for func in minion_funcs:
                        minion_funcs[func] = salt.utils.functools.namespaced_function(
                            minion_funcs[func], module_globals, preserve_context=True
                        )
            return setup_func(self)

        return wrapper

    def setup_loader_modules(self):
        raise NotImplementedError(
            "'{}.setup_loader_modules()' must be implemented".format(
                self.__class__.__name__
            )
        )


class XMLEqualityMixin(object):
    def assertEqualXML(self, e1, e2):
        if six.PY3 and isinstance(e1, bytes):
            e1 = e1.decode("utf-8")
        if six.PY3 and isinstance(e2, bytes):
            e2 = e2.decode("utf-8")
        if isinstance(e1, six.string_types):
            e1 = etree.XML(e1)
        if isinstance(e2, six.string_types):
            e2 = etree.XML(e2)
        if e1.tag != e2.tag:
            return False
        if e1.text != e2.text:
            return False
        if e1.tail != e2.tail:
            return False
        if e1.attrib != e2.attrib:
            return False
        if len(e1) != len(e2):
            return False
        return all(self.assertEqualXML(c1, c2) for c1, c2 in zip(e1, e2))


class SaltReturnAssertsMixin(object):
    def assertReturnSaltType(self, ret):
        try:
            self.assertTrue(isinstance(ret, dict))
        except AssertionError:
            raise AssertionError(
                "{0} is not dict. Salt returned: {1}".format(type(ret).__name__, ret)
            )

    def assertReturnNonEmptySaltType(self, ret):
        self.assertReturnSaltType(ret)
        try:
            self.assertNotEqual(ret, {})
        except AssertionError:
            raise AssertionError(
                "{} is equal to {}. Salt returned an empty dictionary."
            )

    def __return_valid_keys(self, keys):
        if isinstance(keys, tuple):
            # If it's a tuple, turn it into a list
            keys = list(keys)
        elif isinstance(keys, six.string_types):
            # If it's a string, make it a one item list
            keys = [keys]
        elif not isinstance(keys, list):
            # If we've reached here, it's a bad type passed to keys
            raise RuntimeError("The passed keys need to be a list")
        return keys

    def __getWithinSaltReturn(self, ret, keys):
        self.assertReturnNonEmptySaltType(ret)
        ret_data = []
        for part in six.itervalues(ret):
            keys = self.__return_valid_keys(keys)
            okeys = keys[:]
            try:
                ret_item = part[okeys.pop(0)]
            except (KeyError, TypeError):
                raise AssertionError(
                    "Could not get ret{0} from salt's return: {1}".format(
                        "".join(["['{0}']".format(k) for k in keys]), part
                    )
                )
            while okeys:
                try:
                    ret_item = ret_item[okeys.pop(0)]
                except (KeyError, TypeError):
                    raise AssertionError(
                        "Could not get ret{0} from salt's return: {1}".format(
                            "".join(["['{0}']".format(k) for k in keys]), part
                        )
                    )
            ret_data.append(ret_item)
        return ret_data

    def assertSaltTrueReturn(self, ret):
        try:
            for saltret in self.__getWithinSaltReturn(ret, "result"):
                self.assertTrue(saltret)
        except AssertionError:
            log.info("Salt Full Return:\n{0}".format(pprint.pformat(ret)))
            try:
                raise AssertionError(
                    "{result} is not True. Salt Comment:\n{comment}".format(
                        **(next(six.itervalues(ret)))
                    )
                )
            except (AttributeError, IndexError):
                raise AssertionError(
                    "Failed to get result. Salt Returned:\n{0}".format(
                        pprint.pformat(ret)
                    )
                )

    def assertSaltFalseReturn(self, ret):
        try:
            for saltret in self.__getWithinSaltReturn(ret, "result"):
                self.assertFalse(saltret)
        except AssertionError:
            log.info("Salt Full Return:\n{0}".format(pprint.pformat(ret)))
            try:
                raise AssertionError(
                    "{result} is not False. Salt Comment:\n{comment}".format(
                        **(next(six.itervalues(ret)))
                    )
                )
            except (AttributeError, IndexError):
                raise AssertionError(
                    "Failed to get result. Salt Returned: {0}".format(ret)
                )

    def assertSaltNoneReturn(self, ret):
        try:
            for saltret in self.__getWithinSaltReturn(ret, "result"):
                self.assertIsNone(saltret)
        except AssertionError:
            log.info("Salt Full Return:\n{0}".format(pprint.pformat(ret)))
            try:
                raise AssertionError(
                    "{result} is not None. Salt Comment:\n{comment}".format(
                        **(next(six.itervalues(ret)))
                    )
                )
            except (AttributeError, IndexError):
                raise AssertionError(
                    "Failed to get result. Salt Returned: {0}".format(ret)
                )

    def assertInSaltComment(self, in_comment, ret):
        for saltret in self.__getWithinSaltReturn(ret, "comment"):
            self.assertIn(in_comment, saltret)

    def assertNotInSaltComment(self, not_in_comment, ret):
        for saltret in self.__getWithinSaltReturn(ret, "comment"):
            self.assertNotIn(not_in_comment, saltret)

    def assertSaltCommentRegexpMatches(self, ret, pattern):
        return self.assertInSaltReturnRegexpMatches(ret, pattern, "comment")

    def assertInSaltStateWarning(self, in_comment, ret):
        for saltret in self.__getWithinSaltReturn(ret, "warnings"):
            self.assertIn(in_comment, saltret)

    def assertNotInSaltStateWarning(self, not_in_comment, ret):
        for saltret in self.__getWithinSaltReturn(ret, "warnings"):
            self.assertNotIn(not_in_comment, saltret)

    def assertInSaltReturn(self, item_to_check, ret, keys):
        for saltret in self.__getWithinSaltReturn(ret, keys):
            self.assertIn(item_to_check, saltret)

    def assertNotInSaltReturn(self, item_to_check, ret, keys):
        for saltret in self.__getWithinSaltReturn(ret, keys):
            self.assertNotIn(item_to_check, saltret)

    def assertInSaltReturnRegexpMatches(self, ret, pattern, keys=()):
        for saltret in self.__getWithinSaltReturn(ret, keys):
            self.assertRegex(saltret, pattern)

    def assertSaltStateChangesEqual(self, ret, comparison, keys=()):
        keys = ["changes"] + self.__return_valid_keys(keys)
        for saltret in self.__getWithinSaltReturn(ret, keys):
            self.assertEqual(saltret, comparison)

    def assertSaltStateChangesNotEqual(self, ret, comparison, keys=()):
        keys = ["changes"] + self.__return_valid_keys(keys)
        for saltret in self.__getWithinSaltReturn(ret, keys):
            self.assertNotEqual(saltret, comparison)


def _fetch_events(q, opts):
    """
    Collect events and store them
    """

    def _clean_queue():
        log.info("Cleaning queue!")
        while not q.empty():
            queue_item = q.get()
            queue_item.task_done()

    atexit.register(_clean_queue)
    event = salt.utils.event.get_event("minion", sock_dir=opts["sock_dir"], opts=opts)

    # Wait for event bus to be connected
    while not event.connect_pull(30):
        time.sleep(1)

    # Notify parent process that the event bus is connected
    q.put("CONNECTED")

    while True:
        try:
            events = event.get_event(full=False)
        except Exception as exc:  # pylint: disable=broad-except
            # This is broad but we'll see all kinds of issues right now
            # if we drop the proc out from under the socket while we're reading
            log.exception("Exception caught while getting events %r", exc)
        q.put(events)


class SaltMinionEventAssertsMixin(object):
    """
    Asserts to verify that a given event was seen
    """

    @classmethod
    def setUpClass(cls):
        opts = copy.deepcopy(RUNTIME_VARS.RUNTIME_CONFIGS["minion"])
        cls.q = multiprocessing.Queue()
        cls.fetch_proc = salt.utils.process.SignalHandlingProcess(
            target=_fetch_events,
            args=(cls.q, opts),
            name="Process-{}-Queue".format(cls.__name__),
        )
        cls.fetch_proc.start()
        # Wait for the event bus to be connected
        msg = cls.q.get(block=True)
        if msg != "CONNECTED":
            # Just in case something very bad happens
            raise RuntimeError("Unexpected message in test's event queue")

    @classmethod
    def tearDownClass(cls):
        cls.fetch_proc.join()
        del cls.q
        del cls.fetch_proc

    def assertMinionEventFired(self, tag):
        # TODO
        raise salt.exceptions.NotImplemented("assertMinionEventFired() not implemented")

    def assertMinionEventReceived(self, desired_event, timeout=5, sleep_time=0.5):
        start = time.time()
        while True:
            try:
                event = self.q.get(False)
            except Empty:
                time.sleep(sleep_time)
                if time.time() - start >= timeout:
                    break
                continue
            if isinstance(event, dict):
                event.pop("_stamp")
            if desired_event == event:
                self.fetch_proc.terminate()
                return True
            if time.time() - start >= timeout:
                break
        self.fetch_proc.terminate()
        raise AssertionError(
            "Event {0} was not received by minion".format(desired_event)
        )
