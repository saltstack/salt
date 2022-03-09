"""
    :codeauthor: :email:`Alexandru Bleotu <alexandru.bleotu@morganstanley.com>`

    Tests for functions in salt.states.esxdatacenter
"""

import salt.states.esxdatacenter as esxdatacenter
from salt.exceptions import CommandExecutionError
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class DatacenterConfiguredTestCase(TestCase, LoaderModuleMockMixin):
    """Tests for salt.modules.esxdatacenter.datacenter_configured"""

    def setup_loader_modules(self):
        return {esxdatacenter: {}}

    def setUp(self):
        self.mock_si = MagicMock()
        self.mock_dc = MagicMock()

        patcher = patch.dict(
            esxdatacenter.__salt__,
            {
                "vsphere.get_proxy_type": MagicMock(),
                "vsphere.get_service_instance_via_proxy": MagicMock(
                    return_value=self.mock_si
                ),
                "vsphere.list_datacenters_via_proxy": MagicMock(
                    return_value=[self.mock_dc]
                ),
                "vsphere.disconnect": MagicMock(),
            },
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        patcher = patch.dict(esxdatacenter.__opts__, {"test": False})
        patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self):
        for attrname in ("mock_si",):
            try:
                delattr(self, attrname)
            except AttributeError:
                continue

    def test_dc_name_different_proxy(self):
        with patch.dict(
            esxdatacenter.__salt__,
            {"vsphere.get_proxy_type": MagicMock(return_value="different_proxy")},
        ):
            res = esxdatacenter.datacenter_configured("fake_dc")
        self.assertDictEqual(
            res,
            {
                "name": "fake_dc",
                "changes": {},
                "result": True,
                "comment": "Datacenter 'fake_dc' already exists. Nothing to be done.",
            },
        )

    def test_dc_name_esxdatacenter_proxy(self):
        with patch.dict(
            esxdatacenter.__salt__,
            {
                "vsphere.get_proxy_type": MagicMock(return_value="esxdatacenter"),
                "esxdatacenter.get_details": MagicMock(
                    return_value={"datacenter": "proxy_dc"}
                ),
            },
        ):
            res = esxdatacenter.datacenter_configured("fake_dc")
        self.assertDictEqual(
            res,
            {
                "name": "fake_dc",
                "changes": {},
                "result": True,
                "comment": "Datacenter 'proxy_dc' already exists. Nothing to be done.",
            },
        )

    def test_get_service_instance(self):
        mock_get_service_instance = MagicMock()
        with patch.dict(
            esxdatacenter.__salt__,
            {"vsphere.get_service_instance_via_proxy": mock_get_service_instance},
        ):
            esxdatacenter.datacenter_configured("fake_dc")
        mock_get_service_instance.assert_called_once_with()

    def test_list_datacenters(self):
        mock_list_datacenters = MagicMock()
        with patch.dict(
            esxdatacenter.__salt__,
            {"vsphere.list_datacenters_via_proxy": mock_list_datacenters},
        ):
            esxdatacenter.datacenter_configured("fake_dc")
        mock_list_datacenters.assert_called_once_with(
            datacenter_names=["fake_dc"], service_instance=self.mock_si
        )

    def test_create_datacenter(self):
        mock_create_datacenter = MagicMock()
        with patch.dict(
            esxdatacenter.__salt__,
            {
                "vsphere.list_datacenters_via_proxy": MagicMock(return_value=[]),
                "vsphere.create_datacenter": mock_create_datacenter,
            },
        ):
            res = esxdatacenter.datacenter_configured("fake_dc")
        mock_create_datacenter.assert_called_once_with("fake_dc", self.mock_si)
        self.assertDictEqual(
            res,
            {
                "name": "fake_dc",
                "changes": {"new": {"name": "fake_dc"}},
                "result": True,
                "comment": "Created datacenter 'fake_dc'.",
            },
        )

    def test_create_datacenter_test_mode(self):
        with patch.dict(esxdatacenter.__opts__, {"test": True}):
            with patch.dict(
                esxdatacenter.__salt__,
                {"vsphere.list_datacenters_via_proxy": MagicMock(return_value=[])},
            ):
                res = esxdatacenter.datacenter_configured("fake_dc")
        self.assertDictEqual(
            res,
            {
                "name": "fake_dc",
                "changes": {"new": {"name": "fake_dc"}},
                "result": None,
                "comment": "State will create datacenter 'fake_dc'.",
            },
        )

    def test_nothing_to_be_done_test_mode(self):
        with patch.dict(esxdatacenter.__opts__, {"test": True}):
            with patch.dict(
                esxdatacenter.__salt__,
                {"vsphere.get_proxy_type": MagicMock(return_value="different_proxy")},
            ):
                res = esxdatacenter.datacenter_configured("fake_dc")
        self.assertDictEqual(
            res,
            {
                "name": "fake_dc",
                "changes": {},
                "result": True,
                "comment": "Datacenter 'fake_dc' already exists. Nothing to be done.",
            },
        )

    def test_state_get_service_instance_raise_command_execution_error(self):
        mock_disconnect = MagicMock()
        with patch.dict(
            esxdatacenter.__salt__,
            {
                "vsphere.disconnect": mock_disconnect,
                "vsphere.get_service_instance_via_proxy": MagicMock(
                    side_effect=CommandExecutionError("Error")
                ),
            },
        ):
            res = esxdatacenter.datacenter_configured("fake_dc")
        self.assertEqual(mock_disconnect.call_count, 0)
        self.assertDictEqual(
            res, {"name": "fake_dc", "changes": {}, "result": False, "comment": "Error"}
        )

    def test_state_raise_command_execution_error_after_si(self):
        mock_disconnect = MagicMock()
        with patch.dict(
            esxdatacenter.__salt__,
            {
                "vsphere.disconnect": mock_disconnect,
                "vsphere.list_datacenters_via_proxy": MagicMock(
                    side_effect=CommandExecutionError("Error")
                ),
            },
        ):
            res = esxdatacenter.datacenter_configured("fake_dc")
        mock_disconnect.assert_called_once_with(self.mock_si)
        self.assertDictEqual(
            res, {"name": "fake_dc", "changes": {}, "result": False, "comment": "Error"}
        )

    def test_state_raise_command_execution_error_test_mode(self):
        with patch.dict(esxdatacenter.__opts__, {"test": True}):
            with patch.dict(
                esxdatacenter.__salt__,
                {
                    "vsphere.list_datacenters_via_proxy": MagicMock(
                        side_effect=CommandExecutionError("Error")
                    )
                },
            ):
                res = esxdatacenter.datacenter_configured("fake_dc")
        self.assertDictEqual(
            res, {"name": "fake_dc", "changes": {}, "result": None, "comment": "Error"}
        )
