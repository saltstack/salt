import hashlib

import pytest

import salt.modules.pdbedit as pdbedit
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


def _md4_supported():
    try:
        hashlib.new("md4", "".encode("utf-16le"))
        return True
    except ValueError:
        return False


pytestmark = [
    pytest.mark.skipif(
        not _md4_supported(),
        reason="Hash type md4 is unsupported on this OS",
    ),
]


class PdbeditTestCase(TestCase, LoaderModuleMockMixin):
    """
    TestCase for salt.modules.pdbedit module
    """

    def setup_loader_modules(self):
        return {pdbedit: {}}

    def test_version(self):
        """
        Test salt.modules.__virtual__'s handling of pdbedit versions
        """
        mock_bad_ver = MagicMock(return_value="Ver 1.1a")
        mock_old_ver = MagicMock(return_value="Version 1.0.0")
        mock_exa_ver = MagicMock(return_value="Version 4.5.0")
        mock_new_ver = MagicMock(return_value="Version 4.9.2")
        mock_deb_ver = MagicMock(return_value="Version 4.5.16-Debian")

        # NOTE: no pdbedit installed
        with patch("salt.utils.path.which", MagicMock(return_value=None)):
            ret = pdbedit.__virtual__()
            self.assertEqual(ret, (False, "pdbedit command is not available"))

        # NOTE: pdbedit is not returning a valid version
        with patch(
            "salt.utils.path.which", MagicMock(return_value="/opt/local/bin/pdbedit")
        ), patch("salt.modules.cmdmod.run", mock_bad_ver):
            ret = pdbedit.__virtual__()
            self.assertEqual(
                ret, (False, "pdbedit -V returned an unknown version format")
            )

        # NOTE: pdbedit is too old
        with patch(
            "salt.utils.path.which", MagicMock(return_value="/opt/local/bin/pdbedit")
        ), patch("salt.modules.cmdmod.run", mock_old_ver):
            ret = pdbedit.__virtual__()
            self.assertEqual(
                ret, (False, "pdbedit is to old, 4.5.0 or newer is required")
            )

        # NOTE: pdbedit is exactly 4.5.0
        with patch(
            "salt.utils.path.which", MagicMock(return_value="/opt/local/bin/pdbedit")
        ), patch("salt.modules.cmdmod.run", mock_exa_ver):
            ret = pdbedit.__virtual__()
            self.assertEqual(ret, "pdbedit")

        # NOTE: pdbedit is debian version
        with patch(
            "salt.utils.path.which", MagicMock(return_value="/opt/local/bin/pdbedit")
        ), patch("salt.modules.cmdmod.run", mock_deb_ver):
            ret = pdbedit.__virtual__()
            self.assertEqual(ret, "pdbedit")

        # NOTE: pdbedit is newer than 4.5.0
        with patch(
            "salt.utils.path.which", MagicMock(return_value="/opt/local/bin/pdbedit")
        ), patch("salt.modules.cmdmod.run", mock_new_ver):
            ret = pdbedit.__virtual__()
            self.assertEqual(ret, "pdbedit")

    def test_generate_nt_hash(self):
        """
        Test salt.modules.pdbedit.generate_nt_hash
        """
        ret = pdbedit.generate_nt_hash("supersecret")
        assert b"43239E3A0AF748020D5B426A4977D7E5" == ret
