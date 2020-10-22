"""
    :codeauthor: `Andreas Thienemann <andreas@bawue.net>`

    tests.unit.cloud.clouds.xen_test
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
"""

import logging

from salt.cloud.clouds import xen
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase

log = logging.getLogger(__name__)


class XenTestCase(TestCase, LoaderModuleMockMixin):
    """
    Unit TestCase for salt.cloud.clouds.xen module.
    """

    def setup_loader_modules(self):
        return {
            xen: {
                "__active_provider_name__": "",
                "__opts__": {
                    "providers": {
                        "my-xen-cloud": {
                            "xen": {
                                "driver": "xen",
                                "user": "SantaClaus",
                                "password": "TooManyElves",
                                "url": "https://127.0.0.2",
                            }
                        }
                    }
                },
            }
        }

    def test_get_configured_provider_bad(self):

        with patch.dict(xen.__opts__, {"providers": {}}):
            result = xen.get_configured_provider()
            self.assertEqual(result, False)

    def test_get_configured_provider_auth(self):
        config = {
            "url": "https://127.0.0.2",
        }
        with patch.dict(
            xen.__opts__, {"providers": {"my-xen-cloud": {"xen": config}}},
        ):
            result = xen.get_configured_provider()
            self.assertEqual(config, result)

    def test_get_dependencies(self):
        with patch("salt.cloud.clouds.xen.HAS_XEN_API", True):
            result = xen._get_dependencies()
            self.assertEqual(result, True)

    def test_get_dependencies_no_xenapi(self):
        with patch("salt.cloud.clouds.xen.HAS_XEN_API", False):
            result = xen._get_dependencies()
            self.assertEqual(result, False)

    def test_get_vm(self):
        XenAPI = MagicMock(name="mock_session")
        XenAPI.xenapi.VM.get_by_name_label = MagicMock(return_value=["0000"],)
        XenAPI.xenapi.VM.get_is_a_template = MagicMock(return_value=False)
        with patch(
            "salt.cloud.clouds.xen._get_session", MagicMock(return_value=XenAPI)
        ):
            result = xen._get_vm(name="test")
            self.assertEqual(result, "0000")

    def test_get_vm_multiple(self):
        """Verify correct behavior if VM and template is returned"""
        vms = {"0000": False, "0001": True}
        XenAPI = MagicMock(name="mock_session")
        XenAPI.xenapi.VM.get_by_name_label = MagicMock(return_value=vms.keys(),)
        XenAPI.xenapi.VM.get_is_a_template = MagicMock(side_effect=lambda x: vms[x])
        with patch(
            "salt.cloud.clouds.xen._get_session", MagicMock(return_value=XenAPI)
        ):
            result = xen._get_vm(name="test")
            self.assertEqual(result, "0000")
