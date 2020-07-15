# -*- coding: utf-8 -*-
"""
    :codeauthor: :email:`David Homolka <david.homolka@ultimum.io>`
"""

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libsrestartcheck
import salt.modules.restartcheck as restartcheck

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase

# import salt.utils.files
# from salt.exceptions import CommandExecutionError


class RestartcheckTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.modules.restartcheck
    """

    def setup_loader_modules(self):
        return {restartcheck: {}}

    def test_kernel_versions_debian(self):
        """
        Test kernel version debian
        """
        mock = MagicMock(return_value="  Installed: 4.9.82-1+deb9u3")
        with patch.dict(restartcheck.__grains__, {"os": "Debian"}):
            with patch.dict(restartcheck.__salt__, {"cmd.run": mock}):
                self.assertListEqual(
                    restartcheck._kernel_versions_debian(), ["4.9.82-1+deb9u3"]
                )

    def test_kernel_versions_ubuntu(self):
        """
        Test kernel version ubuntu
        """
        mock = MagicMock(return_value="  Installed: 4.10.0-42.46")
        with patch.dict(restartcheck.__grains__, {"os": "Ubuntu"}):
            with patch.dict(restartcheck.__salt__, {"cmd.run": mock}):
                self.assertListEqual(
                    restartcheck._kernel_versions_debian(),
                    [
                        "4.10.0-42.46",
                        "4.10.0-42-generic #46",
                        "4.10.0-42-lowlatency #46",
                    ],
                )

    def test_kernel_versions_redhat(self):
        """
        Test if it return a data structure of the current, in-memory rules
        """
        mock = MagicMock(
            return_value="kernel-3.10.0-862.el7.x86_64                  Thu Apr 5 00:40:00 2018"
        )
        with patch.dict(restartcheck.__salt__, {"cmd.run": mock}):
            self.assertListEqual(
                restartcheck._kernel_versions_redhat(), ["3.10.0-862.el7.x86_64"]
            )

    def test_valid_deleted_file_deleted(self):
        """
        Test (deleted) file
        """
        self.assertTrue(restartcheck._valid_deleted_file("/usr/lib/test (deleted)"))

    def test_valid_deleted_file_psth_inode(self):
        """
        Test (path inode=1) file
        """
        self.assertTrue(
            restartcheck._valid_deleted_file("/usr/lib/test (path inode=1)")
        )

    def test_valid_deleted_file_var_log(self):
        """
        Test /var/log/
        """
        self.assertFalse(restartcheck._valid_deleted_file("/var/log/test"))
        self.assertFalse(restartcheck._valid_deleted_file("/var/log/test (deleted)"))
        self.assertFalse(
            restartcheck._valid_deleted_file("/var/log/test (path inode=1)")
        )

    def test_valid_deleted_file_var_local_log(self):
        """
        Test /var/local/log/
        """
        self.assertFalse(restartcheck._valid_deleted_file("/var/local/log/test"))
        self.assertFalse(
            restartcheck._valid_deleted_file("/var/local/log/test (deleted)")
        )
        self.assertFalse(
            restartcheck._valid_deleted_file("/var/local/log/test (path inode=1)")
        )

    def test_valid_deleted_file_var_run(self):
        """
        Test /var/run/
        """
        self.assertFalse(restartcheck._valid_deleted_file("/var/run/test"))
        self.assertFalse(restartcheck._valid_deleted_file("/var/run/test (deleted)"))
        self.assertFalse(
            restartcheck._valid_deleted_file("/var/run/test (path inode=1)")
        )

    def test_valid_deleted_file_var_local_run(self):
        """
        Test /var/local/run/
        """
        self.assertFalse(restartcheck._valid_deleted_file("/var/local/run/test"))
        self.assertFalse(
            restartcheck._valid_deleted_file("/var/local/run/test (deleted)")
        )
        self.assertFalse(
            restartcheck._valid_deleted_file("/var/local/run/test (path inode=1)")
        )

    def test_valid_deleted_file_tmp(self):
        """
        Test /tmp/
        """
        self.assertFalse(restartcheck._valid_deleted_file("/tmp/test"))
        self.assertFalse(restartcheck._valid_deleted_file("/tmp/test (deleted)"))
        self.assertFalse(restartcheck._valid_deleted_file("/tmp/test (path inode=1)"))

    def test_valid_deleted_file_dev_shm(self):
        """
        Test /dev/shm/
        """
        self.assertFalse(restartcheck._valid_deleted_file("/dev/shm/test"))
        self.assertFalse(restartcheck._valid_deleted_file("/dev/shm/test (deleted)"))
        self.assertFalse(
            restartcheck._valid_deleted_file("/dev/shm/test (path inode=1)")
        )

    def test_valid_deleted_file_run(self):
        """
        Test /run/
        """
        self.assertFalse(restartcheck._valid_deleted_file("/run/test"))
        self.assertFalse(restartcheck._valid_deleted_file("/run/test (deleted)"))
        self.assertFalse(restartcheck._valid_deleted_file("/run/test (path inode=1)"))

    def test_valid_deleted_file_drm(self):
        """
        Test /drm/
        """
        self.assertFalse(restartcheck._valid_deleted_file("/drm/test"))
        self.assertFalse(restartcheck._valid_deleted_file("/drm/test (deleted)"))
        self.assertFalse(restartcheck._valid_deleted_file("/drm/test (path inode=1)"))

    def test_valid_deleted_file_var_tmp(self):
        """
        Test /var/tmp/
        """
        self.assertFalse(restartcheck._valid_deleted_file("/var/tmp/test"))
        self.assertFalse(restartcheck._valid_deleted_file("/var/tmp/test (deleted)"))
        self.assertFalse(
            restartcheck._valid_deleted_file("/var/tmp/test (path inode=1)")
        )

    def test_valid_deleted_file_var_local_tmp(self):
        """
        Test /var/local/tmp/
        """
        self.assertFalse(restartcheck._valid_deleted_file("/var/local/tmp/test"))
        self.assertFalse(
            restartcheck._valid_deleted_file("/var/local/tmp/test (deleted)")
        )
        self.assertFalse(
            restartcheck._valid_deleted_file("/var/local/tmp/test (path inode=1)")
        )

    def test_valid_deleted_file_dev_zero(self):
        """
        Test /dev/zero/
        """
        self.assertFalse(restartcheck._valid_deleted_file("/dev/zero/test"))
        self.assertFalse(restartcheck._valid_deleted_file("/dev/zero/test (deleted)"))
        self.assertFalse(
            restartcheck._valid_deleted_file("/dev/zero/test (path inode=1)")
        )

    def test_valid_deleted_file_dev_pts(self):
        """
        Test /dev/pts/
        """
        self.assertFalse(restartcheck._valid_deleted_file("/dev/pts/test"))
        self.assertFalse(restartcheck._valid_deleted_file("/dev/pts/test (deleted)"))
        self.assertFalse(
            restartcheck._valid_deleted_file("/dev/pts/test (path inode=1)")
        )

    def test_valid_deleted_file_usr_lib_locale(self):
        """
        Test /usr/lib/locale/
        """
        self.assertFalse(restartcheck._valid_deleted_file("/usr/lib/locale/test"))
        self.assertFalse(
            restartcheck._valid_deleted_file("/usr/lib/locale/test (deleted)")
        )
        self.assertFalse(
            restartcheck._valid_deleted_file("/usr/lib/locale/test (path inode=1)")
        )

    def test_valid_deleted_file_home(self):
        """
        Test /home/
        """
        self.assertFalse(restartcheck._valid_deleted_file("/home/test"))
        self.assertFalse(restartcheck._valid_deleted_file("/home/test (deleted)"))
        self.assertFalse(restartcheck._valid_deleted_file("/home/test (path inode=1)"))

    def test_valid_deleted_file_icon_theme_cache(self):
        """
        Test /test.icon-theme.cache
        """
        self.assertFalse(restartcheck._valid_deleted_file("/dev/test.icon-theme.cache"))
        self.assertFalse(
            restartcheck._valid_deleted_file("/dev/test.icon-theme.cache (deleted)")
        )
        self.assertFalse(
            restartcheck._valid_deleted_file(
                "/dev/test.icon-theme.cache (path inode=1)"
            )
        )

    def test_valid_deleted_file_var_cache_fontconfig(self):
        """
        Test /var/cache/fontconfig/
        """
        self.assertFalse(restartcheck._valid_deleted_file("/var/cache/fontconfig/test"))
        self.assertFalse(
            restartcheck._valid_deleted_file("/var/cache/fontconfig/test (deleted)")
        )
        self.assertFalse(
            restartcheck._valid_deleted_file(
                "/var/cache/fontconfig/test (path inode=1)"
            )
        )

    def test_valid_deleted_file_var_lib_nagios3_spool(self):
        """
        Test /var/lib/nagios3/spool/
        """
        self.assertFalse(
            restartcheck._valid_deleted_file("/var/lib/nagios3/spool/test")
        )
        self.assertFalse(
            restartcheck._valid_deleted_file("/var/lib/nagios3/spool/test (deleted)")
        )
        self.assertFalse(
            restartcheck._valid_deleted_file(
                "/var/lib/nagios3/spool/test (path inode=1)"
            )
        )

    def test_valid_deleted_file_var_lib_nagios3_spool_checkresults(self):
        """
        Test /var/lib/nagios3/spool/checkresults/
        """
        self.assertFalse(
            restartcheck._valid_deleted_file("/var/lib/nagios3/spool/checkresults/test")
        )
        self.assertFalse(
            restartcheck._valid_deleted_file(
                "/var/lib/nagios3/spool/checkresults/test (deleted)"
            )
        )
        self.assertFalse(
            restartcheck._valid_deleted_file(
                "/var/lib/nagios3/spool/checkresults/test (path inode=1)"
            )
        )

    def test_valid_deleted_file_var_lib_postgresql(self):
        """
        Test /var/lib/postgresql/
        """
        self.assertFalse(restartcheck._valid_deleted_file("/var/lib/postgresql/test"))
        self.assertFalse(
            restartcheck._valid_deleted_file("/var/lib/postgresql/test (deleted)")
        )
        self.assertFalse(
            restartcheck._valid_deleted_file("/var/lib/postgresql/test (path inode=1)")
        )

    def test_valid_deleted_file_var_lib_vdr(self):
        """
        Test /var/lib/vdr/
        """
        self.assertFalse(restartcheck._valid_deleted_file("/var/lib/vdr/test"))
        self.assertFalse(
            restartcheck._valid_deleted_file("/var/lib/vdr/test (deleted)")
        )
        self.assertFalse(
            restartcheck._valid_deleted_file("/var/lib/vdr/test (path inode=1)")
        )

    def test_valid_deleted_file_aio(self):
        """
        Test /[aio]/
        """
        self.assertFalse(restartcheck._valid_deleted_file("/opt/test"))
        self.assertFalse(restartcheck._valid_deleted_file("/opt/test (deleted)"))
        self.assertFalse(restartcheck._valid_deleted_file("/opt/test (path inode=1)"))
        self.assertFalse(restartcheck._valid_deleted_file("/apt/test"))
        self.assertFalse(restartcheck._valid_deleted_file("/apt/test (deleted)"))
        self.assertFalse(restartcheck._valid_deleted_file("/apt/test (path inode=1)"))
        self.assertFalse(restartcheck._valid_deleted_file("/ipt/test"))
        self.assertFalse(restartcheck._valid_deleted_file("/ipt/test (deleted)"))
        self.assertFalse(restartcheck._valid_deleted_file("/ipt/test (path inode=1)"))
        self.assertFalse(restartcheck._valid_deleted_file("/aio/test"))
        self.assertFalse(restartcheck._valid_deleted_file("/aio/test (deleted)"))
        self.assertFalse(restartcheck._valid_deleted_file("/aio/test (path inode=1)"))

    def test_valid_deleted_file_sysv(self):
        """
        Test /SYSV/
        """
        self.assertFalse(restartcheck._valid_deleted_file("/SYSV/test"))
        self.assertFalse(restartcheck._valid_deleted_file("/SYSV/test (deleted)"))
        self.assertFalse(restartcheck._valid_deleted_file("/SYSV/test (path inode=1)"))
