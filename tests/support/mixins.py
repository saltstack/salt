"""
    :codeauthor: Pedro Algarvio (pedro@algarvio.me)

    =============
    Class Mix-Ins
    =============

    Some reusable class Mixins
"""

import atexit
import copy
import functools
import logging
import multiprocessing
import os
import pprint
import queue
import subprocess
import tempfile
import time
import xml.etree.ElementTree as etree

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
from salt.utils.immutabletypes import freeze
from salt.utils.verify import verify_env
from saltfactories.utils import random_string
from tests.support.paths import CODE_DIR
from tests.support.pytest.loader import LoaderModuleMock
from tests.support.runtests import RUNTIME_VARS

log = logging.getLogger(__name__)


class CheckShellBinaryNameAndVersionMixin:
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


class AdaptedConfigurationTestCaseMixin:

    __slots__ = ()

    @staticmethod
    def get_temp_config(config_for, **config_overrides):
        rootdir = config_overrides.get(
            "root_dir", tempfile.mkdtemp(dir=RUNTIME_VARS.TMP)
        )
        if not os.path.exists(rootdir):
            os.makedirs(rootdir)
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
            minion_id = (
                config_overrides.get("id")
                or config_overrides.get("minion_id")
                or cdict.get("id")
                or cdict.get("minion_id")
                or random_string("temp-minion-")
            )
            config_overrides["minion_id"] = config_overrides["id"] = minion_id
            rdict = salt.config.apply_minion_config(
                config_overrides, cdict, cache_minion_id=False, minion_id=minion_id
            )

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
                    AdaptedConfigurationTestCaseMixin.get_config_file_path(config_for),
                    cache_minion_id=False,
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
                "Failed to get the output of 'git describe'. Error: '{}'".format(
                    salt.utils.stringutils.to_str(err)
                )
            )

        parsed_version = SaltStackVersion.parse(out)

        if parsed_version.info < __version_info__:
            self.skipTest(
                "We're likely about to release a new version. This test "
                "would fail. Parsed('{}') < Expected('{}')".format(
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
            return super().__new__(mcs, cls_name, cls_bases, cls_dict)
        bases = list(cls_bases)
        for idx, base in enumerate(bases):
            if base.__name__ == "LoaderModuleMockMixin":
                bases.insert(0, bases.pop(idx))
                break

        # Create the class instance
        instance = super().__new__(mcs, cls_name, tuple(bases), cls_dict)

        # Apply our setUp function decorator
        instance.setUp = LoaderModuleMockMixin.__setup_loader_modules_mocks__(
            instance.setUp
        )
        return instance


class LoaderModuleMockMixin(metaclass=_FixLoaderModuleMockMixinMroOrder):
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
                    "{}.setup_loader_modules() must return a dictionary where the keys"
                    " are the modules that require loader mocking setup and the values,"
                    " the global module variables for each of the module being mocked."
                    " For example '__salt__', '__opts__', etc.".format(
                        self.__class__.__name__
                    )
                )

            mocker = LoaderModuleMock(loader_modules_configs)
            mocker.start()
            self.addCleanup(mocker.stop)
            return setup_func(self)

        return wrapper

    def setup_loader_modules(self):
        raise NotImplementedError(
            "'{}.setup_loader_modules()' must be implemented".format(
                self.__class__.__name__
            )
        )


class XMLEqualityMixin:
    def assertEqualXML(self, e1, e2):
        if isinstance(e1, bytes):
            e1 = e1.decode("utf-8")
        if isinstance(e2, bytes):
            e2 = e2.decode("utf-8")
        if isinstance(e1, str):
            e1 = etree.XML(e1)
        if isinstance(e2, str):
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


class SaltReturnAssertsMixin:
    def assertReturnSaltType(self, ret):
        try:
            self.assertTrue(isinstance(ret, dict))
        except AssertionError:
            raise AssertionError(
                "{} is not dict. Salt returned: {}".format(type(ret).__name__, ret)
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
        elif isinstance(keys, str):
            # If it's a string, make it a one item list
            keys = [keys]
        elif not isinstance(keys, list):
            # If we've reached here, it's a bad type passed to keys
            raise RuntimeError("The passed keys need to be a list")
        return keys

    def __getWithinSaltReturn(self, ret, keys):
        self.assertReturnNonEmptySaltType(ret)
        ret_data = []
        for part in ret.values():
            keys = self.__return_valid_keys(keys)
            okeys = keys[:]
            try:
                ret_item = part[okeys.pop(0)]
            except (KeyError, TypeError):
                raise AssertionError(
                    "Could not get ret{} from salt's return: {}".format(
                        "".join(["['{}']".format(k) for k in keys]), part
                    )
                )
            while okeys:
                try:
                    ret_item = ret_item[okeys.pop(0)]
                except (KeyError, TypeError):
                    raise AssertionError(
                        "Could not get ret{} from salt's return: {}".format(
                            "".join(["['{}']".format(k) for k in keys]), part
                        )
                    )
            ret_data.append(ret_item)
        return ret_data

    def assertSaltTrueReturn(self, ret):
        try:
            for saltret in self.__getWithinSaltReturn(ret, "result"):
                self.assertTrue(saltret)
        except AssertionError:
            log.info("Salt Full Return:\n%s", pprint.pformat(ret))
            try:
                raise AssertionError(
                    "{result} is not True. Salt Comment:\n{comment}".format(
                        **(next(iter(ret.values())))
                    )
                )
            except (AttributeError, IndexError):
                raise AssertionError(
                    "Failed to get result. Salt Returned:\n{}".format(
                        pprint.pformat(ret)
                    )
                )

    def assertSaltFalseReturn(self, ret):
        try:
            for saltret in self.__getWithinSaltReturn(ret, "result"):
                self.assertFalse(saltret)
        except AssertionError:
            log.info("Salt Full Return:\n%s", pprint.pformat(ret))
            try:
                raise AssertionError(
                    "{result} is not False. Salt Comment:\n{comment}".format(
                        **(next(iter(ret.values())))
                    )
                )
            except (AttributeError, IndexError):
                raise AssertionError(
                    "Failed to get result. Salt Returned: {}".format(ret)
                )

    def assertSaltNoneReturn(self, ret):
        try:
            for saltret in self.__getWithinSaltReturn(ret, "result"):
                self.assertIsNone(saltret)
        except AssertionError:
            log.info("Salt Full Return:\n%s", pprint.pformat(ret))
            try:
                raise AssertionError(
                    "{result} is not None. Salt Comment:\n{comment}".format(
                        **(next(iter(ret.values())))
                    )
                )
            except (AttributeError, IndexError):
                raise AssertionError(
                    "Failed to get result. Salt Returned: {}".format(ret)
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
    with salt.utils.event.get_event(
        "minion", sock_dir=opts["sock_dir"], opts=opts
    ) as event:

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


class SaltMinionEventAssertsMixin:
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
            except queue.Empty:
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
            "Event {} was not received by minion".format(desired_event)
        )
