# -*- coding: utf-8 -*-
"""
    :codeauthor: Bo Maryniuk <bo@suse.de>
"""

# Import Python Libs
from __future__ import absolute_import

import imp
import os
import sys

from tests.support.mock import MagicMock, patch

# Import Salt Testing Libs
from tests.support.unit import TestCase
from zypp_plugin import BogusIO

if sys.version_info >= (3,):
    BUILTINS_OPEN = "builtins.open"
else:
    BUILTINS_OPEN = "__builtin__.open"

ZYPPNOTIFY_FILE = os.path.sep.join(
    os.path.dirname(__file__).split(os.path.sep)[:-2]
    + ["scripts", "suse", "zypper", "plugins", "commit", "zyppnotify"]
)


class ZyppPluginsTestCase(TestCase):
    """
    Test shipped libzypp plugins.
    """

    def test_drift_detector(self):
        """
        Test drift detector for a correct cookie file.
        Returns:

        """
        zyppnotify = imp.load_source("zyppnotify", ZYPPNOTIFY_FILE)
        drift = zyppnotify.DriftDetector()
        drift._get_mtime = MagicMock(return_value=123)
        drift._get_checksum = MagicMock(return_value="deadbeef")
        bogus_io = BogusIO()
        with patch(BUILTINS_OPEN, bogus_io):
            drift.PLUGINEND(None, None)
        self.assertEqual(str(bogus_io), "deadbeef 123\n")
        self.assertEqual(bogus_io.mode, "w")
        self.assertEqual(bogus_io.path, "/var/cache/salt/minion/rpmdb.cookie")
