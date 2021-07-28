import logging

import salt.utils.azurearm as azurearm
from tests.support.unit import TestCase, skipIf

# Azure libs
# pylint: disable=import-error
HAS_LIBS = False
try:
    import azure.mgmt.compute.models  # pylint: disable=unused-import
    import azure.mgmt.network.models  # pylint: disable=unused-import

    HAS_LIBS = True
except ImportError:
    pass

# pylint: enable=import-error

log = logging.getLogger(__name__)

MOCK_CREDENTIALS = {
    "client_id": "CLIENT_ID",
    "secret": "SECRET",
    "subscription_id": "SUBSCRIPTION_ID",
    "tenant": "TENANT",
}


@skipIf(HAS_LIBS is False, "The azure.mgmt.network module must be installed.")
class AzureRmUtilsTestCase(TestCase):
    def test_create_object_model_vnet(self):
        module_name = "network"
        object_name = "VirtualNetwork"
        vnet = {
            "address_space": {"address_prefixes": ["10.0.0.0/8"]},
            "enable_ddos_protection": False,
            "enable_vm_protection": True,
            "tags": {"contact_name": "Elmer Fudd Gantry"},
        }
        model = azurearm.create_object_model(module_name, object_name, **vnet)
        self.assertEqual(vnet, model.as_dict())

    def test_create_object_model_nic_ref(self):
        module_name = "compute"
        object_name = "NetworkInterfaceReference"
        ref = {
            "id": "/subscriptions/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa/resourceGroups/rg/providers/Microsoft.Network/networkInterfaces/nic",
            "primary": False,
        }
        model = azurearm.create_object_model(module_name, object_name, **ref)
        self.assertEqual(ref, model.as_dict())
