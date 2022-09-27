"""
    :codeauthor: Nicole Thomas <nicole@saltstack.com>
"""


import logging

from salt.utils.versions import LooseVersion
from tests.integration.cloud.helpers.cloud_test_base import CloudTest
from tests.support.unit import skipIf

try:
    import azure  # pylint: disable=unused-import

    HAS_AZURE = True
except ImportError:
    HAS_AZURE = False

if HAS_AZURE and not hasattr(azure, "__version__"):
    import azure.common

log = logging.getLogger(__name__)

TIMEOUT = 1000
REQUIRED_AZURE = "1.1.0"


def __has_required_azure():
    """
    Returns True/False if the required version of the Azure SDK is installed.
    """
    if HAS_AZURE:
        if hasattr(azure, "__version__"):
            version = LooseVersion(azure.__version__)
        else:
            version = LooseVersion(azure.common.__version__)
        if LooseVersion(REQUIRED_AZURE) <= version:
            return True
    return False


@skipIf(not HAS_AZURE, "These tests require the Azure Python SDK to be installed.")
@skipIf(
    not __has_required_azure(),
    "The Azure Python SDK must be >= {}.".format(REQUIRED_AZURE),
)
class AzureTest(CloudTest):
    """
    Integration tests for the Azure cloud provider in Salt-Cloud
    """

    PROVIDER = "azurearm"
    REQUIRED_PROVIDER_CONFIG_ITEMS = ("subscription_id",)

    def test_instance(self):
        """
        Test creating an instance on Azure
        """
        # check if instance with salt installed returned
        ret_val = self.run_cloud(
            "-p azure-test {}".format(self.instance_name), timeout=TIMEOUT
        )
        self.assertInstanceExists(ret_val)
        self.assertDestroyInstance(timeout=TIMEOUT)
