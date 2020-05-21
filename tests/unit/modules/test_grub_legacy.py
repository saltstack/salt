# -*- coding: utf-8 -*-
"""
    :codeauthor: Rupesh Tare <rupesht@saltstack.com>
"""

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

import errno

# Import Salt Libs
import salt.modules.grub_legacy as grub_legacy
import salt.utils.stringutils
from salt.exceptions import CommandExecutionError

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, mock_open, patch
from tests.support.unit import TestCase


class GrublegacyTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.modules.grub_legacy
    """

    def setup_loader_modules(self):
        return {grub_legacy: {}}

    def test_version(self):
        """
        Test for Return server version from grub --version
        """
        mock = MagicMock(return_value="out")
        with patch.dict(grub_legacy.__salt__, {"cmd.run": mock}):
            self.assertEqual(grub_legacy.version(), "out")

    def test_conf(self):
        """
        Test for Parse GRUB conf file
        """
        file_data = IOError(errno.EACCES, "Permission denied")
        with patch(
            "salt.utils.files.fopen", mock_open(read_data=file_data)
        ), patch.object(grub_legacy, "_detect_conf", return_value="A"):
            self.assertRaises(CommandExecutionError, grub_legacy.conf)

        file_data = salt.utils.stringutils.to_str("\n".join(["#", "A B C D,E,F G H"]))
        with patch(
            "salt.utils.files.fopen", mock_open(read_data=file_data)
        ), patch.object(grub_legacy, "_detect_conf", return_value="A"):
            conf = grub_legacy.conf()
            assert conf == {"A": "B C D,E,F G H", "stanzas": []}, conf
