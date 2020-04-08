# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import salt libs
import salt.utils.timed_subprocess as timed_subprocess

# Import Salt Testing libs
from tests.support.unit import TestCase


class TestTimedSubprocess(TestCase):
    def test_timedproc_with_shell_true_and_list_args(self):
        """
        This test confirms the fix for the regression introduced in 1f7d50d.
        The TimedProc dunder init would result in a traceback if the args were
        passed as a list and shell=True was set.
        """
        p = timed_subprocess.TimedProc(["echo", "foo"], shell=True)
        del p  # Don't need this anymore
