# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

import os

# Import salt libs
import salt.utils.files
import salt.utils.platform

# Import Salt Testing libs
from tests.support.case import ModuleCase


class StdTest(ModuleCase):
    """
    Test standard client calls
    """

    def setUp(self):
        self.TIMEOUT = 600 if salt.utils.platform.is_windows() else 10

    def test_cli(self):
        """
        Test cli function
        """
        cmd_iter = self.client.cmd_cli("minion", "test.ping", timeout=20,)
        for ret in cmd_iter:
            self.assertTrue(ret["minion"])

        # make sure that the iter waits for long running jobs too
        cmd_iter = self.client.cmd_cli("minion", "test.sleep", [6], timeout=20,)
        num_ret = 0
        for ret in cmd_iter:
            num_ret += 1
            self.assertTrue(ret["minion"])
        assert num_ret > 0

        # ping a minion that doesn't exist, to make sure that it doesn't hang forever
        # create fake minion
        key_file = os.path.join(self.master_opts["pki_dir"], "minions", "footest")
        # touch the file
        with salt.utils.files.fopen(key_file, "a"):
            pass
        # ping that minion and ensure it times out
        try:
            cmd_iter = self.client.cmd_cli("footest", "test.ping", timeout=20,)
            num_ret = 0
            for ret in cmd_iter:
                num_ret += 1
                self.assertTrue(ret["minion"])
            assert num_ret == 0
        finally:
            os.unlink(key_file)

    def test_iter(self):
        """
        test cmd_iter
        """
        cmd_iter = self.client.cmd_iter("minion", "test.ping",)
        for ret in cmd_iter:
            self.assertTrue(ret["minion"])

    def test_iter_no_block(self):
        """
        test cmd_iter_no_block
        """
        cmd_iter = self.client.cmd_iter_no_block("minion", "test.ping",)
        for ret in cmd_iter:
            if ret is None:
                continue
            self.assertTrue(ret["minion"])

    def test_batch(self):
        """
        test cmd_batch
        """
        cmd_batch = self.client.cmd_batch("minion", "test.ping",)
        for ret in cmd_batch:
            self.assertTrue(ret["minion"])

    def test_batch_raw(self):
        """
        test cmd_batch with raw option
        """
        cmd_batch = self.client.cmd_batch("minion", "test.ping", raw=True,)
        for ret in cmd_batch:
            self.assertTrue(ret["data"]["success"])

    def test_full_returns(self):
        """
        test cmd_iter
        """
        ret = self.client.cmd_full_return("minion", "test.ping", timeout=20,)
        self.assertIn("minion", ret)
        self.assertEqual({"ret": True, "success": True}, ret["minion"])

    def test_disconnected_return(self):
        """
        Test return/messaging on a disconnected minion
        """
        test_ret = {"ret": "Minion did not return. [No response]", "out": "no_return"}

        # Create a minion key, but do not start the "fake" minion. This mimics
        # a disconnected minion.
        key_file = os.path.join(self.master_opts["pki_dir"], "minions", "disconnected")
        with salt.utils.files.fopen(key_file, "a"):
            pass

        # ping disconnected minion and ensure it times out and returns with correct message
        try:
            cmd_iter = self.client.cmd_cli(
                "disconnected", "test.ping", show_timeout=True
            )
            num_ret = 0
            for ret in cmd_iter:
                num_ret += 1
                self.assertEqual(ret["disconnected"]["ret"], test_ret["ret"])
                self.assertEqual(ret["disconnected"]["out"], test_ret["out"])

            # Ensure that we entered the loop above
            self.assertEqual(num_ret, 1)

        finally:
            os.unlink(key_file)

    def test_missing_minion_list(self):
        """
        test cmd with missing minion in nodegroup
        """
        ret = self.client.cmd(
            "minion,ghostminion", "test.ping", tgt_type="list", timeout=self.TIMEOUT
        )
        self.assertIn("minion", ret)
        self.assertIn("ghostminion", ret)
        self.assertEqual(True, ret["minion"])
        self.assertEqual("Minion did not return. [No response]", ret["ghostminion"])

    def test_missing_minion_nodegroup(self):
        """
        test cmd with missing minion in nodegroup
        """
        ret = self.client.cmd("missing_minion", "test.ping", tgt_type="nodegroup")
        self.assertIn("minion", ret)
        self.assertIn("ghostminion", ret)
        self.assertEqual(True, ret["minion"])
        self.assertEqual("Minion did not return. [No response]", ret["ghostminion"])
