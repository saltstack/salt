"""
    :codeauthor: :email:`Alexandru Bleotu <alexandru.bleotu@morganstanley.com>`
"""
import pytest
import salt.states.esxdatacenter as esxdatacenter
from salt.exceptions import CommandExecutionError
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {esxdatacenter: {}}


@pytest.fixture(scope="function")
def policy_set():
    patcher_1 = patcher_2 = None
    try:
        patcher_1 = patch.dict(esxdatacenter.__opts__, {"test": False})
        patcher_1.start()
        mock_si = MagicMock()
        mock_dc = MagicMock()
        patcher_2 = patch.dict(
            esxdatacenter.__salt__,
            {
                "vsphere.get_proxy_type": MagicMock(),
                "vsphere.get_service_instance_via_proxy": MagicMock(
                    return_value=mock_si
                ),
                "vsphere.list_datacenters_via_proxy": MagicMock(return_value=[mock_dc]),
                "vsphere.disconnect": MagicMock(),
            },
        )
        patcher_2.start()
        yield
    finally:
        if patcher_1:
            patcher_1.stop()
        if patcher_2:
            patcher_2.stop()


def test_dc_name_different_proxy(policy_set):
    with patch.dict(
        esxdatacenter.__salt__,
        {"vsphere.get_proxy_type": MagicMock(return_value="different_proxy")},
    ):
        res = esxdatacenter.datacenter_configured("fake_dc")
    assert res == {
        "name": "fake_dc",
        "changes": {},
        "result": True,
        "comment": "Datacenter 'fake_dc' already exists. Nothing to be done.",
    }


def test_dc_name_esxdatacenter_proxy(policy_set):
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
    assert res == {
        "name": "fake_dc",
        "changes": {},
        "result": True,
        "comment": "Datacenter 'proxy_dc' already exists. Nothing to be done.",
    }


def test_get_service_instance(policy_set):
    mock_get_service_instance = MagicMock()
    with patch.dict(
        esxdatacenter.__salt__,
        {"vsphere.get_service_instance_via_proxy": mock_get_service_instance},
    ):
        esxdatacenter.datacenter_configured("fake_dc")
    mock_get_service_instance.assert_called_once_with()


def test_list_datacenters(policy_set):
    mock_si = MagicMock()
    mock_list_datacenters = MagicMock()
    with patch.dict(
        esxdatacenter.__salt__,
        {
            "vsphere.get_proxy_type": MagicMock(),
            "vsphere.get_service_instance_via_proxy": MagicMock(return_value=mock_si),
            "vsphere.disconnect": MagicMock(),
            "vsphere.list_datacenters_via_proxy": mock_list_datacenters,
        },
    ):
        esxdatacenter.datacenter_configured("fake_dc")
        mock_list_datacenters.assert_called_once_with(
            datacenter_names=["fake_dc"], service_instance=mock_si
        )


def test_create_datacenter(policy_set):
    mock_create_datacenter = MagicMock()
    mock_si = MagicMock()
    with patch.dict(
        esxdatacenter.__salt__,
        {
            "vsphere.get_proxy_type": MagicMock(),
            "vsphere.get_service_instance_via_proxy": MagicMock(return_value=mock_si),
            "vsphere.disconnect": MagicMock(),
            "vsphere.list_datacenters_via_proxy": MagicMock(return_value=[]),
            "vsphere.create_datacenter": mock_create_datacenter,
        },
    ):
        res = esxdatacenter.datacenter_configured("fake_dc")
        mock_create_datacenter.assert_called_once_with("fake_dc", mock_si)
        assert res == {
            "name": "fake_dc",
            "changes": {"new": {"name": "fake_dc"}},
            "result": True,
            "comment": "Created datacenter 'fake_dc'.",
        }


def test_create_datacenter_test_mode(policy_set):
    with patch.dict(esxdatacenter.__opts__, {"test": True}):
        with patch.dict(
            esxdatacenter.__salt__,
            {"vsphere.list_datacenters_via_proxy": MagicMock(return_value=[])},
        ):
            res = esxdatacenter.datacenter_configured("fake_dc")
    assert res == {
        "name": "fake_dc",
        "changes": {"new": {"name": "fake_dc"}},
        "result": None,
        "comment": "State will create datacenter 'fake_dc'.",
    }


def test_nothing_to_be_done_test_mode(policy_set):
    with patch.dict(esxdatacenter.__opts__, {"test": True}):
        with patch.dict(
            esxdatacenter.__salt__,
            {"vsphere.get_proxy_type": MagicMock(return_value="different_proxy")},
        ):
            res = esxdatacenter.datacenter_configured("fake_dc")
    assert res == {
        "name": "fake_dc",
        "changes": {},
        "result": True,
        "comment": "Datacenter 'fake_dc' already exists. Nothing to be done.",
    }


def test_state_get_service_instance_raise_command_execution_error(policy_set):
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
    assert mock_disconnect.call_count == 0
    assert res == {
        "name": "fake_dc",
        "changes": {},
        "result": False,
        "comment": "Error",
    }


def test_state_raise_command_execution_error_after_si(policy_set):
    mock_disconnect = MagicMock()
    mock_si = MagicMock()
    with patch.dict(
        esxdatacenter.__salt__,
        {
            "vsphere.get_proxy_type": MagicMock(),
            "vsphere.get_service_instance_via_proxy": MagicMock(return_value=mock_si),
            "vsphere.disconnect": mock_disconnect,
            "vsphere.list_datacenters_via_proxy": MagicMock(
                side_effect=CommandExecutionError("Error")
            ),
        },
    ):
        res = esxdatacenter.datacenter_configured("fake_dc")
        mock_disconnect.assert_called_once_with(mock_si)
        assert res == {
            "name": "fake_dc",
            "changes": {},
            "result": False,
            "comment": "Error",
        }


def test_state_raise_command_execution_error_test_mode(policy_set):
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
    assert res == {"name": "fake_dc", "changes": {}, "result": None, "comment": "Error"}
