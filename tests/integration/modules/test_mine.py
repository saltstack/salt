# -*- coding: utf-8 -*-
"""
Test the salt mine system
"""
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

import pprint
import time

# Import Salt libs
import salt.utils.platform

# Import Salt Testing libs
from tests.support.case import ModuleCase, ShellCase
from tests.support.runtests import RUNTIME_VARS


class MineTest(ModuleCase, ShellCase):
    """
    Test the mine system
    """

    def setUp(self):
        self.tgt = r"\*"
        if salt.utils.platform.is_windows():
            self.tgt = "*"
        self.wait_for_all_jobs()

    def test_get(self):
        """
        test mine.get and mine.update
        """
        assert self.run_function("mine.update", minion_tgt="minion")
        assert self.run_function("mine.update", minion_tgt="sub_minion")
        # Since the minion has mine_functions defined in its configuration,
        # mine.update will return True
        self.assertTrue(self.run_function("mine.get", ["minion", "test.ping"]))

    def test_get_allow_tgt(self):
        """
        test mine.get and mine.update using allow_tgt
        """
        assert self.run_function("mine.update", minion_tgt="minion")
        assert self.run_function("mine.update", minion_tgt="sub_minion")

        # sub_minion should be able to view test.arg data
        sub_min_ret = self.run_call(
            "mine.get {0} test.arg".format(self.tgt),
            config_dir=RUNTIME_VARS.TMP_SUB_MINION_CONF_DIR,
        )
        assert "            - isn't" in sub_min_ret

        # minion should not be able to view test.arg data
        min_ret = self.run_call("mine.get {0} test.arg".format(self.tgt))
        assert "            - isn't" not in min_ret

    def test_send_allow_tgt(self):
        """
        test mine.send with allow_tgt set
        """
        mine_name = "test_this"
        for minion in ["sub_minion", "minion"]:
            assert self.run_function(
                "mine.send",
                [mine_name, "mine_function=test.arg_clean", "one"],
                allow_tgt="sub_minion",
                minion_tgt=minion,
            )
        min_ret = self.run_call("mine.get {0} {1}".format(self.tgt, mine_name))
        sub_ret = self.run_call(
            "mine.get {0} {1}".format(self.tgt, mine_name),
            config_dir=RUNTIME_VARS.TMP_SUB_MINION_CONF_DIR,
        )

        # ensure we did get the mine_name mine function for sub_minion
        assert "            - one" in sub_ret
        # ensure we did not get the mine_name mine function for minion
        assert "            - one" not in min_ret

    def test_send_allow_tgt_compound(self):
        """
        test mine.send with allow_tgt set
        and using compound targeting
        """
        mine_name = "test_this_comp"
        for minion in ["sub_minion", "minion"]:
            assert self.run_function(
                "mine.send",
                [mine_name, "mine_function=test.arg_clean", "one"],
                allow_tgt="L@minion,sub_minion",
                allow_tgt_type="compound",
                minion_tgt=minion,
            )
        min_ret = self.run_call("mine.get {0} {1}".format(self.tgt, mine_name))
        sub_ret = self.run_call(
            "mine.get {0} {1}".format(self.tgt, mine_name),
            config_dir=RUNTIME_VARS.TMP_SUB_MINION_CONF_DIR,
        )

        # ensure we get the mine_name mine function for both minions
        for ret in [min_ret, sub_ret]:
            assert "            - one" in ret

    def test_send_allow_tgt_doesnotexist(self):
        """
        test mine.send with allow_tgt set when
        the minion defined in allow_tgt does
        not exist
        """
        mine_name = "mine_doesnotexist"
        for minion in ["sub_minion", "minion"]:
            assert self.run_function(
                "mine.send",
                [mine_name, "mine_function=test.arg_clean", "one"],
                allow_tgt="doesnotexist",
                minion_tgt=minion,
            )
        min_ret = self.run_call("mine.get {0} {1}".format(self.tgt, mine_name))
        sub_ret = self.run_call(
            "mine.get {0} {1}".format(self.tgt, mine_name),
            config_dir=RUNTIME_VARS.TMP_SUB_MINION_CONF_DIR,
        )

        # ensure we did not get the mine_name mine function for both minions
        for ret in [sub_ret, min_ret]:
            assert "            - one" not in ret

    def test_send(self):
        """
        test mine.send
        """
        self.assertFalse(self.run_function("mine.send", ["foo.__spam_and_cheese"]))
        self.assertTrue(
            self.run_function("mine.send", ["grains.items"], minion_tgt="minion",)
        )
        self.assertTrue(
            self.run_function("mine.send", ["grains.items"], minion_tgt="sub_minion",)
        )
        ret = self.run_function("mine.get", ["sub_minion", "grains.items"])
        self.assertEqual(ret["sub_minion"]["id"], "sub_minion")
        ret = self.run_function(
            "mine.get", ["minion", "grains.items"], minion_tgt="sub_minion"
        )
        self.assertEqual(ret["minion"]["id"], "minion")

    def test_mine_flush(self):
        """
        Test mine.flush
        """
        # TODO The calls to sleep were added in an attempt to make this tests
        # less flaky. If we still see it fail we need to look for a more robust
        # solution.
        for minion_id in ("minion", "sub_minion"):
            self.assertTrue(
                self.run_function("mine.send", ["grains.items"], minion_tgt=minion_id)
            )
            time.sleep(1)
        for minion_id in ("minion", "sub_minion"):
            ret = self.run_function(
                "mine.get", [minion_id, "grains.items"], minion_tgt=minion_id
            )
            self.assertEqual(ret[minion_id]["id"], minion_id)
            time.sleep(1)
        self.assertTrue(self.run_function("mine.flush", minion_tgt="minion"))
        time.sleep(1)
        ret_flushed = self.run_function("mine.get", ["*", "grains.items"])
        self.assertEqual(ret_flushed.get("minion", None), None)
        self.assertEqual(ret_flushed["sub_minion"]["id"], "sub_minion")

    def test_mine_delete(self):
        """
        Test mine.delete
        """
        self.assertTrue(
            self.run_function("mine.send", ["grains.items"], minion_tgt="minion")
        )
        self.wait_for_all_jobs(minions=("minion",))

        attempts = 10
        ret_grains = None
        while True:
            if ret_grains:
                break
            # Smoke testing that grains should now exist in the mine
            ret_grains = self.run_function(
                "mine.get", ["minion", "grains.items"], minion_tgt="minion"
            )
            if ret_grains and "minion" in ret_grains:
                break

            if attempts:
                attempts -= 1

            if attempts:
                time.sleep(1.5)
                continue

            self.fail(
                "'minion' was not found as a key of the 'mine.get' 'grains.items' call. Full return: {}".format(
                    pprint.pformat(ret_grains)
                )
            )

        self.assertEqual(
            ret_grains["minion"]["id"],
            "minion",
            msg="{} != minion, full return payload: {}".format(
                ret_grains["minion"]["id"], pprint.pformat(ret_grains)
            ),
        )
        self.assertTrue(
            self.run_function(
                "mine.send",
                ["test.arg", "foo=bar", "fnord=roscivs"],
                minion_tgt="minion",
            )
        )
        self.wait_for_all_jobs(minions=("minion",))
        ret_args = self.run_function("mine.get", ["minion", "test.arg"])
        expected = {
            "minion": {"args": [], "kwargs": {"fnord": "roscivs", "foo": "bar"}},
        }
        # Smoke testing that test.arg exists in the mine
        self.assertDictEqual(ret_args, expected)
        self.assertTrue(
            self.run_function("mine.send", ["test.echo", "foo"], minion_tgt="minion")
        )
        self.wait_for_all_jobs(minions=("minion",))
        ret_echo = self.run_function(
            "mine.get", ["minion", "test.echo"], minion_tgt="minion"
        )
        # Smoke testing that we were also able to set test.echo in the mine
        self.assertEqual(ret_echo["minion"], "foo")
        self.assertTrue(
            self.run_function("mine.delete", ["test.arg"], minion_tgt="minion")
        )
        self.wait_for_all_jobs(minions=("minion",))
        ret_arg_deleted = self.run_function(
            "mine.get", ["minion", "test.arg"], minion_tgt="minion"
        )
        # Now comes the real test - did we obliterate test.arg from the mine?
        # We could assert this a different way, but there shouldn't be any
        # other tests that are setting this mine value, so this should
        # definitely avoid any race conditions.
        self.assertFalse(
            ret_arg_deleted.get("minion", {}).get("kwargs", {}).get("fnord", None)
            == "roscivs",
            '{} contained "fnord":"roscivs", which should be gone'.format(
                ret_arg_deleted,
            ),
        )
        ret_echo_stays = self.run_function(
            "mine.get", ["minion", "test.echo"], minion_tgt="minion"
        )
        # Of course, one more health check - we want targeted removal.
        # This isn't horseshoes or hand grenades - test.arg should go away
        # but test.echo should still be available.
        self.assertEqual(ret_echo_stays["minion"], "foo")
