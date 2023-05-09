"""
mac_utils tests
"""
import os
import plistlib
import subprocess
import xml.parsers.expat

import pytest

import salt.modules.cmdmod as cmd
import salt.utils.mac_utils as mac_utils
import salt.utils.platform
from salt.exceptions import CommandExecutionError, SaltInvocationError
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, MockTimedProc, mock_open, patch
from tests.support.unit import TestCase


@pytest.mark.skip_unless_on_darwin
class MacUtilsTestCase(TestCase, LoaderModuleMockMixin):
    """
    test mac_utils salt utility
    """

    def setup_loader_modules(self):
        return {mac_utils: {}}

    def test_execute_return_success_not_supported(self):
        """
        test execute_return_success function
        command not supported
        """
        mock_cmd = MagicMock(
            return_value={"retcode": 0, "stdout": "not supported", "stderr": "error"}
        )
        with patch.object(mac_utils, "_run_all", mock_cmd):
            self.assertRaises(
                CommandExecutionError, mac_utils.execute_return_success, "dir c:\\"
            )

    def test_execute_return_success_command_failed(self):
        """
        test execute_return_success function
        command failed
        """
        mock_cmd = MagicMock(
            return_value={"retcode": 1, "stdout": "spongebob", "stderr": "error"}
        )
        with patch.object(mac_utils, "_run_all", mock_cmd):
            self.assertRaises(
                CommandExecutionError, mac_utils.execute_return_success, "dir c:\\"
            )

    def test_execute_return_success_command_succeeded(self):
        """
        test execute_return_success function
        command succeeded
        """
        mock_cmd = MagicMock(return_value={"retcode": 0, "stdout": "spongebob"})
        with patch.object(mac_utils, "_run_all", mock_cmd):
            ret = mac_utils.execute_return_success("dir c:\\")
            self.assertEqual(ret, True)

    def test_execute_return_result_command_failed(self):
        """
        test execute_return_result function
        command failed
        """
        mock_cmd = MagicMock(
            return_value={"retcode": 1, "stdout": "spongebob", "stderr": "squarepants"}
        )
        with patch.object(mac_utils, "_run_all", mock_cmd):
            self.assertRaises(
                CommandExecutionError, mac_utils.execute_return_result, "dir c:\\"
            )

    def test_execute_return_result_command_succeeded(self):
        """
        test execute_return_result function
        command succeeded
        """
        mock_cmd = MagicMock(return_value={"retcode": 0, "stdout": "spongebob"})
        with patch.object(mac_utils, "_run_all", mock_cmd):
            ret = mac_utils.execute_return_result("dir c:\\")
            self.assertEqual(ret, "spongebob")

    def test_parse_return_space(self):
        """
        test parse_return function
        space after colon
        """
        self.assertEqual(
            mac_utils.parse_return("spongebob: squarepants"), "squarepants"
        )

    def test_parse_return_new_line(self):
        """
        test parse_return function
        new line after colon
        """
        self.assertEqual(
            mac_utils.parse_return("spongebob:\nsquarepants"), "squarepants"
        )

    def test_parse_return_no_delimiter(self):
        """
        test parse_return function
        no delimiter
        """
        self.assertEqual(mac_utils.parse_return("squarepants"), "squarepants")

    def test_validate_enabled_on(self):
        """
        test validate_enabled function
        test on
        """
        self.assertEqual(mac_utils.validate_enabled("On"), "on")

    def test_validate_enabled_off(self):
        """
        test validate_enabled function
        test off
        """
        self.assertEqual(mac_utils.validate_enabled("Off"), "off")

    def test_validate_enabled_bad_string(self):
        """
        test validate_enabled function
        test bad string
        """
        self.assertRaises(SaltInvocationError, mac_utils.validate_enabled, "bad string")

    def test_validate_enabled_non_zero(self):
        """
        test validate_enabled function
        test non zero
        """
        for x in range(1, 179, 3):
            self.assertEqual(mac_utils.validate_enabled(x), "on")

    def test_validate_enabled_0(self):
        """
        test validate_enabled function
        test 0
        """
        self.assertEqual(mac_utils.validate_enabled(0), "off")

    def test_validate_enabled_true(self):
        """
        test validate_enabled function
        test True
        """
        self.assertEqual(mac_utils.validate_enabled(True), "on")

    def test_validate_enabled_false(self):
        """
        test validate_enabled function
        test False
        """
        self.assertEqual(mac_utils.validate_enabled(False), "off")

    def test_launchctl(self):
        """
        test launchctl function
        """
        mock_cmd = MagicMock(
            return_value={"retcode": 0, "stdout": "success", "stderr": "none"}
        )
        with patch("salt.utils.mac_utils.__salt__", {"cmd.run_all": mock_cmd}):
            ret = mac_utils.launchctl("enable", "org.salt.minion")
            self.assertEqual(ret, True)

    def test_launchctl_return_stdout(self):
        """
        test launchctl function and return stdout
        """
        mock_cmd = MagicMock(
            return_value={"retcode": 0, "stdout": "success", "stderr": "none"}
        )
        with patch("salt.utils.mac_utils.__salt__", {"cmd.run_all": mock_cmd}):
            ret = mac_utils.launchctl("enable", "org.salt.minion", return_stdout=True)
            self.assertEqual(ret, "success")

    def test_launchctl_error(self):
        """
        test launchctl function returning an error
        """
        mock_cmd = MagicMock(
            return_value={"retcode": 1, "stdout": "failure", "stderr": "test failure"}
        )
        error = (
            "Failed to enable service:\n"
            "stdout: failure\n"
            "stderr: test failure\n"
            "retcode: 1"
        )
        with patch("salt.utils.mac_utils.__salt__", {"cmd.run_all": mock_cmd}):
            try:
                mac_utils.launchctl("enable", "org.salt.minion")
            except CommandExecutionError as exc:
                self.assertEqual(exc.message, error)

    @patch("salt.utils.path.os_walk")
    @patch("os.path.exists")
    def test_available_services_result(self, mock_exists, mock_os_walk):
        """
        test available_services results are properly formed dicts.
        """
        results = {"/Library/LaunchAgents": ["com.apple.lla1.plist"]}
        mock_os_walk.side_effect = _get_walk_side_effects(results)
        mock_exists.return_value = True

        plists = [{"Label": "com.apple.lla1"}]
        ret = _run_available_services(plists)

        file_path = os.sep + os.path.join(
            "Library", "LaunchAgents", "com.apple.lla1.plist"
        )
        if salt.utils.platform.is_windows():
            file_path = "c:" + file_path

        expected = {
            "com.apple.lla1": {
                "file_name": "com.apple.lla1.plist",
                "file_path": file_path,
                "plist": plists[0],
            }
        }
        self.assertEqual(ret, expected)

    @patch("salt.utils.path.os_walk")
    @patch("os.path.exists")
    @patch("os.listdir")
    @patch("os.path.isdir")
    def test_available_services_dirs(
        self, mock_isdir, mock_listdir, mock_exists, mock_os_walk
    ):
        """
        test available_services checks all of the expected dirs.
        """
        results = {
            "/Library/LaunchAgents": ["com.apple.lla1.plist"],
            "/Library/LaunchDaemons": ["com.apple.lld1.plist"],
            "/System/Library/LaunchAgents": ["com.apple.slla1.plist"],
            "/System/Library/LaunchDaemons": ["com.apple.slld1.plist"],
            "/Users/saltymcsaltface/Library/LaunchAgents": ["com.apple.uslla1.plist"],
        }

        mock_os_walk.side_effect = _get_walk_side_effects(results)
        mock_listdir.return_value = ["saltymcsaltface"]
        mock_isdir.return_value = True
        mock_exists.return_value = True

        plists = [
            {"Label": "com.apple.lla1"},
            {"Label": "com.apple.lld1"},
            {"Label": "com.apple.slla1"},
            {"Label": "com.apple.slld1"},
            {"Label": "com.apple.uslla1"},
        ]
        ret = _run_available_services(plists)

        self.assertEqual(len(ret), 5)

    @patch("salt.utils.path.os_walk")
    @patch("os.path.exists")
    @patch("plistlib.load")
    def test_available_services_broken_symlink(
        self, mock_read_plist, mock_exists, mock_os_walk
    ):
        """
        test available_services when it encounters a broken symlink.
        """
        results = {
            "/Library/LaunchAgents": ["com.apple.lla1.plist", "com.apple.lla2.plist"]
        }
        mock_os_walk.side_effect = _get_walk_side_effects(results)
        mock_exists.side_effect = [True, False]

        plists = [{"Label": "com.apple.lla1"}]
        ret = _run_available_services(plists)

        file_path = os.sep + os.path.join(
            "Library", "LaunchAgents", "com.apple.lla1.plist"
        )
        if salt.utils.platform.is_windows():
            file_path = "c:" + file_path

        expected = {
            "com.apple.lla1": {
                "file_name": "com.apple.lla1.plist",
                "file_path": file_path,
                "plist": plists[0],
            }
        }
        self.assertEqual(ret, expected)

    @patch("salt.utils.path.os_walk")
    @patch("os.path.exists")
    @patch("salt.utils.mac_utils.__salt__")
    def test_available_services_binary_plist(
        self,
        mock_run,
        mock_exists,
        mock_os_walk,
    ):
        """
        test available_services handles binary plist files.
        """
        results = {"/Library/LaunchAgents": ["com.apple.lla1.plist"]}
        mock_os_walk.side_effect = _get_walk_side_effects(results)
        mock_exists.return_value = True

        plists = [{"Label": "com.apple.lla1"}]

        file_path = os.sep + os.path.join(
            "Library", "LaunchAgents", "com.apple.lla1.plist"
        )
        if salt.utils.platform.is_windows():
            file_path = "c:" + file_path

        ret = _run_available_services(plists)

        expected = {
            "com.apple.lla1": {
                "file_name": "com.apple.lla1.plist",
                "file_path": file_path,
                "plist": plists[0],
            }
        }
        self.assertEqual(ret, expected)

    @patch("salt.utils.path.os_walk")
    @patch("os.path.exists")
    def test_available_services_invalid_file(self, mock_exists, mock_os_walk):
        """
        test available_services excludes invalid files.
        The py3 plistlib raises an InvalidFileException when a plist
        file cannot be parsed.
        """
        results = {"/Library/LaunchAgents": ["com.apple.lla1.plist"]}
        mock_os_walk.side_effect = _get_walk_side_effects(results)
        mock_exists.return_value = True

        plists = [{"Label": "com.apple.lla1"}]

        mock_load = MagicMock()
        mock_load.side_effect = plistlib.InvalidFileException
        with patch("salt.utils.files.fopen", mock_open()):
            with patch("plistlib.load", mock_load):
                ret = mac_utils._available_services()

        self.assertEqual(len(ret), 0)

    @patch("salt.utils.mac_utils.__salt__")
    @patch("salt.utils.path.os_walk")
    @patch("os.path.exists")
    def test_available_services_expat_error(self, mock_exists, mock_os_walk, mock_run):
        """
        test available_services excludes files with expat errors.

        Poorly formed XML will raise an ExpatError on py2. It will
        also be raised by some almost-correct XML on py3.
        """
        results = {"/Library/LaunchAgents": ["com.apple.lla1.plist"]}
        mock_os_walk.side_effect = _get_walk_side_effects(results)
        mock_exists.return_value = True

        file_path = os.sep + os.path.join(
            "Library", "LaunchAgents", "com.apple.lla1.plist"
        )
        if salt.utils.platform.is_windows():
            file_path = "c:" + file_path

        mock_load = MagicMock()
        mock_load.side_effect = xml.parsers.expat.ExpatError
        with patch("salt.utils.files.fopen", mock_open()):
            with patch("plistlib.load", mock_load):
                ret = mac_utils._available_services()

        self.assertEqual(len(ret), 0)

    @patch("salt.utils.mac_utils.__salt__")
    @patch("salt.utils.path.os_walk")
    @patch("os.path.exists")
    def test_available_services_value_error(self, mock_exists, mock_os_walk, mock_run):
        """
        test available_services excludes files with ValueErrors.
        """
        results = {"/Library/LaunchAgents": ["com.apple.lla1.plist"]}
        mock_os_walk.side_effect = _get_walk_side_effects(results)
        mock_exists.return_value = True

        file_path = os.sep + os.path.join(
            "Library", "LaunchAgents", "com.apple.lla1.plist"
        )
        if salt.utils.platform.is_windows():
            file_path = "c:" + file_path

        mock_load = MagicMock()
        mock_load.side_effect = ValueError
        with patch("salt.utils.files.fopen", mock_open()):
            with patch("plistlib.load", mock_load):
                ret = mac_utils._available_services()

        self.assertEqual(len(ret), 0)

    def test_bootout_retcode_36_success(self):
        """
        Make sure that if we run a `launchctl bootout` cmd and it returns
        36 that we treat it as a success.
        """
        proc = MagicMock(
            return_value=MockTimedProc(stdout=None, stderr=None, returncode=36)
        )
        with patch("salt.utils.timed_subprocess.TimedProc", proc):
            with patch(
                "salt.utils.mac_utils.__salt__", {"cmd.run_all": cmd._run_all_quiet}
            ):
                ret = mac_utils.launchctl("bootout", "org.salt.minion")
        self.assertEqual(ret, True)

    def test_bootout_retcode_99_fail(self):
        """
        Make sure that if we run a `launchctl bootout` cmd and it returns
        something other than 0 or 36 that we treat it as a fail.
        """
        error = (
            "Failed to bootout service:\n"
            "stdout: failure\n"
            "stderr: test failure\n"
            "retcode: 99"
        )
        proc = MagicMock(
            return_value=MockTimedProc(
                stdout=b"failure", stderr=b"test failure", returncode=99
            )
        )
        with patch("salt.utils.timed_subprocess.TimedProc", proc):
            with patch(
                "salt.utils.mac_utils.__salt__", {"cmd.run_all": cmd._run_all_quiet}
            ):
                try:
                    mac_utils.launchctl("bootout", "org.salt.minion")
                except CommandExecutionError as exc:
                    self.assertEqual(exc.message, error)

    def test_not_bootout_retcode_36_fail(self):
        """
        Make sure that if we get a retcode 36 on non bootout cmds
        that we still get a failure.
        """
        error = (
            "Failed to bootstrap service:\n"
            "stdout: failure\n"
            "stderr: test failure\n"
            "retcode: 36"
        )
        proc = MagicMock(
            return_value=MockTimedProc(
                stdout=b"failure", stderr=b"test failure", returncode=36
            )
        )
        with patch("salt.utils.timed_subprocess.TimedProc", proc):
            with patch(
                "salt.utils.mac_utils.__salt__", {"cmd.run_all": cmd._run_all_quiet}
            ):
                try:
                    mac_utils.launchctl("bootstrap", "org.salt.minion")
                except CommandExecutionError as exc:
                    self.assertEqual(exc.message, error)

    def test_git_is_stub(self):
        mock_check_call = MagicMock(
            side_effect=subprocess.CalledProcessError(cmd="", returncode=2)
        )
        with patch("salt.utils.mac_utils.subprocess.check_call", mock_check_call):
            self.assertEqual(mac_utils.git_is_stub(), True)

    @patch("salt.utils.mac_utils.subprocess.check_call")
    def test_git_is_not_stub(self, mock_check_call):
        self.assertEqual(mac_utils.git_is_stub(), False)


def _get_walk_side_effects(results):
    """
    Data generation helper function for service tests.
    """

    def walk_side_effect(*args, **kwargs):
        return [(args[0], [], results.get(args[0], []))]

    return walk_side_effect


def _run_available_services(plists):
    mock_load = MagicMock()
    mock_load.side_effect = plists
    with patch("salt.utils.files.fopen", mock_open()):
        with patch("plistlib.load", mock_load):
            ret = mac_utils._available_services()
    return ret
