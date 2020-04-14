# -*- coding: utf-8 -*-
"""
Tests for various minion timeouts
"""

# Import Python libs
from __future__ import absolute_import

import os
import sys

import salt.utils.platform

# Import Salt Testing libs
from tests.support.case import ShellCase


class MinionTimeoutTestCase(ShellCase):
    """
    Test minion timing functions
    """

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
            "minion test.sleep {0}".format(sleep_length),
            timeout=90,
            catch_stderr=True,
            popen_kwargs=popen_kwargs,
        )
        self.assertTrue(
            isinstance(ret[0], list),
            "Return is not a list. Minion" " may have returned error: {0}".format(ret),
        )
        self.assertEqual(len(ret[0]), 2, "Standard out wrong length {}".format(ret))
        self.assertTrue(
            "True" in ret[0][1],
            "Minion did not return True after "
            "{0} seconds. ret={1}".format(sleep_length, ret),
        )
