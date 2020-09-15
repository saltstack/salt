"""
Tests for the cron state
"""

import logging
import pprint

import salt.utils.platform
from tests.support.case import ModuleCase
from tests.support.helpers import skip_if_binaries_missing, slowTest
from tests.support.unit import skipIf

log = logging.getLogger(__name__)


@skipIf(salt.utils.platform.is_windows(), "minion is windows")
@skip_if_binaries_missing("crontab")
class CronTest(ModuleCase):
    """
    Validate the file state
    """

    def setUp(self):
        """
        Setup
        """
        ret = self.run_state("user.present", name="test_cron_user")
        assert ret

    def tearDown(self):
        """
        Teardown
        """
        # Remove cron file
        if salt.utils.platform.is_freebsd():
            self.run_function("cmd.run", cmd="crontab -u test_cron_user -rf")
        else:
            self.run_function("cmd.run", cmd="crontab -u test_cron_user -r")

        # Delete user
        self.run_state("user.absent", name="test_cron_user")

    @slowTest
    def test_managed(self):
        """
        file.managed
        """
        ret = self.run_state(
            "cron.file", name="salt://issue-46881/cron", user="test_cron_user"
        )
        assert ret
        self.assertIn(
            "cron_|-salt://issue-46881/cron_|-salt://issue-46881/cron_|-file",
            ret,
            msg="Assertion failed. run_state retuned: {}".format(pprint.pformat(ret)),
        )
        state = ret["cron_|-salt://issue-46881/cron_|-salt://issue-46881/cron_|-file"]
        self.assertIn(
            "changes",
            state,
            msg="Assertion failed. ret: {}".format(pprint.pformat(ret)),
        )
        self.assertIn(
            "diff",
            state["changes"],
            msg="Assertion failed. ret: {}".format(pprint.pformat(ret)),
        )
        expected = "--- \n+++ \n@@ -1 +1,2 @@\n-\n+# Lines below here are managed by Salt, do not edit\n+@hourly touch /tmp/test-file\n"
        self.assertEqual(
            expected,
            state["changes"]["diff"],
            msg="Assertion failed. ret: {}".format(pprint.pformat(ret)),
        )
