# -*- coding: utf-8 -*-
"""
    :codeauthor: Nicole Thomas <nicole@saltstack.com>
"""

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

import logging
import os
import time

import salt.utils.cloud
import salt.utils.files
import salt.utils.path
import salt.utils.yaml
import yaml

# Import Salt Libs
from salt.ext.six.moves import range

# Create the cloud instance name to be used throughout the tests
# Create the cloud instance name to be used throughout the tests
from tests.integration.cloud.helpers.cloud_test_base import (
    CloudTest,
    OverrideCloudConfig,
    requires_profile_config,
    requires_provider_config,
)
from tests.support import win_installer

# Import Salt Testing Libs
from tests.support.paths import FILES
from tests.support.unit import skipIf

HAS_WINRM = salt.utils.cloud.HAS_WINRM and salt.utils.cloud.HAS_SMB
log = logging.getLogger(__name__)


@requires_provider_config(
    "id",
    "key",
    "keyname",
    "private_key",
    "location",
    require_any=("securitygroup", "subnetid"),
)
class EC2Test(CloudTest):
    """
    Integration tests for the EC2 cloud provider in Salt-Cloud
    """

    PROVIDER = "ec2"
    # This test needs a longer timeout than other cloud tests
    TEST_TIMEOUT = 1200
    WIN2012R2_PROFILE = "ec2-win2012r2-test"
    WIN2016_PROFILE = "ec2-win2016-test"

    PROVIDER = "ec2"
    REQUIRED_PROVIDER_CONFIG_ITEMS = ("id", "key", "keyname", "private_key", "location")

    @staticmethod
    def __fetch_installer():
        # Determine the downloaded installer name by searching the files
        # directory for the first file that looks like an installer.
        for path, dirs, files in salt.utils.path.os_walk(FILES):
            for file in files:
                if file.startswith(win_installer.PREFIX):
                    log.debug("Found installer: {}".format(file))
                    return file

        # If the installer wasn't found in the previous steps, download the latest Windows installer executable
        name = win_installer.latest_installer_name()
        path = salt.utils.path.join(FILES, name)
        log.debug("Downloading installer '{}' to '{}'".format(name, path))
        with salt.utils.files.fopen(path, "wb") as fp:
            win_installer.download_and_verify(fp, name)
        assert os.path.exists(path), "Download failed: {}".format(name)
        return name

    @property
    def installer(self):
        """
        Make sure the testing environment has a Windows installer executable.
        """
        if not hasattr(self, "_installer"):
            self._installer = self.__fetch_installer()
        return self._installer

    def copy_file(self, name):
        """
        Copy a file from tests/integration/files to a test's temporary
        configuration directory. The path to the file which is created will be
        returned.
        """
        src = salt.utils.path.join(FILES, name)
        dst = salt.utils.path.join(self.config_dir, name)
        with salt.utils.files.fopen(src, "rb") as sfp:
            with salt.utils.files.fopen(dst, "wb") as dfp:
                dfp.write(sfp.read())
        return dst

    def _test_instance(self, profile_config_name, debug):
        """
        Tests creating and deleting an instance on EC2 (classic)
        """
        self.assertCreateInstance(
            profile_config_name, args=["-l", "debug"] if debug else []
        )
        self.assertDestroyInstance()

    def test_instance_rename(self):
        """
        Tests creating and renaming an instance on EC2 (classic)
        """
        self.assertCreateInstance(args=["--no-deploy"])
        changed_name = self.instance_name + "-changed"

        self.run_cloud(
            "-a rename {0} newname={1} --assume-yes".format(
                self.instance_name, changed_name
            ),
            timeout=self.TEST_TIMEOUT,
        )

        # Wait until the previous instance name disappears
        for _ in range(12):
            if not self._instance_exists() and self._instance_exists(changed_name):
                break
            else:
                time.sleep(5)
        else:
            self.fail(
                'Failed to rename instance "{}" to "{}"'.format(
                    self.instance_name, changed_name
                )
            )

        self.assertDestroyInstance(changed_name)

    def test_instance(self):
        """
        Tests creating and deleting an instance on EC2 (classic)
        """
        self.assertCreateInstance()
        self.assertDestroyInstance()

    @requires_profile_config(profile_config_name=WIN2012R2_PROFILE)
    def test_win2012r2_psexec(self):
        """
        Tests creating and deleting a Windows 2012r2instance on EC2 using
        psexec (classic)
        """
        with OverrideCloudConfig(
            self.profile_config_path,
            self.WIN2012R2_PROFILE,
            use_winrm=False,
            userdata_file=self.copy_file("windows-firewall-winexe.ps1"),
            win_installer=self.copy_file(self.installer),
        ):
            self._test_instance(self.WIN2012R2_PROFILE, debug=True)

    @requires_profile_config(profile_config_name=WIN2012R2_PROFILE)
    @skipIf(not HAS_WINRM, "Skip when winrm dependencies are missing")
    def test_win2012r2_winrm(self):
        """
        Tests creating and deleting a Windows 2012r2 instance on EC2 using
        winrm (classic)
        """

        with OverrideCloudConfig(
            self.profile_config_path,
            self.WIN2012R2_PROFILE,
            use_winrm=True,
            userdata_file=self.copy_file("windows-firewall.ps1"),
            win_installer=self.copy_file(self.installer),
            winrm_ssl_verify=False,
        ):
            self._test_instance(self.WIN2012R2_PROFILE, debug=True)

    @requires_profile_config(profile_config_name=WIN2016_PROFILE)
    def test_win2016_psexec(self):
        """
        Tests creating and deleting a Windows 2016 instance on EC2 using winrm (classic)
        """
        with OverrideCloudConfig(
            self.profile_config_path,
            self.WIN2016_PROFILE,
            use_winrm=False,
            userdata_file=self.copy_file("windows-firewall-winexe.ps1"),
            win_installer=self.copy_file(self.installer),
        ):
            self._test_instance(self.WIN2016_PROFILE, debug=True)

    @requires_profile_config(profile_config_name=WIN2016_PROFILE)
    @skipIf(not HAS_WINRM, "Skip when winrm dependencies are missing")
    def test_win2016_winrm(self):
        """
        Tests creating and deleting a Windows 2016 instance on EC2 using winrm (classic)
        """
        with OverrideCloudConfig(
            self.profile_config_path,
            self.WIN2016_PROFILE,
            use_winrm=True,
            userdata_file=self.copy_file("windows-firewall.ps1"),
            win_installer=self.copy_file(self.installer),
            winrm_ssl_verify=False,
        ):
            self._test_instance(self.WIN2016_PROFILE, debug=True)
