"""
    :codeauthor: `Gareth J. Greenaway <gareth@saltstack.com>`

    tests.unit.cloud.clouds.digitalocean_test
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
"""


import logging

import pytest

from salt.cloud.clouds import digitalocean
from salt.exceptions import SaltCloudSystemExit

log = logging.getLogger(__name__)


def test_reboot_no_call():
    """
    Tests that a SaltCloudSystemExit is raised when
    kwargs that are provided do not include an action.
    """
    with pytest.raises(SaltCloudSystemExit) as excinfo:
        digitalocean.reboot(name="fake_name")

    assert "The reboot action must be called with -a or --action." == str(excinfo.value)
