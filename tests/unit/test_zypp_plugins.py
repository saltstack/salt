"""
    :codeauthor: Bo Maryniuk <bo@suse.de>
"""

import imp  # pylint: disable=deprecated-module
import os

import pytest

from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase

try:
    from zypp_plugin import BogusIO

    HAS_ZYPP_PLUGIN = True
except ImportError:
    HAS_ZYPP_PLUGIN = False

BUILTINS_OPEN = "builtins.open"

ZYPPNOTIFY_FILE = os.path.sep.join(
    os.path.dirname(__file__).split(os.path.sep)[:-2]
    + ["scripts", "suse", "zypper", "plugins", "commit", "zyppnotify"]
)


@pytest.mark.skipif(not HAS_ZYPP_PLUGIN, reason="zypp_plugin is missing.")
class ZyppPluginsTestCase(TestCase):
    """
    Test shipped libzypp plugins.
    """

    @pytest.mark.skipif(
        not os.path.exists(ZYPPNOTIFY_FILE),
        reason=f"Required file '{ZYPPNOTIFY_FILE}' does not exist.",
    )
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
