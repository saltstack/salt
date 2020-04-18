# -*- coding: utf-8 -*-
"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
import salt.modules.rsync as rsync
from salt.exceptions import CommandExecutionError, SaltInvocationError

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class RsyncTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.modules.rsync
    """

    def setup_loader_modules(self):
        return {rsync: {}}

    def test_rsync(self):
        """
        Test for rsync files from src to dst
        """
        with patch.dict(
            rsync.__salt__, {"config.option": MagicMock(return_value=False)}
        ):
            self.assertRaises(SaltInvocationError, rsync.rsync, "", "")

        with patch.dict(
            rsync.__salt__,
            {
                "config.option": MagicMock(return_value="A"),
                "cmd.run_all": MagicMock(side_effect=[OSError(1, "f"), "A"]),
            },
        ):
            with patch.object(rsync, "_check", return_value=["A"]):
                self.assertRaises(CommandExecutionError, rsync.rsync, "a", "b")

                self.assertEqual(rsync.rsync("src", "dst"), "A")

    def test_version(self):
        """
        Test for return rsync version
        """
        mock = MagicMock(side_effect=[OSError(1, "f"), "A B C\n"])
        with patch.dict(rsync.__salt__, {"cmd.run_stdout": mock}):
            self.assertRaises(CommandExecutionError, rsync.version)

            self.assertEqual(rsync.version(), "C")

    def test_rsync_excludes_list(self):
        """
        Test for rsync files from src to dst with a list of excludes
        """
        mock = {
            "config.option": MagicMock(return_value=False),
            "cmd.run_all": MagicMock(),
        }
        with patch.dict(rsync.__salt__, mock):
            rsync.rsync("src", "dst", exclude=["test/one", "test/two"])
        mock["cmd.run_all"].assert_called_once_with(
            [
                "rsync",
                "-avz",
                "--exclude",
                "test/one",
                "--exclude",
                "test/two",
                "src",
                "dst",
            ],
            python_shell=False,
        )

    def test_rsync_excludes_str(self):
        """
        Test for rsync files from src to dst with one exclude
        """
        mock = {
            "config.option": MagicMock(return_value=False),
            "cmd.run_all": MagicMock(),
        }
        with patch.dict(rsync.__salt__, mock):
            rsync.rsync("src", "dst", exclude="test/one")
        mock["cmd.run_all"].assert_called_once_with(
            ["rsync", "-avz", "--exclude", "test/one", "src", "dst"],
            python_shell=False,
        )
