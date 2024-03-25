"""
Tests for various minion timeouts
"""

import os
import sys

import pytest

import salt.utils.platform
from tests.support.case import ShellCase


@pytest.mark.windows_whitelisted
class MinionTimeoutTestCase(ShellCase):
    """
    Test minion timing functions
    """

    @pytest.mark.slow_test
    def test_long_running_job(self):
        """
        Test that we will wait longer than the job timeout for a minion to
        return.
        """
        # Launch the command
        sleep_length = 30
        if salt.utils.platform.is_windows():
            popen_kwargs = {"env": dict(os.environ, PYTHONPATH=";".join(sys.path))}
        else:
            popen_kwargs = None
        ret = self.run_salt(
            f"minion test.sleep {sleep_length}",
            timeout=90,
            catch_stderr=True,
            popen_kwargs=popen_kwargs,
        )
        self.assertTrue(
            isinstance(ret[0], list),
            f"Return is not a list. Minion may have returned error: {ret}",
        )
        self.assertEqual(len(ret[0]), 2, f"Standard out wrong length {ret}")
        self.assertTrue(
            "True" in ret[0][1],
            "Minion did not return True after {} seconds. ret={}".format(
                sleep_length, ret
            ),
        )
