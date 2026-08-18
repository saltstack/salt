"""
    :codeauthor: Nicole Thomas <nicole@saltstack.com>
"""

import random

# Create the cloud instance name to be used throughout the tests
from tests.integration.cloud.helpers.cloud_test_base import TIMEOUT, CloudTest


class LinodeTest(CloudTest):
    """
    Integration tests for the Linode cloud provider in Salt-Cloud
    """

    PROVIDER = "linode"
    REQUIRED_PROVIDER_CONFIG_ITEMS = ("apikey", "password")

    def _test_instance(self, profile, destroy=True):
        """
        Test creating an instance on Linode for a given profile.
        """

        # create the instance
        args = ["-p", profile, self.instance_name]
        ret_str = self.run_cloud(" ".join(args), timeout=TIMEOUT)

        self.assertInstanceExists(ret_str)
        if destroy:
            self.assertDestroyInstance()
        return ret_str

    def test_instance(self):
        return self._test_instance("linode-test")

    def test_instance_with_backup(self):
        profile = "linode-test-with-backup"

        self._test_instance(profile, False)

        set_backup_func = "set_backup_schedule"

        available_days = [
            "Sunday",
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
        ]
        available_windows = [
            "W0",
            "W2",
            "W4",
            "W6",
            "W8",
            "W10",
            "W12",
            "W14",
            "W16",
            "W18",
            "W20",
            "W22",
        ]

        args = [
            "-f",
            set_backup_func,
            self.PROVIDER,
            f"name={self.instance_name}",
            f"day={random.choice(available_days)}",
            f"window={random.choice(available_windows)}",
            "auto_enable=True",
        ]
        self.run_cloud(" ".join(args), timeout=TIMEOUT)

        args = ["-f", set_backup_func, self.PROVIDER, f"name={self.instance_name}"]
        self.run_cloud(" ".join(args), timeout=TIMEOUT)

        self.assertDestroyInstance()
