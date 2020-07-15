# -*- coding: utf-8 -*-

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

import os
from tempfile import NamedTemporaryFile

import salt.modules.timezone as timezone
import salt.utils.platform
import salt.utils.stringutils

# Import Salt Libs
from salt.exceptions import CommandExecutionError, SaltInvocationError
from salt.ext import six

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, mock_open, patch
from tests.support.unit import TestCase, skipIf

GET_ZONE_FILE = "salt.modules.timezone._get_zone_file"
GET_LOCALTIME_PATH = "salt.modules.timezone._get_localtime_path"


class TimezoneTestCase(TestCase, LoaderModuleMockMixin):
    def setup_loader_modules(self):
        return {timezone: {"__grains__": {"os_family": "Ubuntu"}}}

    def setUp(self):
        self.tempfiles = []

    def tearDown(self):
        for tempfile in self.tempfiles:
            try:
                os.remove(tempfile.name)
            except OSError:
                pass
        del self.tempfiles

    def test_zone_compare_equal(self):
        etc_localtime = self.create_tempfile_with_contents("a")
        zone_path = self.create_tempfile_with_contents("a")

        with patch(GET_ZONE_FILE, lambda p: zone_path.name):
            with patch(GET_LOCALTIME_PATH, lambda: etc_localtime.name):

                self.assertTrue(timezone.zone_compare("foo"))

    def test_zone_compare_nonexistent(self):
        etc_localtime = self.create_tempfile_with_contents("a")

        with patch(GET_ZONE_FILE, lambda p: "/foopath/nonexistent"):
            with patch(GET_LOCALTIME_PATH, lambda: etc_localtime.name):

                self.assertRaises(SaltInvocationError, timezone.zone_compare, "foo")

    def test_zone_compare_unequal(self):
        etc_localtime = self.create_tempfile_with_contents("a")
        zone_path = self.create_tempfile_with_contents("b")

        with patch(GET_ZONE_FILE, lambda p: zone_path.name):
            with patch(GET_LOCALTIME_PATH, lambda: etc_localtime.name):

                self.assertFalse(timezone.zone_compare("foo"))

    def test_missing_localtime(self):
        with patch(GET_ZONE_FILE, lambda p: "/nonexisting"):
            with patch(GET_LOCALTIME_PATH, lambda: "/also-missing"):
                self.assertRaises(CommandExecutionError, timezone.zone_compare, "foo")

    def create_tempfile_with_contents(self, contents):
        temp = NamedTemporaryFile(delete=False)
        if six.PY3:
            temp.write(salt.utils.stringutils.to_bytes(contents))
        else:
            temp.write(contents)
        temp.close()
        self.tempfiles.append(temp)
        return temp


class TimezoneModuleTestCase(TestCase, LoaderModuleMockMixin):
    """
        Timezone test case
        """

    TEST_TZ = "UTC"

    def setup_loader_modules(self):
        return {
            timezone: {
                "__grains__": {"os": ""},
                "__salt__": {
                    "file.sed": MagicMock(),
                    "cmd.run": MagicMock(),
                    "cmd.retcode": MagicMock(return_value=0),
                },
            }
        }

    @patch("salt.utils.path.which", MagicMock(return_value=False))
    def test_get_zone_centos(self):
        """
        Test CentOS is recognized
        :return:
        """
        with patch.dict(timezone.__grains__, {"os": "centos"}):
            with patch(
                "salt.modules.timezone._get_zone_etc_localtime",
                MagicMock(return_value=self.TEST_TZ),
            ):
                assert timezone.get_zone() == self.TEST_TZ

    @patch("salt.utils.path.which", MagicMock(return_value=False))
    def test_get_zone_os_family_rh_suse(self):
        """
        Test RedHat and Suse are recognized
        :return:
        """
        for osfamily in ["RedHat", "Suse"]:
            with patch.dict(timezone.__grains__, {"os_family": [osfamily]}):
                with patch(
                    "salt.modules.timezone._get_zone_sysconfig",
                    MagicMock(return_value=self.TEST_TZ),
                ):
                    assert timezone.get_zone() == self.TEST_TZ

    @patch("salt.utils.path.which", MagicMock(return_value=False))
    def test_get_zone_os_family_debian_gentoo(self):
        """
        Test Debian and Gentoo are recognized
        :return:
        """
        for osfamily in ["Debian", "Gentoo"]:
            with patch.dict(timezone.__grains__, {"os_family": [osfamily]}):
                with patch(
                    "salt.modules.timezone._get_zone_etc_timezone",
                    MagicMock(return_value=self.TEST_TZ),
                ):
                    assert timezone.get_zone() == self.TEST_TZ

    @patch("salt.utils.path.which", MagicMock(return_value=False))
    def test_get_zone_os_family_allbsd_nilinuxrt(self):
        """
        Test *BSD and NILinuxRT are recognized
        :return:
        """
        for osfamily in ["FreeBSD", "OpenBSD", "NetBSD", "NILinuxRT"]:
            with patch.dict(timezone.__grains__, {"os_family": osfamily}):
                with patch(
                    "salt.modules.timezone._get_zone_etc_localtime",
                    MagicMock(return_value=self.TEST_TZ),
                ):
                    assert timezone.get_zone() == self.TEST_TZ

    @patch("salt.utils.path.which", MagicMock(return_value=False))
    def test_get_zone_os_family_slowlaris(self):
        """
        Test Slowlaris is recognized
        :return:
        """
        with patch.dict(timezone.__grains__, {"os_family": ["Solaris"]}):
            with patch(
                "salt.modules.timezone._get_zone_solaris",
                MagicMock(return_value=self.TEST_TZ),
            ):
                assert timezone.get_zone() == self.TEST_TZ

    @patch("salt.utils.path.which", MagicMock(return_value=False))
    def test_get_zone_os_family_aix(self):
        """
        Test IBM AIX is recognized
        :return:
        """
        with patch.dict(timezone.__grains__, {"os_family": ["AIX"]}):
            with patch(
                "salt.modules.timezone._get_zone_aix",
                MagicMock(return_value=self.TEST_TZ),
            ):
                assert timezone.get_zone() == self.TEST_TZ

    @skipIf(salt.utils.platform.is_windows(), "os.symlink not available in Windows")
    @patch("salt.utils.path.which", MagicMock(return_value=False))
    @patch("os.path.exists", MagicMock(return_value=True))
    @patch("os.unlink", MagicMock())
    @patch("os.symlink", MagicMock())
    def test_set_zone_redhat(self):
        """
        Test zone set on RH series
        :return:
        """
        with patch.dict(timezone.__grains__, {"os_family": ["RedHat"]}):
            assert timezone.set_zone(self.TEST_TZ)
            name, args, kwargs = timezone.__salt__["file.sed"].mock_calls[0]
            assert args == ("/etc/sysconfig/clock", "^ZONE=.*", 'ZONE="UTC"')

    @skipIf(salt.utils.platform.is_windows(), "os.symlink not available in Windows")
    @patch("salt.utils.path.which", MagicMock(return_value=False))
    @patch("os.path.exists", MagicMock(return_value=True))
    @patch("os.unlink", MagicMock())
    @patch("os.symlink", MagicMock())
    def test_set_zone_suse(self):
        """
        Test zone set on SUSE series
        :return:
        """
        with patch.dict(timezone.__grains__, {"os_family": ["Suse"]}):
            assert timezone.set_zone(self.TEST_TZ)
            name, args, kwargs = timezone.__salt__["file.sed"].mock_calls[0]
            assert args == ("/etc/sysconfig/clock", "^TIMEZONE=.*", 'TIMEZONE="UTC"')

    @skipIf(salt.utils.platform.is_windows(), "os.symlink not available in Windows")
    @patch("salt.utils.path.which", MagicMock(return_value=False))
    @patch("os.path.exists", MagicMock(return_value=True))
    @patch("os.unlink", MagicMock())
    @patch("os.symlink", MagicMock())
    def test_set_zone_gentoo(self):
        """
        Test zone set on Gentoo series
        :return:
        """
        with patch.dict(timezone.__grains__, {"os_family": ["Gentoo"]}):
            with patch("salt.utils.files.fopen", mock_open()) as m_open:
                assert timezone.set_zone(self.TEST_TZ)
                fh_ = m_open.filehandles["/etc/timezone"][0]
                assert fh_.call.args == ("/etc/timezone", "w"), fh_.call.args
                assert fh_.write_calls == ["UTC", "\n"], fh_.write_calls

    @skipIf(salt.utils.platform.is_windows(), "os.symlink not available in Windows")
    @patch("salt.utils.path.which", MagicMock(return_value=False))
    @patch("os.path.exists", MagicMock(return_value=True))
    @patch("os.unlink", MagicMock())
    @patch("os.symlink", MagicMock())
    def test_set_zone_debian(self):
        """
        Test zone set on Debian series
        :return:
        """
        with patch.dict(timezone.__grains__, {"os_family": ["Debian"]}):
            with patch("salt.utils.files.fopen", mock_open()) as m_open:
                assert timezone.set_zone(self.TEST_TZ)
                fh_ = m_open.filehandles["/etc/timezone"][0]
                assert fh_.call.args == ("/etc/timezone", "w"), fh_.call.args
                assert fh_.write_calls == ["UTC", "\n"], fh_.write_calls

    @skipIf(salt.utils.platform.is_windows(), "os.symlink not available in Windows")
    @patch("salt.utils.path.which", MagicMock(return_value=True))
    @patch("os.path.exists", MagicMock(return_value=True))
    @patch("os.unlink", MagicMock())
    @patch("os.symlink", MagicMock())
    def test_get_hwclock_timedate_utc(self):
        """
        Test get hwclock UTC/localtime
        :return:
        """
        with patch(
            "salt.modules.timezone._timedatectl",
            MagicMock(return_value={"stdout": "rtc in local tz"}),
        ):
            assert timezone.get_hwclock() == "UTC"
        with patch(
            "salt.modules.timezone._timedatectl",
            MagicMock(return_value={"stdout": "rtc in local tz:yes"}),
        ):
            assert timezone.get_hwclock() == "localtime"

    @skipIf(salt.utils.platform.is_windows(), "os.symlink not available in Windows")
    @patch("salt.utils.path.which", MagicMock(return_value=False))
    @patch("os.path.exists", MagicMock(return_value=True))
    @patch("os.unlink", MagicMock())
    @patch("os.symlink", MagicMock())
    def test_get_hwclock_suse(self):
        """
        Test get hwclock on SUSE
        :return:
        """
        with patch.dict(timezone.__grains__, {"os_family": ["Suse"]}):
            timezone.get_hwclock()
            name, args, kwarg = timezone.__salt__["cmd.run"].mock_calls[0]
            assert args == (["tail", "-n", "1", "/etc/adjtime"],)
            assert kwarg == {"python_shell": False}

    @skipIf(salt.utils.platform.is_windows(), "os.symlink not available in Windows")
    @patch("salt.utils.path.which", MagicMock(return_value=False))
    @patch("os.path.exists", MagicMock(return_value=True))
    @patch("os.unlink", MagicMock())
    @patch("os.symlink", MagicMock())
    def test_get_hwclock_redhat(self):
        """
        Test get hwclock on RedHat
        :return:
        """
        with patch.dict(timezone.__grains__, {"os_family": ["RedHat"]}):
            timezone.get_hwclock()
            name, args, kwarg = timezone.__salt__["cmd.run"].mock_calls[0]
            assert args == (["tail", "-n", "1", "/etc/adjtime"],)
            assert kwarg == {"python_shell": False}

    def _test_get_hwclock_debian(
        self,
    ):  # TODO: Enable this when testing environment is working properly
        """
        Test get hwclock on Debian
        :return:
        """
        with patch("salt.utils.path.which", MagicMock(return_value=False)):
            with patch("os.path.exists", MagicMock(return_value=True)):
                with patch("os.unlink", MagicMock()):
                    with patch("os.symlink", MagicMock()):
                        with patch.dict(timezone.__grains__, {"os_family": ["Debian"]}):
                            timezone.get_hwclock()
                            name, args, kwarg = timezone.__salt__["cmd.run"].mock_calls[
                                0
                            ]
                            assert args == (["tail", "-n", "1", "/etc/adjtime"],)
                            assert kwarg == {"python_shell": False}

    @skipIf(salt.utils.platform.is_windows(), "os.symlink not available in Windows")
    @patch("salt.utils.path.which", MagicMock(return_value=False))
    @patch("os.path.exists", MagicMock(return_value=True))
    @patch("os.unlink", MagicMock())
    @patch("os.symlink", MagicMock())
    def test_get_hwclock_solaris(self):
        """
        Test get hwclock on Solaris
        :return:
        """
        # Incomplete
        with patch.dict(timezone.__grains__, {"os_family": ["Solaris"]}):
            assert timezone.get_hwclock() == "UTC"
            with patch("salt.utils.files.fopen", mock_open()):
                assert timezone.get_hwclock() == "localtime"

    @skipIf(salt.utils.platform.is_windows(), "os.symlink not available in Windows")
    @patch("salt.utils.path.which", MagicMock(return_value=False))
    @patch("os.path.exists", MagicMock(return_value=True))
    @patch("os.unlink", MagicMock())
    @patch("os.symlink", MagicMock())
    def test_get_hwclock_aix(self):
        """
        Test get hwclock on AIX
        :return:
        """
        # Incomplete
        hwclock = "localtime"
        if not os.path.isfile("/etc/environment"):
            hwclock = "UTC"
        with patch.dict(timezone.__grains__, {"os_family": ["AIX"]}):
            assert timezone.get_hwclock() == hwclock

    @skipIf(salt.utils.platform.is_windows(), "os.symlink not available in Windows")
    @patch("salt.utils.path.which", MagicMock(return_value=True))
    def test_set_hwclock_timedatectl(self):
        """
        Test set hwclock with timedatectl
        :return:
        """
        timezone.set_hwclock("UTC")
        name, args, kwargs = timezone.__salt__["cmd.retcode"].mock_calls[0]
        assert args == (["timedatectl", "set-local-rtc", "false"],)

        timezone.set_hwclock("localtime")
        name, args, kwargs = timezone.__salt__["cmd.retcode"].mock_calls[1]
        assert args == (["timedatectl", "set-local-rtc", "true"],)

    @skipIf(salt.utils.platform.is_windows(), "os.symlink not available in Windows")
    @patch("salt.utils.path.which", MagicMock(return_value=False))
    @patch("os.path.exists", MagicMock(return_value=True))
    @patch("os.unlink", MagicMock())
    @patch("os.symlink", MagicMock())
    def test_set_hwclock_aix_nilinuxrt(self):
        """
        Test set hwclock on AIX and NILinuxRT
        :return:
        """
        for osfamily in ["AIX", "NILinuxRT"]:
            with patch.dict(timezone.__grains__, {"os_family": osfamily}):
                with self.assertRaises(SaltInvocationError):
                    assert timezone.set_hwclock("forty two")
                assert timezone.set_hwclock("UTC")

    @skipIf(salt.utils.platform.is_windows(), "os.symlink not available in Windows")
    @patch("salt.utils.path.which", MagicMock(return_value=False))
    @patch("os.path.exists", MagicMock(return_value=True))
    @patch("os.unlink", MagicMock())
    @patch("os.symlink", MagicMock())
    @patch("salt.modules.timezone.get_zone", MagicMock(return_value="TEST_TIMEZONE"))
    def test_set_hwclock_solaris(self):
        """
        Test set hwclock on Solaris
        :return:
        """
        with patch.dict(
            timezone.__grains__, {"os_family": ["Solaris"], "cpuarch": "x86"}
        ):
            with self.assertRaises(SaltInvocationError):
                assert timezone.set_hwclock("forty two")
            assert timezone.set_hwclock("UTC")
            name, args, kwargs = timezone.__salt__["cmd.retcode"].mock_calls[0]
            assert args == (["rtc", "-z", "GMT"],)
            assert kwargs == {"python_shell": False}

    @skipIf(salt.utils.platform.is_windows(), "os.symlink not available in Windows")
    @patch("salt.utils.path.which", MagicMock(return_value=False))
    @patch("os.path.exists", MagicMock(return_value=True))
    @patch("os.unlink", MagicMock())
    @patch("os.symlink", MagicMock())
    @patch("salt.modules.timezone.get_zone", MagicMock(return_value="TEST_TIMEZONE"))
    def test_set_hwclock_arch(self):
        """
        Test set hwclock on arch
        :return:
        """
        with patch.dict(timezone.__grains__, {"os_family": ["Arch"]}):
            assert timezone.set_hwclock("UTC")
            name, args, kwargs = timezone.__salt__["cmd.retcode"].mock_calls[0]
            assert args == (["timezonectl", "set-local-rtc", "false"],)
            assert kwargs == {"python_shell": False}

    @skipIf(salt.utils.platform.is_windows(), "os.symlink not available in Windows")
    @patch("salt.utils.path.which", MagicMock(return_value=False))
    @patch("os.path.exists", MagicMock(return_value=True))
    @patch("os.unlink", MagicMock())
    @patch("os.symlink", MagicMock())
    @patch("salt.modules.timezone.get_zone", MagicMock(return_value="TEST_TIMEZONE"))
    def test_set_hwclock_redhat(self):
        """
        Test set hwclock on RedHat
        :return:
        """
        with patch.dict(timezone.__grains__, {"os_family": ["RedHat"]}):
            assert timezone.set_hwclock("UTC")
            name, args, kwargs = timezone.__salt__["file.sed"].mock_calls[0]
            assert args == ("/etc/sysconfig/clock", "^ZONE=.*", 'ZONE="TEST_TIMEZONE"')

    @skipIf(salt.utils.platform.is_windows(), "os.symlink not available in Windows")
    @patch("salt.utils.path.which", MagicMock(return_value=False))
    @patch("os.path.exists", MagicMock(return_value=True))
    @patch("os.unlink", MagicMock())
    @patch("os.symlink", MagicMock())
    @patch("salt.modules.timezone.get_zone", MagicMock(return_value="TEST_TIMEZONE"))
    def test_set_hwclock_suse(self):
        """
        Test set hwclock on SUSE
        :return:
        """
        with patch.dict(timezone.__grains__, {"os_family": ["Suse"]}):
            assert timezone.set_hwclock("UTC")
            name, args, kwargs = timezone.__salt__["file.sed"].mock_calls[0]
            assert args == (
                "/etc/sysconfig/clock",
                "^TIMEZONE=.*",
                'TIMEZONE="TEST_TIMEZONE"',
            )

    @skipIf(salt.utils.platform.is_windows(), "os.symlink not available in Windows")
    @patch("salt.utils.path.which", MagicMock(return_value=False))
    @patch("os.path.exists", MagicMock(return_value=True))
    @patch("os.unlink", MagicMock())
    @patch("os.symlink", MagicMock())
    @patch("salt.modules.timezone.get_zone", MagicMock(return_value="TEST_TIMEZONE"))
    def test_set_hwclock_debian(self):
        """
        Test set hwclock on Debian
        :return:
        """
        with patch.dict(timezone.__grains__, {"os_family": ["Debian"]}):
            assert timezone.set_hwclock("UTC")
            name, args, kwargs = timezone.__salt__["file.sed"].mock_calls[0]
            assert args == ("/etc/default/rcS", "^UTC=.*", "UTC=yes")

            assert timezone.set_hwclock("localtime")
            name, args, kwargs = timezone.__salt__["file.sed"].mock_calls[1]
            assert args == ("/etc/default/rcS", "^UTC=.*", "UTC=no")

    @skipIf(salt.utils.platform.is_windows(), "os.symlink not available in Windows")
    @patch("salt.utils.path.which", MagicMock(return_value=False))
    @patch("os.path.exists", MagicMock(return_value=True))
    @patch("os.unlink", MagicMock())
    @patch("os.symlink", MagicMock())
    @patch("salt.modules.timezone.get_zone", MagicMock(return_value="TEST_TIMEZONE"))
    def test_set_hwclock_gentoo(self):
        """
        Test set hwclock on Gentoo
        :return:
        """
        with patch.dict(timezone.__grains__, {"os_family": ["Gentoo"]}):
            with self.assertRaises(SaltInvocationError):
                timezone.set_hwclock("forty two")

            timezone.set_hwclock("UTC")
            name, args, kwargs = timezone.__salt__["file.sed"].mock_calls[0]
            assert args == ("/etc/conf.d/hwclock", "^clock=.*", 'clock="UTC"')

            timezone.set_hwclock("localtime")
            name, args, kwargs = timezone.__salt__["file.sed"].mock_calls[1]
            assert args == ("/etc/conf.d/hwclock", "^clock=.*", 'clock="local"')
