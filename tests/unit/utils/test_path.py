import ntpath
import os
import platform
import posixpath
import sys
import tempfile
import types

import pytest

import salt.utils.compat
import salt.utils.path
import salt.utils.platform
from salt.exceptions import CommandNotFoundError
from tests.support.mock import patch
from tests.support.unit import TestCase


class PathJoinTestCase(TestCase):

    PLATFORM_FUNC = platform.system
    BUILTIN_MODULES = sys.builtin_module_names

    NIX_PATHS = (
        (("/", "key"), "/key"),
        (("/etc/salt", "/etc/salt/pki"), "/etc/salt/etc/salt/pki"),
        (("/usr/local", "/etc/salt/pki"), "/usr/local/etc/salt/pki"),
    )

    WIN_PATHS = (
        (("c:", "temp", "foo"), "c:\\temp\\foo"),
        (("c:", r"\temp", r"\foo"), "c:\\temp\\foo"),
        (("c:\\", r"\temp", r"\foo"), "c:\\temp\\foo"),
        ((r"c:\\", r"\temp", r"\foo"), "c:\\temp\\foo"),
        (("c:", r"\temp", r"\foo", "bar"), "c:\\temp\\foo\\bar"),
        (("c:", r"\temp", r"\foo\bar"), "c:\\temp\\foo\\bar"),
    )

    @pytest.mark.skip(reason="Skipped until properly mocked")
    @pytest.mark.skip_on_windows
    def test_nix_paths(self):
        for idx, (parts, expected) in enumerate(self.NIX_PATHS):
            path = salt.utils.path.join(*parts)
            assert f"{idx}: {path}" == f"{idx}: {expected}"

    @pytest.mark.skip(reason="Skipped until properly mocked")
    @pytest.mark.skip_unless_on_windows
    def test_windows_paths(self):
        for idx, (parts, expected) in enumerate(self.WIN_PATHS):
            path = salt.utils.path.join(*parts)
            assert f"{idx}: {path}" == f"{idx}: {expected}"

    @pytest.mark.skip(reason="Skipped until properly mocked")
    @pytest.mark.skip_on_windows
    def test_windows_paths_patched_path_module(self):
        self.__patch_path()

        try:
            for idx, (parts, expected) in enumerate(self.WIN_PATHS):
                path = salt.utils.path.join(*parts)
                assert f"{idx}: {path}" == f"{idx}: {expected}"
        finally:
            self.__unpatch_path()

    @pytest.mark.skip_on_windows(reason="*nix-only test")
    def test_mixed_unicode_and_binary(self):
        """
        This tests joining paths that contain a mix of components with unicode
        strings and non-unicode strings with the unicode characters as binary.

        This is no longer something we need to concern ourselves with in
        Python 3, but the test should nonetheless pass on Python 3. Really what
        we're testing here is that we don't get a UnicodeDecodeError when
        running on Python 2.
        """
        a = "/foo/bar"
        b = "Д"
        expected = "/foo/bar/\u0414"
        actual = salt.utils.path.join(a, b)
        assert actual == expected

    def __patch_path(self):
        modules = list(self.BUILTIN_MODULES[:])
        modules.pop(modules.index("posix"))
        modules.append("nt")

        code = """'''Salt unittest loaded NT module'''"""
        module = types.ModuleType("nt")
        exec(code, module.__dict__)
        sys.modules["nt"] = module

        sys.builtin_module_names = modules
        platform.system = lambda: "windows"

        for module in (ntpath, os, os.path, tempfile):
            salt.utils.compat.reload(module)

    def __unpatch_path(self):
        del sys.modules["nt"]
        sys.builtin_module_names = self.BUILTIN_MODULES[:]
        platform.system = self.PLATFORM_FUNC

        for module in (posixpath, os, os.path, tempfile, platform):
            salt.utils.compat.reload(module)


class PathTestCase(TestCase):
    def test_which_bin(self):
        ret = salt.utils.path.which_bin("str")
        assert ret is None

        test_exes = ["ls", "echo"]
        with patch("salt.utils.path.which", return_value="/tmp/dummy_path"):
            ret = salt.utils.path.which_bin(test_exes)
            assert ret == "/tmp/dummy_path"

            ret = salt.utils.path.which_bin([])
            assert ret is None

        with patch("salt.utils.path.which", return_value=""):
            ret = salt.utils.path.which_bin(test_exes)
            assert ret is None

    def test_sanitize_win_path(self):
        assert (
            salt.utils.path.sanitize_win_path("\\windows\\system")
            == "\\windows\\system"
        )
        assert (
            salt.utils.path.sanitize_win_path("\\bo:g|us\\p?at*h>")
            == "\\bo_g_us\\p_at_h_"
        )

    def test_check_or_die(self):
        with pytest.raises(CommandNotFoundError):
            salt.utils.path.check_or_die(None)

        with patch("salt.utils.path.which", return_value=False):
            with pytest.raises(CommandNotFoundError):
                salt.utils.path.check_or_die("FAKE COMMAND")

    def test_join(self):
        with patch(
            "salt.utils.platform.is_windows", return_value=False
        ) as is_windows_mock:
            assert not is_windows_mock.return_value
            expected_path = os.path.join(os.sep + "a", "b", "c", "d")
            ret = salt.utils.path.join("/a/b/c", "d")
            assert ret == expected_path


class TestWhich(TestCase):
    """
    Tests salt.utils.path.which function to ensure that it returns True as
    expected.
    """

    # The mock patch below will make sure that ALL calls to the which function
    # returns None
    def test_missing_binary_in_linux(self):
        # salt.utils.path.which uses platform.is_windows to determine the platform, so we're using linux here
        with patch("salt.utils.platform.is_windows", lambda: False):
            with patch("salt.utils.path.which", lambda exe: None):
                assert salt.utils.path.which("this-binary-does-not-exist") is None

    # The mock patch below will make sure that ALL calls to the which function
    # return whatever is sent to it
    def test_existing_binary_in_linux(self):
        # salt.utils.path.which uses platform.is_windows to determine the platform, so we're using linux here
        with patch("salt.utils.platform.is_windows", lambda: False):
            with patch("salt.utils.path.which", lambda exe: exe):
                assert salt.utils.path.which("this-binary-exists-under-linux")

    def test_existing_binary_in_windows(self):
        with patch("os.path.isfile") as isfile:
            # We define the side_effect attribute on the mocked object in order to
            # specify which calls return which values. First call to os.path.isfile
            # returns X, the second Y, the third Z, etc...
            isfile.side_effect = [
                # The first os.path.isfile should return False due to checking the explicit path (first is_executable)
                False,
                # We will now also return False once so we get a .EXE back from
                # the function, see PATHEXT below.
                False,
                # Lastly return True, this is the windows check.
                True,
            ]

            # Patch os.access so that it always returns True
            with patch("os.access", lambda path, mode: True):
                # Disable os.path.islink
                with patch("os.path.islink", lambda path: False):
                    # we're using ';' as os.pathsep in this test
                    with patch("os.pathsep", ";"):
                        # Let's patch os.environ to provide a custom PATH variable
                        with patch.dict(
                            os.environ,
                            {"PATH": os.sep + "bin", "PATHEXT": ".COM;.EXE;.BAT;.CMD"},
                        ):
                            # Let's also patch is_windows to return True
                            with patch("salt.utils.platform.is_windows", lambda: True):
                                assert salt.utils.path.which(
                                    "this-binary-exists-under-windows"
                                ) == os.path.join(
                                    os.sep + "bin",
                                    "this-binary-exists-under-windows.EXE",
                                )

    def test_missing_binary_in_windows(self):
        with patch("os.access") as osaccess:
            osaccess.side_effect = [
                # The first os.access should return False due to checking the explicit path (first is_executable)
                False,
                # The second, iterating through $PATH, should also return False,
                # still checking for Linux
                # which() will add 4 extra paths to the given one, os.access will
                # be called 5 times
                False,
                False,
                False,
                False,
                False,
            ]
            # we're using ';' as os.pathsep in this test
            with patch("os.pathsep", ";"):
                # Let's patch os.environ to provide a custom PATH variable
                with patch.dict(os.environ, {"PATH": os.sep + "bin"}):
                    # Let's also patch is_widows to return True
                    with patch("salt.utils.platform.is_windows", lambda: True):
                        assert (
                            salt.utils.path.which(
                                "this-binary-is-missing-in-windows.exe"
                            )
                            is None
                        )

    def test_existing_binary_in_windows_pathext(self):
        with patch("os.path.isfile") as isfile:
            # We define the side_effect attribute on the mocked object in order to
            # specify which calls return which values. First call to os.path.isfile
            # returns X, the second Y, the third Z, etc...
            isfile.side_effect = [
                # The first os.path.isfile should return False due to checking the explicit path (first is_executable)
                False,
                # We will now also return False 3 times so we get a .CMD back from
                # the function, see PATHEXT below.
                # Lastly return True, this is the windows check.
                False,
                False,
                False,
                True,
            ]

            # Patch os.access so that it always returns True
            with patch("os.access", lambda path, mode: True):

                # Disable os.path.islink
                with patch("os.path.islink", lambda path: False):

                    # we're using ';' as os.pathsep in this test
                    with patch("os.pathsep", ";"):

                        # Let's patch os.environ to provide a custom PATH variable
                        with patch.dict(
                            os.environ,
                            {
                                "PATH": os.sep + "bin",
                                "PATHEXT": (
                                    ".COM;.EXE;.BAT;.CMD;.VBS;"
                                    ".VBE;.JS;.JSE;.WSF;.WSH;.MSC;.PY"
                                ),
                            },
                        ):

                            # Let's also patch is_windows to return True
                            with patch("salt.utils.platform.is_windows", lambda: True):
                                assert salt.utils.path.which(
                                    "this-binary-exists-under-windows"
                                ) == os.path.join(
                                    os.sep + "bin",
                                    "this-binary-exists-under-windows.CMD",
                                )
