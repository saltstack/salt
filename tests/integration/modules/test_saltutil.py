# -*- coding: utf-8 -*-
"""
Integration tests for the saltutil module.
"""

from __future__ import absolute_import, print_function, unicode_literals

import os
import shutil
import textwrap
import threading
import time

import pytest
import salt.config
import salt.defaults.events
import salt.utils.event
import salt.utils.files
import salt.utils.stringutils
from tests.support.case import ModuleCase
from tests.support.helpers import flaky, slowTest
from tests.support.runtests import RUNTIME_VARS
from tests.support.unit import skipIf


@pytest.mark.windows_whitelisted
@pytest.mark.usefixtures("salt_sub_minion")
class SaltUtilModuleTest(ModuleCase):
    """
    Testcase for the saltutil execution module
    """

    @classmethod
    def setUpClass(cls):
        # Whell functions, on a minion, must run with the master running
        # along side the minion.
        # We copy the master config to the minion's configuration directory just
        # for this test since the test suite master and minion(s) do not share the
        # same configuration directory
        src = os.path.join(RUNTIME_VARS.TMP_CONF_DIR, "master")
        dst = os.path.join(RUNTIME_VARS.TMP_MINION_CONF_DIR, "master")
        cls.copied_master_config_file = None
        if not os.path.exists(dst):
            shutil.copyfile(src, dst)
            cls.copied_master_config_file = dst

    @classmethod
    def tearDownClass(cls):
        if cls.copied_master_config_file and os.path.exists(
            cls.copied_master_config_file
        ):
            os.unlink(cls.copied_master_config_file)
        cls.copied_master_config_file = None

    def setUp(self):
        self.run_function("saltutil.refresh_pillar")

    # Tests for the wheel function

    @slowTest
    def test_wheel_just_function(self):
        """
        Tests using the saltutil.wheel function when passing only a function.
        """
        # Wait for the pillar refresh to kick in, so that grains are ready to go
        time.sleep(3)
        ret = self.run_function("saltutil.wheel", ["minions.connected"])
        self.assertIn("minion", ret["return"])
        self.assertIn("sub_minion", ret["return"])

    @slowTest
    def test_wheel_with_arg(self):
        """
        Tests using the saltutil.wheel function when passing a function and an arg.
        """
        ret = self.run_function("saltutil.wheel", ["key.list", "minion"])
        self.assertEqual(ret["return"], {})

    @slowTest
    def test_wheel_no_arg_raise_error(self):
        """
        Tests using the saltutil.wheel function when passing a function that requires
        an arg, but one isn't supplied.
        """
        self.assertRaises(TypeError, "saltutil.wheel", ["key.list"])

    @slowTest
    def test_wheel_with_kwarg(self):
        """
        Tests using the saltutil.wheel function when passing a function and a kwarg.
        This function just generates a key pair, but doesn't do anything with it. We
        just need this for testing purposes.
        """
        ret = self.run_function("saltutil.wheel", ["key.gen"], keysize=1024)
        self.assertIn("pub", ret["return"])
        self.assertIn("priv", ret["return"])


@pytest.mark.windows_whitelisted
class SyncGrainsTest(ModuleCase):
    @slowTest
    def test_sync_grains(self):
        ret = self.run_function("saltutil.sync_grains")
        self.assertEqual(ret, [])


@pytest.mark.windows_whitelisted
class SaltUtilSyncModuleTest(ModuleCase):
    """
    Testcase for the saltutil sync execution module
    """

    def setUp(self):
        whitelist = {
            "modules": [],
        }
        self.run_function("saltutil.sync_all", extmod_whitelist=whitelist)

    def tearDown(self):
        self.run_function("saltutil.sync_all")

    @slowTest
    def test_sync_all(self):
        """
        Test syncing all ModuleCase
        """
        expected_return = {
            "engines": [],
            "clouds": [],
            "grains": [],
            "beacons": [],
            "utils": [],
            "returners": [],
            "modules": [
                "modules.depends_versioned",
                "modules.depends_versionless",
                "modules.mantest",
                "modules.override_test",
                "modules.runtests_decorators",
                "modules.runtests_helpers",
                "modules.salttest",
            ],
            "renderers": [],
            "log_handlers": [],
            "matchers": [],
            "states": [],
            "sdb": [],
            "proxymodules": [],
            "executors": [],
            "output": [],
            "thorium": [],
            "serializers": [],
        }
        ret = self.run_function("saltutil.sync_all")
        self.assertEqual(ret, expected_return)

    @slowTest
    def test_sync_all_whitelist(self):
        """
        Test syncing all ModuleCase with whitelist
        """
        expected_return = {
            "engines": [],
            "clouds": [],
            "grains": [],
            "beacons": [],
            "utils": [],
            "returners": [],
            "modules": ["modules.salttest"],
            "renderers": [],
            "log_handlers": [],
            "matchers": [],
            "states": [],
            "sdb": [],
            "proxymodules": [],
            "executors": [],
            "output": [],
            "thorium": [],
            "serializers": [],
        }
        ret = self.run_function(
            "saltutil.sync_all", extmod_whitelist={"modules": ["salttest"]}
        )
        self.assertEqual(ret, expected_return)

    @slowTest
    def test_sync_all_blacklist(self):
        """
        Test syncing all ModuleCase with blacklist
        """
        expected_return = {
            "engines": [],
            "clouds": [],
            "grains": [],
            "beacons": [],
            "utils": [],
            "returners": [],
            "modules": [
                "modules.mantest",
                "modules.override_test",
                "modules.runtests_helpers",
                "modules.salttest",
            ],
            "renderers": [],
            "log_handlers": [],
            "matchers": [],
            "states": [],
            "sdb": [],
            "proxymodules": [],
            "executors": [],
            "output": [],
            "thorium": [],
            "serializers": [],
        }
        ret = self.run_function(
            "saltutil.sync_all",
            extmod_blacklist={
                "modules": [
                    "runtests_decorators",
                    "depends_versioned",
                    "depends_versionless",
                ]
            },
        )
        self.assertEqual(ret, expected_return)

    @slowTest
    def test_sync_all_blacklist_and_whitelist(self):
        """
        Test syncing all ModuleCase with whitelist and blacklist
        """
        expected_return = {
            "engines": [],
            "clouds": [],
            "grains": [],
            "beacons": [],
            "utils": [],
            "returners": [],
            "executors": [],
            "modules": [],
            "renderers": [],
            "log_handlers": [],
            "matchers": [],
            "states": [],
            "sdb": [],
            "proxymodules": [],
            "output": [],
            "thorium": [],
            "serializers": [],
        }
        ret = self.run_function(
            "saltutil.sync_all",
            extmod_whitelist={"modules": ["runtests_decorators"]},
            extmod_blacklist={"modules": ["runtests_decorators"]},
        )
        self.assertEqual(ret, expected_return)


@skipIf(True, "Pillar refresh test is flaky. Skipping for now.")
@pytest.mark.windows_whitelisted
class SaltUtilSyncPillarTest(ModuleCase):
    """
    Testcase for the saltutil sync pillar module
    """

    class WaitForEvent(threading.Thread):
        def __init__(self, opts, event_tag):
            self.__eventer = salt.utils.event.get_event(
                "minion", opts=opts, listen=True
            )
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
        """
        test pillar refresh module
        """
        pillar_key = "itworked"

        pre_pillar = self.run_function("pillar.raw")
        self.assertNotIn(pillar_key, pre_pillar.get(pillar_key, "didnotwork"))

        with salt.utils.files.fopen(
            os.path.join(RUNTIME_VARS.TMP_PILLAR_TREE, "add_pillar.sls"), "w"
        ) as fp:
            fp.write(salt.utils.stringutils.to_str("{0}: itworked".format(pillar_key)))

        with salt.utils.files.fopen(
            os.path.join(RUNTIME_VARS.TMP_PILLAR_TREE, "top.sls"), "w"
        ) as fp:
            fp.write(
                textwrap.dedent(
                    """\
                     base:
                       '*':
                         - add_pillar
                     """
                )
            )

        self.run_function("saltutil.refresh_pillar")

        pillar = False
        timeout = time.time() + 30
        while not pillar:
            post_pillar = self.run_function("pillar.raw")
            try:
                self.assertIn(pillar_key, post_pillar.get(pillar_key, "didnotwork"))
                pillar = True
            except AssertionError:
                if time.time() > timeout:
                    self.assertIn(pillar_key, post_pillar.get(pillar_key, "didnotwork"))
                continue

        post_pillar = self.run_function("pillar.raw")
        self.assertIn(pillar_key, post_pillar.get(pillar_key, "didnotwork"))

    def test_pillar_refresh_sync(self):
        """
        test pillar refresh module with sync enabled
        """
        pillar_key = "itworked_sync"

        pre_pillar = self.run_function("pillar.raw")
        self.assertNotIn(pillar_key, pre_pillar.get(pillar_key, "didnotwork_sync"))

        with salt.utils.files.fopen(
            os.path.join(RUNTIME_VARS.TMP_PILLAR_TREE, "add_pillar_sync.sls"), "w"
        ) as fp:
            fp.write(
                salt.utils.stringutils.to_str("{0}: itworked_sync".format(pillar_key))
            )

        with salt.utils.files.fopen(
            os.path.join(RUNTIME_VARS.TMP_PILLAR_TREE, "top.sls"), "w"
        ) as fp:
            fp.write(
                textwrap.dedent(
                    """\
                     base:
                       '*':
                         - add_pillar_sync
                     """
                )
            )

        opts = self.run_function("test.get_opts")
        wait = self.WaitForEvent(
            opts, salt.defaults.events.MINION_PILLAR_REFRESH_COMPLETE
        )
        wait.start()
        self.run_function("saltutil.refresh_pillar", wait=True)
        while wait.is_alive():
            time.sleep(1)
        self.assertTrue(wait.is_complete())

        pillar = False
        timeout = time.time() + 30
        while not pillar:
            post_pillar = self.run_function("pillar.raw")
            try:
                self.assertIn(
                    pillar_key, post_pillar.get(pillar_key, "didnotwork_sync")
                )
                pillar = True
            except AssertionError:
                if time.time() > timeout:
                    self.assertIn(
                        pillar_key, post_pillar.get(pillar_key, "didnotwork_sync")
                    )
                continue

        post_pillar = self.run_function("pillar.raw")
        self.assertIn(pillar_key, post_pillar.get(pillar_key, "didnotwork_sync"))

    def tearDown(self):
        for filename in os.listdir(RUNTIME_VARS.TMP_PILLAR_TREE):
            os.remove(os.path.join(RUNTIME_VARS.TMP_PILLAR_TREE, filename))
