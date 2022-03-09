"""
    :codeauthor: Bo Maryniuk <bo@suse.de>
"""
import imp
import os

from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase, skipIf

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


@skipIf(not HAS_ZYPP_PLUGIN, "zypp_plugin is missing.")
class ZyppPluginsTestCase(TestCase):
    """
    Test shipped libzypp plugins.
    """

    @skipIf(
        not os.path.exists(ZYPPNOTIFY_FILE),
        "Required file '{}' does not exist.".format(ZYPPNOTIFY_FILE),
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
