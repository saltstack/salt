# -*- coding: utf-8 -*-
"""
Tests for minion blackout
"""

# Import Python libs
from __future__ import absolute_import

import logging
import os
import textwrap
import time

# Import Salt libs
import salt.utils.files

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.runtests import RUNTIME_VARS

log = logging.getLogger(__name__)


class MinionBlackoutTestCase(ModuleCase):
    """
    Test minion blackout functionality
    """

    @classmethod
    def setUpClass(cls):
        cls.top_pillar = os.path.join(RUNTIME_VARS.TMP_PILLAR_TREE, "top.sls")
        cls.blackout_pillar = os.path.join(RUNTIME_VARS.TMP_PILLAR_TREE, "blackout.sls")

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.top_pillar):
            os.unlink(cls.top_pillar)
        del cls.top_pillar
        if os.path.exists(cls.blackout_pillar):
            os.unlink(cls.blackout_pillar)
        del cls.blackout_pillar

    def setUp(self):
        with salt.utils.files.fopen(self.top_pillar, "w") as wfh:
            wfh.write(
                textwrap.dedent(
                    """\
                base:
                  '*':
                    - blackout
                """
                )
            )
        with salt.utils.files.fopen(self.blackout_pillar, "w") as wfh:
            wfh.write("minion_blackout: False")
        self.addCleanup(self.cleanup_blackout_pillar)

    def tearDown(self):
        self.end_blackout()
        # Be sure to also refresh the sub_minion pillar
        self.run_function("saltutil.refresh_pillar", minion_tgt="sub_minion")
        timeout = 120
        if not self.wait_for_blackout(end=True, tgt="sub_minion", timeout=timeout):
            raise Exception(
                "Minion did not exit blackout mode after {} seconds".format(timeout)
            )
        self.wait_for_all_jobs()

    def cleanup_blackout_pillar(self):
        if os.path.exists(self.top_pillar):
            os.unlink(self.top_pillar)
        if os.path.exists(self.blackout_pillar):
            os.unlink(self.blackout_pillar)

    def begin_blackout(self, blackout_data="minion_blackout: True"):
        """
        setup minion blackout mode
        """
        log.info("Entering minion blackout...")
        self.wait_for_all_jobs()
        with salt.utils.files.fopen(self.blackout_pillar, "w") as wfh:
            wfh.write(blackout_data)
        ret = self.run_function("saltutil.refresh_pillar", timeout=30)
        timeout = 120
        if not self.wait_for_blackout(timeout=timeout):
            raise Exception(
                "Minion did not enter blackout mode after {} seconds".format(timeout)
            )
        log.info("Entered minion blackout.")

    def wait_for_blackout(self, end=False, tgt="minion", timeout=120, sleep=0.3):
        """
        Wait for blackout mode to start or end.
        """
        start = time.time()
        while time.time() - start <= timeout:
            ret = self.run_function(
                "pillar.get", minion_tgt=tgt, arg=["minion_blackout"], timeout=30,
            )
            if end:
                if str(ret).find("Minion in blackout mode") == -1:
                    return True
            else:
                if str(ret).find("Minion in blackout mode") != -1:
                    return True
            time.sleep(sleep)
        return False

    def end_blackout(self):
        """
        takedown minion blackout mode
        """
        log.info("Exiting minion blackout...")
        with salt.utils.files.fopen(self.blackout_pillar, "w") as wfh:
            wfh.write("minion_blackout: False\n")
        self.run_function("saltutil.refresh_pillar")
        timeout = 120
        if not self.wait_for_blackout(end=True, timeout=timeout):
            raise Exception(
                "Minion did not exit blackout mode after {} seconds".format(timeout)
            )
        self.wait_for_all_jobs()
        log.info("Exited minion blackout.")

    def test_blackout(self):
        """
        Test that basic minion blackout functionality works
        """
        try:
            self.begin_blackout()
            blackout_ret = self.run_function("test.ping")
            self.assertIn("Minion in blackout mode.", blackout_ret)
        finally:
            self.end_blackout()

        ret = self.run_function("test.ping")
        self.assertEqual(ret, True)

    def test_blackout_whitelist(self):
        """
        Test that minion blackout whitelist works
        """
        self.begin_blackout(
            textwrap.dedent(
                """\
            minion_blackout: True
            minion_blackout_whitelist:
              - test.ping
              - test.fib
            """
            )
        )

        ping_ret = self.run_function("test.ping")
        self.assertEqual(ping_ret, True)

        fib_ret = self.run_function("test.fib", [7])
        self.assertTrue(isinstance(fib_ret, list))
        self.assertEqual(fib_ret[0], 13)

    def test_blackout_nonwhitelist(self):
        """
        Test that minion refuses to run non-whitelisted functions during
        blackout whitelist
        """
        self.begin_blackout(
            textwrap.dedent(
                """\
            minion_blackout: True
            minion_blackout_whitelist:
              - test.ping
              - test.fib
            """
            )
        )

        state_ret = self.run_function("state.apply")
        self.assertIn("Minion in blackout mode.", state_ret)

        cloud_ret = self.run_function("cloud.query", ["list_nodes_full"])
        self.assertIn("Minion in blackout mode.", cloud_ret)
