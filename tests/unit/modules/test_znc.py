"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""


import salt.modules.znc as znc
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class ZncTestCase(TestCase, LoaderModuleMockMixin):
    """
    TestCase for salt.modules.znc
    """

    def setup_loader_modules(self):
        return {znc: {}}

    # 'buildmod' function tests: 1

    def test_buildmod(self):
        """
        Tests build module using znc-buildmod
        """
        with patch("os.path.exists", MagicMock(return_value=False)):
            self.assertEqual(
                znc.buildmod("modules.cpp"),
                "Error: The file (modules.cpp) does not exist.",
            )

    def test_buildmod_module(self):
        """
        Tests build module using znc-buildmod
        """
        mock = MagicMock(return_value="SALT")
        with patch.dict(znc.__salt__, {"cmd.run": mock}), patch(
            "os.path.exists", MagicMock(return_value=True)
        ):
            self.assertEqual(znc.buildmod("modules.cpp"), "SALT")

    # 'dumpconf' function tests: 1

    def test_dumpconf(self):
        """
        Tests write the active configuration state to config file
        """
        mock = MagicMock(return_value="SALT")
        with patch.dict(znc.__salt__, {"ps.pkill": mock}), patch.object(
            znc, "signal", MagicMock()
        ):
            self.assertEqual(znc.dumpconf(), "SALT")

    # 'rehashconf' function tests: 1

    def test_rehashconf(self):
        """
        Tests rehash the active configuration state from config file
        """
        mock = MagicMock(return_value="SALT")
        with patch.dict(znc.__salt__, {"ps.pkill": mock}), patch.object(
            znc, "signal", MagicMock()
        ):
            self.assertEqual(znc.rehashconf(), "SALT")

    # 'version' function tests: 1

    def test_version(self):
        """
        Tests return server version from znc --version
        """
        mock = MagicMock(return_value="ZNC 1.2 - http://znc.in")
        with patch.dict(znc.__salt__, {"cmd.run": mock}):
            self.assertEqual(znc.version(), "ZNC 1.2")
