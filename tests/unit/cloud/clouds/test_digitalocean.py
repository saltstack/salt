"""
    :codeauthor: `Gareth J. Greenaway <gareth@saltstack.com>`

    tests.unit.cloud.clouds.digitalocean_test
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
"""


import logging

from salt.cloud.clouds import digitalocean
from salt.exceptions import SaltCloudSystemExit
from tests.support.unit import TestCase

log = logging.getLogger(__name__)


class DigitalOceanTestCase(TestCase):
    """
    Unit TestCase for salt.cloud.clouds.digitalocean module.
    """

    def test_reboot_no_call(self):
        """
        Tests that a SaltCloudSystemExit is raised when
        kwargs that are provided do not include an action.
        """
        self.assertRaises(
            SaltCloudSystemExit,
            digitalocean.reboot,
            name="fake_name",
        )

        with self.assertRaises(SaltCloudSystemExit) as excinfo:
            ret = digitalocean.reboot(name="fake_name")
        self.assertEqual(
            "The reboot action must be called with -a or --action.",
            excinfo.exception.strerror,
        )
