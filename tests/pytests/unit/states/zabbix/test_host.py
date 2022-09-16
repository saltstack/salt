"""
    :codeauthor: Piter Punk <piterpunk@slackware.com>
"""

import ast
from collections import OrderedDict

import pytest

import salt.states.zabbix_host as zabbix_host
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {zabbix_host: {"__opts__": {"test": False}}}


@pytest.fixture()
def basic_host_configuration():
    host = "new_host"
    groups = ["Testing Group"]
    interfaces = [
        OrderedDict(
            [
                (
                    "basic_interface",
                    [
                        OrderedDict([("ip", "127.0.0.1")]),
                        OrderedDict([("type", "agent")]),
                    ],
                )
            ]
        )
    ]
    kwargs = {
        "_connection_user": "XXXXXXXXXX",
        "_connection_password": "XXXXXXXXXX",
        "_connection_url": "http://XXXXXXXXX/zabbix/api_jsonrpc.php",
    }

    ret = {
        "changes": {
            "new_host": {
                "new": "Host new_host created.",
                "old": "Host new_host does not exist.",
            }
        },
        "comment": "Host new_host created.",
        "name": "new_host",
        "result": True,
    }
    return host, groups, interfaces, kwargs, ret


@pytest.fixture()
def existing_host_responses():
    host_get_output = [
        {
            "hostid": "31337",
            "host": "new_host",
            "auto_compress": "1",
            "available": "1",
            "description": "",
            "disable_until": "0",
            "discover": "0",
            "error": "",
            "errors_from": "0",
            "flags": "0",
            "inventory_mode": "-1",
            "ipmi_authtype": "-1",
            "ipmi_available": "0",
            "ipmi_disable_until": "0",
            "ipmi_error": "",
            "ipmi_errors_from": "0",
            "ipmi_password": "",
            "ipmi_privilege": "2",
            "ipmi_username": "",
            "jmx_available": "0",
            "jmx_disable_until": "0",
            "jmx_error": "",
            "jmx_errors_from": "0",
            "lastaccess": "0",
            "maintenance_from": "0",
            "maintenance_status": "0",
            "maintenance_type": "0",
            "maintenanceid": "0",
            "name": "",
            "proxy_address": "",
            "proxy_hostid": "0",
            "snmp_available": "0",
            "snmp_disable_until": "0",
            "snmp_error": "",
            "snmp_errors_from": "0",
            "status": "0",
            "templateid": "0",
            "tls_accept": "1",
            "tls_connect": "1",
            "tls_issuer": "",
            "tls_psk": "",
            "tls_psk_identity": "",
            "tls_subject": "",
        }
    ]
    hostgroup_get_output_up = [
        {"groupid": "16", "name": "Testing Group", "internal": "0", "flags": "0"}
    ]
    hostinterface_get_output = [
        {
            "interfaceid": "29",
            "hostid": "31337",
            "main": "1",
            "type": "1",
            "useip": "1",
            "ip": "127.0.0.1",
            "dns": "basic_interface",
            "port": "10050",
            "details": [],
        }
    ]
    host_inventory_get_output = False

    return (
        host_get_output,
        hostgroup_get_output_up,
        hostinterface_get_output,
        host_inventory_get_output,
    )


def test_create_a_basic_new_host(basic_host_configuration):
    """
    This test creates a host with the minimum required parameters:

    host, groups, interfaces and _connection_args

    The "groups" should be converted to their numeric IDs and the
    hidden mandatory fields of interfaces should be populated.
    """
    host, groups, interfaces, kwargs, ret = basic_host_configuration

    hostgroup_get_output = [
        {"groupid": "16", "name": "Testing Group", "internal": "0", "flags": "0"}
    ]
    host_exists_output = False
    host_create_output = "31337"

    mock_hostgroup_get = MagicMock(return_value=hostgroup_get_output)
    mock_host_exists = MagicMock(return_value=host_exists_output)
    mock_host_create = MagicMock(return_value=host_create_output)
    with patch.dict(
        zabbix_host.__salt__,
        {
            "zabbix.hostgroup_get": mock_hostgroup_get,
            "zabbix.host_exists": mock_host_exists,
            "zabbix.host_create": mock_host_create,
        },
    ):
        assert zabbix_host.present(host, groups, interfaces, **kwargs) == ret
        mock_host_create.assert_called_with(
            "new_host",
            [16],
            [
                {
                    "type": "1",
                    "main": "1",
                    "useip": "1",
                    "ip": "127.0.0.1",
                    "dns": "basic_interface",
                    "port": "10050",
                    "details": [],
                }
            ],
            _connection_password="XXXXXXXXXX",
            _connection_url="http://XXXXXXXXX/zabbix/api_jsonrpc.php",
            _connection_user="XXXXXXXXXX",
            inventory={},
            proxy_hostid="0",
            visible_name=None,
        )


def test_create_a_new_host_with_multiple_groups(basic_host_configuration):
    """
    This test creates a host with multiple groups, mixing names and IDs.
    """
    host, _, interfaces, kwargs, ret = basic_host_configuration
    groups = ["Testing Group", 15, "Tested Group"]

    hostgroup_get_output = [
        [{"groupid": "16", "name": "Testing Group", "internal": "0", "flags": "0"}],
        [{"groupid": "17", "name": "Tested Group", "internal": "0", "flags": "0"}],
    ]
    host_exists_output = False
    host_create_output = "31337"

    mock_hostgroup_get = MagicMock(side_effect=hostgroup_get_output)
    mock_host_exists = MagicMock(return_value=host_exists_output)
    mock_host_create = MagicMock(return_value=host_create_output)
    with patch.dict(
        zabbix_host.__salt__,
        {
            "zabbix.hostgroup_get": mock_hostgroup_get,
            "zabbix.host_exists": mock_host_exists,
            "zabbix.host_create": mock_host_create,
        },
    ):
        assert zabbix_host.present(host, groups, interfaces, **kwargs) == ret
        mock_host_create.assert_called_with(
            "new_host",
            [16, 15, 17],
            [
                {
                    "type": "1",
                    "main": "1",
                    "useip": "1",
                    "ip": "127.0.0.1",
                    "dns": "basic_interface",
                    "port": "10050",
                    "details": [],
                }
            ],
            _connection_password="XXXXXXXXXX",
            _connection_url="http://XXXXXXXXX/zabbix/api_jsonrpc.php",
            _connection_user="XXXXXXXXXX",
            inventory={},
            proxy_hostid="0",
            visible_name=None,
        )


def test_create_a_new_host_with_multiple_interfaces(basic_host_configuration):
    """
    Tests the creation of a host with multiple interfaces. This creates
    one interface of each type, which needs to have their default
    parameters filled. Also, tests the different dns, ip and useip
    combinations.
    """
    host, groups, _, kwargs, ret = basic_host_configuration
    interfaces = [
        OrderedDict(
            [
                (
                    "agent_interface",
                    [
                        OrderedDict([("dns", "new_host")]),
                        OrderedDict([("type", "agent")]),
                    ],
                ),
                (
                    "snmp_interface",
                    [
                        OrderedDict([("ip", "127.0.0.1")]),
                        OrderedDict([("dns", "new_host")]),
                        OrderedDict([("useip", False)]),
                        OrderedDict([("type", "snmp")]),
                    ],
                ),
                (
                    "ipmi_interface",
                    [
                        OrderedDict([("ip", "127.0.0.1")]),
                        OrderedDict([("dns", "new_host")]),
                        OrderedDict([("type", "ipmi")]),
                    ],
                ),
                (
                    "jmx_interface",
                    [
                        OrderedDict([("ip", "127.0.0.1")]),
                        OrderedDict([("dns", "new_host")]),
                        OrderedDict([("useip", True)]),
                        OrderedDict([("type", "jmx")]),
                    ],
                ),
            ]
        )
    ]

    hostgroup_get_output = [
        [{"groupid": "16", "name": "Testing Group", "internal": "0", "flags": "0"}],
        [{"groupid": "17", "name": "Tested Group", "internal": "0", "flags": "0"}],
    ]
    host_exists_output = False
    host_create_output = "31337"

    mock_hostgroup_get = MagicMock(side_effect=hostgroup_get_output)
    mock_host_exists = MagicMock(return_value=host_exists_output)
    mock_host_create = MagicMock(return_value=host_create_output)
    with patch.dict(
        zabbix_host.__salt__,
        {
            "zabbix.hostgroup_get": mock_hostgroup_get,
            "zabbix.host_exists": mock_host_exists,
            "zabbix.host_create": mock_host_create,
        },
    ):
        assert zabbix_host.present(host, groups, interfaces, **kwargs) == ret
        # Blame Python 3.5 for this:
        host_create_call = mock_host_create.call_args[0]
        assert host_create_call[0] == "new_host"
        assert host_create_call[1] == [16]
        for interface in host_create_call[2]:
            if interface["type"] == "1":
                assert interface == {
                    "type": "1",
                    "main": "1",
                    "useip": "1",
                    "ip": "",
                    "dns": "new_host",
                    "port": "10050",
                    "details": [],
                }
            elif interface["type"] == "2":
                assert interface == {
                    "type": "2",
                    "main": "1",
                    "useip": "0",
                    "ip": "127.0.0.1",
                    "dns": "new_host",
                    "port": "161",
                    "details": {
                        "version": "2",
                        "bulk": "1",
                        "community": "{$SNMP_COMMUNITY}",
                    },
                }
            elif interface["type"] == "3":
                assert interface == {
                    "type": "3",
                    "main": "1",
                    "useip": "1",
                    "ip": "127.0.0.1",
                    "dns": "new_host",
                    "port": "623",
                    "details": [],
                }
            elif interface["type"] == "4":
                assert interface == {
                    "type": "4",
                    "main": "1",
                    "useip": "1",
                    "ip": "127.0.0.1",
                    "dns": "new_host",
                    "port": "12345",
                    "details": [],
                }
            else:
                assert interface["type"] == "Should be 1, 2, 3 or 4"


def test_create_a_new_host_with_additional_parameters(basic_host_configuration):
    """
    Tests if additional parameters, like "description" or "inventory_mode"
    are being properly passed to host_create. Also, checks if invalid
    parameters are filtered out.
    """
    host, groups, interfaces, kwargs, ret = basic_host_configuration
    kwargs["visible_name"] = "Visible Name"
    kwargs["description"] = "An amazing test host entry"
    kwargs["not_valid_property"] = "This should be removed"
    kwargs["inventory_mode"] = "0"

    hostgroup_get_output = [
        {"groupid": "16", "name": "Testing Group", "internal": "0", "flags": "0"}
    ]
    host_exists_output = False
    host_create_output = "31337"

    mock_hostgroup_get = MagicMock(return_value=hostgroup_get_output)
    mock_host_exists = MagicMock(return_value=host_exists_output)
    mock_host_create = MagicMock(return_value=host_create_output)
    with patch.dict(
        zabbix_host.__salt__,
        {
            "zabbix.hostgroup_get": mock_hostgroup_get,
            "zabbix.host_exists": mock_host_exists,
            "zabbix.host_create": mock_host_create,
        },
    ):
        assert zabbix_host.present(host, groups, interfaces, **kwargs) == ret
        mock_host_create.assert_called_with(
            "new_host",
            [16],
            [
                {
                    "type": "1",
                    "main": "1",
                    "useip": "1",
                    "ip": "127.0.0.1",
                    "dns": "basic_interface",
                    "port": "10050",
                    "details": [],
                }
            ],
            _connection_password="XXXXXXXXXX",
            _connection_url="http://XXXXXXXXX/zabbix/api_jsonrpc.php",
            _connection_user="XXXXXXXXXX",
            description="An amazing test host entry",
            inventory={},
            inventory_mode="0",
            proxy_hostid="0",
            visible_name="Visible Name",
        )


def test_create_a_new_host_with_proxy_by_name(basic_host_configuration):
    """
    Test the handling of proxy_host parameter when it is a name
    """
    host, groups, interfaces, kwargs, ret = basic_host_configuration
    kwargs["proxy_host"] = "RemoteProxy"

    hostgroup_get_output = [
        {"groupid": "16", "name": "Testing Group", "internal": "0", "flags": "0"}
    ]
    host_exists_output = False
    host_create_output = "31337"
    run_query_output = [
        {
            "proxyid": "10356",
            "interface": {
                "interfaceid": "56",
                "hostid": "10356",
                "main": "1",
                "type": "0",
                "useip": "1",
                "ip": "127.0.0.1",
                "dns": "remoteproxy.veryfar",
                "port": "10051",
                "details": [],
            },
        }
    ]

    mock_hostgroup_get = MagicMock(return_value=hostgroup_get_output)
    mock_host_exists = MagicMock(return_value=host_exists_output)
    mock_host_create = MagicMock(return_value=host_create_output)
    mock_run_query = MagicMock(return_value=run_query_output)
    with patch.dict(
        zabbix_host.__salt__,
        {
            "zabbix.hostgroup_get": mock_hostgroup_get,
            "zabbix.host_exists": mock_host_exists,
            "zabbix.host_create": mock_host_create,
            "zabbix.run_query": mock_run_query,
        },
    ):
        assert zabbix_host.present(host, groups, interfaces, **kwargs) == ret
        mock_host_create.assert_called_with(
            "new_host",
            [16],
            [
                {
                    "type": "1",
                    "main": "1",
                    "useip": "1",
                    "ip": "127.0.0.1",
                    "dns": "basic_interface",
                    "port": "10050",
                    "details": [],
                }
            ],
            _connection_password="XXXXXXXXXX",
            _connection_url="http://XXXXXXXXX/zabbix/api_jsonrpc.php",
            _connection_user="XXXXXXXXXX",
            inventory={},
            proxy_hostid="10356",
            visible_name=None,
        )


def test_create_a_new_host_with_proxy_by_id(basic_host_configuration):
    """
    Test the handling of proxy_host parameter when it is a proxyid
    """
    host, groups, interfaces, kwargs, ret = basic_host_configuration
    kwargs["proxy_host"] = 10356

    hostgroup_get_output = [
        {"groupid": "16", "name": "Testing Group", "internal": "0", "flags": "0"}
    ]
    host_exists_output = False
    host_create_output = "31337"
    run_query_output = [{"proxyid": "10356"}]

    mock_hostgroup_get = MagicMock(return_value=hostgroup_get_output)
    mock_host_exists = MagicMock(return_value=host_exists_output)
    mock_host_create = MagicMock(return_value=host_create_output)
    mock_run_query = MagicMock(return_value=run_query_output)
    with patch.dict(
        zabbix_host.__salt__,
        {
            "zabbix.hostgroup_get": mock_hostgroup_get,
            "zabbix.host_exists": mock_host_exists,
            "zabbix.host_create": mock_host_create,
            "zabbix.run_query": mock_run_query,
        },
    ):
        assert zabbix_host.present(host, groups, interfaces, **kwargs) == ret
        mock_host_create.assert_called_with(
            "new_host",
            [16],
            [
                {
                    "type": "1",
                    "main": "1",
                    "useip": "1",
                    "ip": "127.0.0.1",
                    "dns": "basic_interface",
                    "port": "10050",
                    "details": [],
                }
            ],
            _connection_password="XXXXXXXXXX",
            _connection_url="http://XXXXXXXXX/zabbix/api_jsonrpc.php",
            _connection_user="XXXXXXXXXX",
            inventory={},
            proxy_hostid="10356",
            visible_name=None,
        )


def test_create_a_new_host_with_missing_groups(basic_host_configuration):
    """
    Tests when any of the provided groups doesn't exists
    """
    host, _, interfaces, kwargs, _ = basic_host_configuration
    groups = ["Testing Group", "Missing Group"]

    ret = {
        "changes": {},
        "comment": "Invalid group Missing Group",
        "name": "new_host",
        "result": False,
    }

    hostgroup_get_output = [
        [{"groupid": "16", "name": "Testing Group", "internal": "0", "flags": "0"}],
        False,
    ]
    host_exists_output = False
    host_create_output = "31337"

    mock_hostgroup_get = MagicMock(side_effect=hostgroup_get_output)
    mock_host_exists = MagicMock(return_value=host_exists_output)
    mock_host_create = MagicMock(return_value=host_create_output)
    with patch.dict(
        zabbix_host.__salt__,
        {
            "zabbix.hostgroup_get": mock_hostgroup_get,
            "zabbix.host_exists": mock_host_exists,
            "zabbix.host_create": mock_host_create,
        },
    ):
        assert zabbix_host.present(host, groups, interfaces, **kwargs) == ret
        assert not mock_host_create.called, "host_create should not be called"


def test_create_a_new_host_with_missing_proxy(basic_host_configuration):
    """
    Tests when the given proxy_host doesn't exists
    """
    host, groups, interfaces, kwargs, _ = basic_host_configuration
    kwargs["proxy_host"] = 10356

    ret = {
        "changes": {},
        "comment": "Invalid proxy_host 10356",
        "name": "new_host",
        "result": False,
    }

    hostgroup_get_output = [
        {"groupid": "16", "name": "Testing Group", "internal": "0", "flags": "0"}
    ]
    host_exists_output = False
    host_create_output = "31337"
    run_query_output = False

    mock_hostgroup_get = MagicMock(return_value=hostgroup_get_output)
    mock_host_exists = MagicMock(return_value=host_exists_output)
    mock_run_query = MagicMock(return_value=run_query_output)
    mock_host_create = MagicMock(return_value=host_create_output)
    with patch.dict(
        zabbix_host.__salt__,
        {
            "zabbix.hostgroup_get": mock_hostgroup_get,
            "zabbix.host_exists": mock_host_exists,
            "zabbix.run_query": mock_run_query,
            "zabbix.host_create": mock_host_create,
        },
    ):
        assert zabbix_host.present(host, groups, interfaces, **kwargs) == ret
        assert not mock_host_create.called, "host_create should not be called"


def test_create_a_new_host_with_inventory_as_a_list(basic_host_configuration):
    """
    This test creates a host with a populated inventory declared as a list
    """
    host, groups, interfaces, kwargs, ret = basic_host_configuration
    inventory = (
        {"vendor": "FakeVendor"},
        {"asset_tag": "ABC12345"},
    )

    hostgroup_get_output = [
        {"groupid": "16", "name": "Testing Group", "internal": "0", "flags": "0"}
    ]
    host_exists_output = False
    host_create_output = "31337"

    mock_hostgroup_get = MagicMock(return_value=hostgroup_get_output)
    mock_host_exists = MagicMock(return_value=host_exists_output)
    mock_host_create = MagicMock(return_value=host_create_output)
    with patch.dict(
        zabbix_host.__salt__,
        {
            "zabbix.hostgroup_get": mock_hostgroup_get,
            "zabbix.host_exists": mock_host_exists,
            "zabbix.host_create": mock_host_create,
        },
    ):
        assert (
            zabbix_host.present(host, groups, interfaces, inventory=inventory, **kwargs)
            == ret
        )
        mock_host_create.assert_called_with(
            "new_host",
            [16],
            [
                {
                    "type": "1",
                    "main": "1",
                    "useip": "1",
                    "ip": "127.0.0.1",
                    "dns": "basic_interface",
                    "port": "10050",
                    "details": [],
                }
            ],
            _connection_password="XXXXXXXXXX",
            _connection_url="http://XXXXXXXXX/zabbix/api_jsonrpc.php",
            _connection_user="XXXXXXXXXX",
            inventory={"vendor": "FakeVendor", "asset_tag": "ABC12345"},
            proxy_hostid="0",
            visible_name=None,
        )


def test_create_a_new_host_with_inventory_as_a_dict(basic_host_configuration):
    """
    This test creates a host with a populated inventory declared as a dictionary
    """
    host, groups, interfaces, kwargs, ret = basic_host_configuration
    inventory = {
        "vendor": "FakeVendor",
        "asset_tag": "ABC12345",
    }

    hostgroup_get_output = [
        {"groupid": "16", "name": "Testing Group", "internal": "0", "flags": "0"}
    ]
    host_exists_output = False
    host_create_output = "31337"

    mock_hostgroup_get = MagicMock(return_value=hostgroup_get_output)
    mock_host_exists = MagicMock(return_value=host_exists_output)
    mock_host_create = MagicMock(return_value=host_create_output)
    with patch.dict(
        zabbix_host.__salt__,
        {
            "zabbix.hostgroup_get": mock_hostgroup_get,
            "zabbix.host_exists": mock_host_exists,
            "zabbix.host_create": mock_host_create,
        },
    ):
        assert (
            zabbix_host.present(host, groups, interfaces, inventory=inventory, **kwargs)
            == ret
        )
        mock_host_create.assert_called_with(
            "new_host",
            [16],
            [
                {
                    "type": "1",
                    "main": "1",
                    "useip": "1",
                    "ip": "127.0.0.1",
                    "dns": "basic_interface",
                    "port": "10050",
                    "details": [],
                }
            ],
            _connection_password="XXXXXXXXXX",
            _connection_url="http://XXXXXXXXX/zabbix/api_jsonrpc.php",
            _connection_user="XXXXXXXXXX",
            inventory={"vendor": "FakeVendor", "asset_tag": "ABC12345"},
            proxy_hostid="0",
            visible_name=None,
        )


def test_ensure_nothing_happens_when_host_is_in_desired_state(
    basic_host_configuration, existing_host_responses
):
    """
    Test to ensure that nothing happens when the state applied
    already corresponds to the host actual configuration.
    """
    host, groups, interfaces, kwargs, _ = basic_host_configuration
    (
        host_get_output,
        hostgroup_get_output_up,
        hostinterface_get_output,
        host_inventory_get_output,
    ) = existing_host_responses

    hostgroup_get_output = [
        [{"groupid": "16", "name": "Testing Group", "internal": "0", "flags": "0"}],
        hostgroup_get_output_up,
    ]
    host_exists_output = True
    host_create_output = "31337"

    ret = {
        "changes": {},
        "comment": "Host new_host already exists.",
        "name": "new_host",
        "result": True,
    }

    mock_hostgroup_get = MagicMock(side_effect=hostgroup_get_output)
    mock_host_exists = MagicMock(return_value=host_exists_output)
    mock_host_get = MagicMock(return_value=host_get_output)
    mock_hostinterface_get = MagicMock(return_value=hostinterface_get_output)
    mock_host_inventory_get = MagicMock(return_value=host_inventory_get_output)
    mock_host_update = MagicMock(return_value=False)
    with patch.dict(
        zabbix_host.__salt__,
        {
            "zabbix.hostgroup_get": mock_hostgroup_get,
            "zabbix.host_exists": mock_host_exists,
            "zabbix.host_get": mock_host_get,
            "zabbix.hostinterface_get": mock_hostinterface_get,
            "zabbix.host_inventory_get": mock_host_inventory_get,
            "zabbix.host_update": mock_host_update,
        },
    ):
        assert zabbix_host.present(host, groups, interfaces, **kwargs) == ret
        assert not mock_host_update.called, "host_update should not be called"


def test_change_a_host_group(basic_host_configuration, existing_host_responses):
    """
    Tests if the group of a host is changed when solicited
    """
    host, groups, interfaces, kwargs, _ = basic_host_configuration
    (
        host_get_output,
        hostgroup_get_output_up,
        hostinterface_get_output,
        host_inventory_get_output,
    ) = existing_host_responses

    hostgroup_get_output = [
        hostgroup_get_output_up,
        [{"groupid": "17", "name": "Actual Group", "internal": "0", "flags": "0"}],
    ]
    host_exists_output = True
    host_update_output = "31337"

    ret = {
        "changes": {"groups": "[16]"},
        "comment": "Host new_host updated.",
        "name": "new_host",
        "result": True,
    }

    mock_hostgroup_get = MagicMock(side_effect=hostgroup_get_output)
    mock_host_exists = MagicMock(return_value=host_exists_output)
    mock_host_get = MagicMock(return_value=host_get_output)
    mock_hostinterface_get = MagicMock(return_value=hostinterface_get_output)
    mock_host_inventory_get = MagicMock(return_value=host_inventory_get_output)
    mock_host_update = MagicMock(return_value=host_update_output)
    with patch.dict(
        zabbix_host.__salt__,
        {
            "zabbix.hostgroup_get": mock_hostgroup_get,
            "zabbix.host_exists": mock_host_exists,
            "zabbix.host_get": mock_host_get,
            "zabbix.hostinterface_get": mock_hostinterface_get,
            "zabbix.host_inventory_get": mock_host_inventory_get,
            "zabbix.host_update": mock_host_update,
        },
    ):
        assert zabbix_host.present(host, groups, interfaces, **kwargs) == ret
        mock_host_update.assert_called_with(
            "31337",
            groups=[16],
            _connection_password="XXXXXXXXXX",
            _connection_url="http://XXXXXXXXX/zabbix/api_jsonrpc.php",
            _connection_user="XXXXXXXXXX",
        )


def test_to_add_new_groups_to_a_host(basic_host_configuration, existing_host_responses):
    """
    Tests if new groups are added to a host
    """
    host, _, interfaces, kwargs, _ = basic_host_configuration
    (
        host_get_output,
        hostgroup_get_output_up,
        hostinterface_get_output,
        host_inventory_get_output,
    ) = existing_host_responses

    groups = ["Testing Group", 15, "Tested Group"]

    hostgroup_get_output = [
        hostgroup_get_output_up,
        [{"groupid": "17", "name": "Actual Group", "internal": "0", "flags": "0"}],
        hostgroup_get_output_up,
    ]
    host_exists_output = True
    host_update_output = "31337"

    ret = {
        "changes": {"groups": "[16, 15, 17]"},
        "comment": "Host new_host updated.",
        "name": "new_host",
        "result": True,
    }

    mock_hostgroup_get = MagicMock(side_effect=hostgroup_get_output)
    mock_host_exists = MagicMock(return_value=host_exists_output)
    mock_host_get = MagicMock(return_value=host_get_output)
    mock_hostinterface_get = MagicMock(return_value=hostinterface_get_output)
    mock_host_inventory_get = MagicMock(return_value=host_inventory_get_output)
    mock_host_update = MagicMock(return_value=host_update_output)
    with patch.dict(
        zabbix_host.__salt__,
        {
            "zabbix.hostgroup_get": mock_hostgroup_get,
            "zabbix.host_exists": mock_host_exists,
            "zabbix.host_get": mock_host_get,
            "zabbix.hostinterface_get": mock_hostinterface_get,
            "zabbix.host_inventory_get": mock_host_inventory_get,
            "zabbix.host_update": mock_host_update,
        },
    ):
        assert zabbix_host.present(host, groups, interfaces, **kwargs) == ret
        mock_host_update.assert_called_with(
            "31337",
            groups=[16, 15, 17],
            _connection_password="XXXXXXXXXX",
            _connection_url="http://XXXXXXXXX/zabbix/api_jsonrpc.php",
            _connection_user="XXXXXXXXXX",
        )


def test_update_an_existent_host_proxy(
    basic_host_configuration, existing_host_responses
):
    """
    Tests if the proxy of a host is updated to a new one.
    This also tests if a proxy can be added, as a host without a proxy
    have the proxy_hostid property equals zero.
    """
    host, groups, interfaces, kwargs, _ = basic_host_configuration
    (
        host_get_output,
        hostgroup_get_output,
        hostinterface_get_output,
        host_inventory_get_output,
    ) = existing_host_responses

    kwargs["proxy_host"] = 10356
    host_exists_output = True
    host_update_output = "31337"
    run_query_output = [{"proxyid": "10356"}]

    ret = {
        "changes": {"proxy_hostid": "10356"},
        "comment": "Host new_host updated.",
        "name": "new_host",
        "result": True,
    }

    mock_hostgroup_get = MagicMock(return_value=hostgroup_get_output)
    mock_host_exists = MagicMock(return_value=host_exists_output)
    mock_host_get = MagicMock(return_value=host_get_output)
    mock_hostinterface_get = MagicMock(return_value=hostinterface_get_output)
    mock_host_inventory_get = MagicMock(return_value=host_inventory_get_output)
    mock_host_update = MagicMock(return_value=host_update_output)
    mock_run_query = MagicMock(return_value=run_query_output)
    with patch.dict(
        zabbix_host.__salt__,
        {
            "zabbix.hostgroup_get": mock_hostgroup_get,
            "zabbix.host_exists": mock_host_exists,
            "zabbix.host_get": mock_host_get,
            "zabbix.hostinterface_get": mock_hostinterface_get,
            "zabbix.host_inventory_get": mock_host_inventory_get,
            "zabbix.host_update": mock_host_update,
            "zabbix.run_query": mock_run_query,
        },
    ):
        assert zabbix_host.present(host, groups, interfaces, **kwargs) == ret
        mock_host_update.assert_called_with(
            "31337",
            proxy_hostid="10356",
            _connection_password="XXXXXXXXXX",
            _connection_url="http://XXXXXXXXX/zabbix/api_jsonrpc.php",
            _connection_user="XXXXXXXXXX",
        )


def test_update_a_host_with_additional_parameters(
    basic_host_configuration, existing_host_responses
):
    """
    This test checks if additional parameters can be added to an
    existing host
    """
    host, groups, interfaces, kwargs, _ = basic_host_configuration
    (
        host_get_output,
        hostgroup_get_output,
        hostinterface_get_output,
        host_inventory_get_output,
    ) = existing_host_responses

    kwargs["inventory_mode"] = 0
    kwargs["description"] = "An amazing test host entry"
    host_exists_output = True
    host_update_output = "31337"

    ret = {
        "changes": {
            "host": "{'description': 'An amazing test host entry', 'inventory_mode': 0}"
        },
        "comment": "Host new_host updated.",
        "name": "new_host",
        "result": True,
    }

    mock_hostgroup_get = MagicMock(return_value=hostgroup_get_output)
    mock_host_exists = MagicMock(return_value=host_exists_output)
    mock_host_get = MagicMock(return_value=host_get_output)
    mock_hostinterface_get = MagicMock(return_value=hostinterface_get_output)
    mock_host_inventory_get = MagicMock(return_value=host_inventory_get_output)
    mock_host_update = MagicMock(return_value=host_update_output)
    with patch.dict(
        zabbix_host.__salt__,
        {
            "zabbix.hostgroup_get": mock_hostgroup_get,
            "zabbix.host_exists": mock_host_exists,
            "zabbix.host_get": mock_host_get,
            "zabbix.hostinterface_get": mock_hostinterface_get,
            "zabbix.host_inventory_get": mock_host_inventory_get,
            "zabbix.host_update": mock_host_update,
        },
    ):
        # Blame Python 3.5 support for all this black magic
        host_present_ret = zabbix_host.present(host, groups, interfaces, **kwargs)
        host_present_changes = ast.literal_eval(host_present_ret["changes"]["host"])
        assert host_present_changes == ast.literal_eval(ret["changes"]["host"])
        assert host_present_ret["comment"] == "Host new_host updated."
        assert host_present_ret["name"] == "new_host"
        assert host_present_ret["result"] is True
        # When Python 3.5 is gone, the following line does the job:
        # assert zabbix_host.present(host, groups, interfaces, **kwargs) == ret
        mock_host_update.assert_called_with(
            "31337",
            _connection_password="XXXXXXXXXX",
            _connection_url="http://XXXXXXXXX/zabbix/api_jsonrpc.php",
            _connection_user="XXXXXXXXXX",
            description="An amazing test host entry",
            inventory_mode=0,
        )


def test_update_a_hostinterface(basic_host_configuration, existing_host_responses):
    """
    Tests the update of a current hostinterface of a host.
    """
    host, groups, _, kwargs, _ = basic_host_configuration
    (
        host_get_output,
        hostgroup_get_output,
        hostinterface_get_output,
        host_inventory_get_output,
    ) = existing_host_responses

    interfaces = [
        OrderedDict(
            [
                (
                    "basic_interface",
                    [
                        OrderedDict([("dns", "new_host")]),
                        OrderedDict([("type", "agent")]),
                        OrderedDict([("useip", False)]),
                    ],
                ),
            ]
        )
    ]
    host_exists_output = True
    hostinterface_update_output = "29"

    ret = {
        "changes": {
            "interfaces": (
                "[{'type': '1', 'main': '1', 'useip': '0', 'ip': '', 'dns': 'new_host',"
                " 'port': '10050', 'details': []}]"
            )
        },
        "comment": "Host new_host updated.",
        "name": "new_host",
        "result": True,
    }

    mock_hostgroup_get = MagicMock(return_value=hostgroup_get_output)
    mock_host_exists = MagicMock(return_value=host_exists_output)
    mock_host_get = MagicMock(return_value=host_get_output)
    mock_hostinterface_get = MagicMock(return_value=hostinterface_get_output)
    mock_host_inventory_get = MagicMock(return_value=host_inventory_get_output)
    mock_hostinterface_update = MagicMock(return_value=hostinterface_update_output)
    with patch.dict(
        zabbix_host.__salt__,
        {
            "zabbix.hostgroup_get": mock_hostgroup_get,
            "zabbix.host_exists": mock_host_exists,
            "zabbix.host_get": mock_host_get,
            "zabbix.hostinterface_get": mock_hostinterface_get,
            "zabbix.host_inventory_get": mock_host_inventory_get,
            "zabbix.hostinterface_update": mock_hostinterface_update,
        },
    ):
        # Blame Python 3.5 support for all this black magic
        host_present_ret = zabbix_host.present(host, groups, interfaces, **kwargs)
        host_present_changes = ast.literal_eval(
            host_present_ret["changes"]["interfaces"]
        )
        assert host_present_changes == ast.literal_eval(ret["changes"]["interfaces"])
        assert host_present_ret["comment"] == "Host new_host updated."
        assert host_present_ret["name"] == "new_host"
        assert host_present_ret["result"] is True
        # When Python 3.5 is gone, the following line does the job:
        # assert zabbix_host.present(host, groups, interfaces, **kwargs) == ret
        mock_hostinterface_update.assert_called_with(
            interfaceid="29",
            ip="",
            dns="new_host",
            useip="0",
            type="1",
            main="1",
            port="10050",
            details=[],
            _connection_password="XXXXXXXXXX",
            _connection_url="http://XXXXXXXXX/zabbix/api_jsonrpc.php",
            _connection_user="XXXXXXXXXX",
        )


def test_add_a_new_hostinterface(basic_host_configuration, existing_host_responses):
    """
    Tests the update of a current and creation of a new hostinterface
    of a host.
    """
    host, groups, _, kwargs, _ = basic_host_configuration
    (
        host_get_output,
        hostgroup_get_output,
        hostinterface_get_output,
        host_inventory_get_output,
    ) = existing_host_responses

    interfaces = [
        OrderedDict(
            [
                (
                    "basic_interface",
                    [
                        OrderedDict([("dns", "new_host")]),
                        OrderedDict([("type", "agent")]),
                        OrderedDict([("useip", "0")]),
                    ],
                ),
                (
                    "ipmi_interface",
                    [
                        OrderedDict([("ip", "127.0.0.1")]),
                        OrderedDict([("dns", "new_host")]),
                        OrderedDict([("useip", False)]),
                        OrderedDict([("type", "ipmi")]),
                    ],
                ),
            ]
        )
    ]
    host_exists_output = True
    hostinterface_update_output = "29"
    hostinterface_create_output = "30"

    ret = {
        "changes": {
            "interfaces": (
                "[{'type': '1', 'main': '1', 'useip': '0', 'ip': '', 'dns': 'new_host',"
                " 'port': '10050', 'details': []}, {'type': '3', 'main': '1', 'useip':"
                " '0', 'ip': '127.0.0.1', 'dns': 'new_host', 'port': '623', 'details':"
                " []}]"
            )
        },
        "comment": "Host new_host updated.",
        "name": "new_host",
        "result": True,
    }

    mock_hostgroup_get = MagicMock(return_value=hostgroup_get_output)
    mock_host_exists = MagicMock(return_value=host_exists_output)
    mock_host_get = MagicMock(return_value=host_get_output)
    mock_hostinterface_get = MagicMock(return_value=hostinterface_get_output)
    mock_host_inventory_get = MagicMock(return_value=host_inventory_get_output)
    mock_hostinterface_update = MagicMock(return_value=hostinterface_update_output)
    mock_hostinterface_create = MagicMock(return_value=hostinterface_create_output)
    with patch.dict(
        zabbix_host.__salt__,
        {
            "zabbix.hostgroup_get": mock_hostgroup_get,
            "zabbix.host_exists": mock_host_exists,
            "zabbix.host_get": mock_host_get,
            "zabbix.hostinterface_get": mock_hostinterface_get,
            "zabbix.host_inventory_get": mock_host_inventory_get,
            "zabbix.hostinterface_update": mock_hostinterface_update,
            "zabbix.hostinterface_create": mock_hostinterface_create,
        },
    ):
        # Blame Python 3.5 support for all this black magic
        host_present_ret = zabbix_host.present(host, groups, interfaces, **kwargs)
        for interface in ast.literal_eval(host_present_ret["changes"]["interfaces"]):
            if interface["type"] == "1":
                assert interface == ast.literal_eval(ret["changes"]["interfaces"])[0]
            elif interface["type"] == "3":
                assert interface == ast.literal_eval(ret["changes"]["interfaces"])[1]
            else:
                assert interface["type"] == "Should be 1 or 3"
        assert host_present_ret["comment"] == "Host new_host updated."
        assert host_present_ret["name"] == "new_host"
        assert host_present_ret["result"] is True
        # When Python 3.5 is gone, the following line does the job:
        # assert zabbix_host.present(host, groups, interfaces, **kwargs) == ret
        mock_hostinterface_update.assert_called_with(
            interfaceid="29",
            ip="",
            dns="new_host",
            useip="0",
            type="1",
            main="1",
            port="10050",
            details=[],
            _connection_password="XXXXXXXXXX",
            _connection_url="http://XXXXXXXXX/zabbix/api_jsonrpc.php",
            _connection_user="XXXXXXXXXX",
        )
        mock_hostinterface_create.assert_called_with(
            "31337",
            "127.0.0.1",
            dns="new_host",
            useip="0",
            if_type="3",
            main="1",
            port="623",
            details=[],
            _connection_password="XXXXXXXXXX",
            _connection_url="http://XXXXXXXXX/zabbix/api_jsonrpc.php",
            _connection_user="XXXXXXXXXX",
        )


def test_update_inventory_values(basic_host_configuration, existing_host_responses):
    """
    Tests the update of an inventory value
    """
    host, groups, interfaces, kwargs, _ = basic_host_configuration
    (
        host_get_output,
        hostgroup_get_output,
        hostinterface_get_output,
        host_inventory_get_output,
    ) = existing_host_responses

    host_inventory_get_output = {
        "vendor": "FakeVendor",
        "asset_tag": "ABC12345",
    }
    hostgroup_get_output = [
        {"groupid": "16", "name": "Testing Group", "internal": "0", "flags": "0"}
    ]
    host_exists_output = True
    host_inventory_set_output = {"result": {"hostids": ["31337"]}}

    inventory = (
        {"vendor": "TrueVendor"},
        {"asset_tag": "ABC12345"},
    )
    ret = {
        "changes": {"inventory": "{'vendor': 'TrueVendor', 'asset_tag': 'ABC12345'}"},
        "comment": "Host new_host updated.",
        "name": "new_host",
        "result": True,
    }

    mock_hostgroup_get = MagicMock(return_value=hostgroup_get_output)
    mock_host_exists = MagicMock(return_value=host_exists_output)
    mock_host_get = MagicMock(return_value=host_get_output)
    mock_hostinterface_get = MagicMock(return_value=hostinterface_get_output)
    mock_host_inventory_get = MagicMock(return_value=host_inventory_get_output)
    mock_host_inventory_set = MagicMock(return_value=host_inventory_set_output)
    with patch.dict(
        zabbix_host.__salt__,
        {
            "zabbix.hostgroup_get": mock_hostgroup_get,
            "zabbix.host_exists": mock_host_exists,
            "zabbix.host_get": mock_host_get,
            "zabbix.hostinterface_get": mock_hostinterface_get,
            "zabbix.host_inventory_get": mock_host_inventory_get,
            "zabbix.host_inventory_set": mock_host_inventory_set,
        },
    ):
        # Blame Python 3.5 support for all this black magic
        host_present_ret = zabbix_host.present(
            host, groups, interfaces, inventory=inventory, **kwargs
        )
        host_present_changes = ast.literal_eval(
            host_present_ret["changes"]["inventory"]
        )
        assert host_present_changes == ast.literal_eval(ret["changes"]["inventory"])
        assert host_present_ret["comment"] == "Host new_host updated."
        assert host_present_ret["name"] == "new_host"
        assert host_present_ret["result"] is True
        # When Python 3.5 is gone, the following line does the job:
        # assert (
        #    zabbix_host.present(host, groups, interfaces, inventory=inventory, **kwargs)
        #    == ret
        # )
        mock_host_inventory_set.assert_called_with(
            "31337",
            _connection_password="XXXXXXXXXX",
            _connection_url="http://XXXXXXXXX/zabbix/api_jsonrpc.php",
            _connection_user="XXXXXXXXXX",
            asset_tag="ABC12345",
            clear_old=True,
            inventory_mode="0",
            vendor="TrueVendor",
        )


def test_update_inventory_keys(basic_host_configuration, existing_host_responses):
    """
    Tests the update of a inventory keys
    """
    host, groups, interfaces, kwargs, _ = basic_host_configuration
    (
        host_get_output,
        hostgroup_get_output,
        hostinterface_get_output,
        host_inventory_get_output,
    ) = existing_host_responses

    host_inventory_get_output = {
        "vendor": "FakeVendor",
        "asset_tag": "ABC12345",
    }
    hostgroup_get_output = [
        {"groupid": "16", "name": "Testing Group", "internal": "0", "flags": "0"}
    ]
    host_exists_output = True
    host_inventory_set_output = {"result": {"hostids": ["31337"]}}

    inventory = (
        {"vendor": "TrueVendor"},
        {"serialno_a": "123751236JJ123K"},
    )
    ret = {
        "changes": {
            "inventory": "{'vendor': 'TrueVendor', 'serialno_a': '123751236JJ123K'}"
        },
        "comment": "Host new_host updated.",
        "name": "new_host",
        "result": True,
    }

    mock_hostgroup_get = MagicMock(return_value=hostgroup_get_output)
    mock_host_exists = MagicMock(return_value=host_exists_output)
    mock_host_get = MagicMock(return_value=host_get_output)
    mock_hostinterface_get = MagicMock(return_value=hostinterface_get_output)
    mock_host_inventory_get = MagicMock(return_value=host_inventory_get_output)
    mock_host_inventory_set = MagicMock(return_value=host_inventory_set_output)
    with patch.dict(
        zabbix_host.__salt__,
        {
            "zabbix.hostgroup_get": mock_hostgroup_get,
            "zabbix.host_exists": mock_host_exists,
            "zabbix.host_get": mock_host_get,
            "zabbix.hostinterface_get": mock_hostinterface_get,
            "zabbix.host_inventory_get": mock_host_inventory_get,
            "zabbix.host_inventory_set": mock_host_inventory_set,
        },
    ):
        # Blame Python 3.5 support for all this black magic
        host_present_ret = zabbix_host.present(
            host, groups, interfaces, inventory=inventory, **kwargs
        )
        host_present_changes = ast.literal_eval(
            host_present_ret["changes"]["inventory"]
        )
        assert host_present_changes == ast.literal_eval(ret["changes"]["inventory"])
        assert host_present_ret["comment"] == "Host new_host updated."
        assert host_present_ret["name"] == "new_host"
        assert host_present_ret["result"] is True
        # When Python 3.5 is gone, the following line does the job:
        # assert (
        #    zabbix_host.present(host, groups, interfaces, inventory=inventory, **kwargs)
        #    == ret
        # )
        mock_host_inventory_set.assert_called_with(
            "31337",
            _connection_password="XXXXXXXXXX",
            _connection_url="http://XXXXXXXXX/zabbix/api_jsonrpc.php",
            _connection_user="XXXXXXXXXX",
            clear_old=True,
            inventory_mode="0",
            serialno_a="123751236JJ123K",
            vendor="TrueVendor",
        )


def test_update_inventory_values_without_clear_existing_data(
    basic_host_configuration, existing_host_responses
):
    """
    Tests the update of an inventory value without clear the current inventory
    """
    host, groups, interfaces, kwargs, _ = basic_host_configuration
    (
        host_get_output,
        hostgroup_get_output,
        hostinterface_get_output,
        host_inventory_get_output,
    ) = existing_host_responses

    host_inventory_get_output = {
        "vendor": "FakeVendor",
        "asset_tag": "ABC12345",
    }
    hostgroup_get_output = [
        {"groupid": "16", "name": "Testing Group", "internal": "0", "flags": "0"}
    ]
    host_exists_output = True
    host_inventory_set_output = {"result": {"hostids": ["31337"]}}

    inventory = ({"vendor": "TrueVendor"},)
    ret = {
        "changes": {"inventory": "{'vendor': 'TrueVendor'}"},
        "comment": "Host new_host updated.",
        "name": "new_host",
        "result": True,
    }

    mock_hostgroup_get = MagicMock(return_value=hostgroup_get_output)
    mock_host_exists = MagicMock(return_value=host_exists_output)
    mock_host_get = MagicMock(return_value=host_get_output)
    mock_hostinterface_get = MagicMock(return_value=hostinterface_get_output)
    mock_host_inventory_get = MagicMock(return_value=host_inventory_get_output)
    mock_host_inventory_set = MagicMock(return_value=host_inventory_set_output)
    with patch.dict(
        zabbix_host.__salt__,
        {
            "zabbix.hostgroup_get": mock_hostgroup_get,
            "zabbix.host_exists": mock_host_exists,
            "zabbix.host_get": mock_host_get,
            "zabbix.hostinterface_get": mock_hostinterface_get,
            "zabbix.host_inventory_get": mock_host_inventory_get,
            "zabbix.host_inventory_set": mock_host_inventory_set,
        },
    ):
        # Blame Python 3.5 support for all this black magic
        host_present_ret = zabbix_host.present(
            host,
            groups,
            interfaces,
            inventory=inventory,
            inventory_clean=False,
            **kwargs
        )
        host_present_changes = ast.literal_eval(
            host_present_ret["changes"]["inventory"]
        )
        assert host_present_changes == ast.literal_eval(ret["changes"]["inventory"])
        assert host_present_ret["comment"] == "Host new_host updated."
        assert host_present_ret["name"] == "new_host"
        assert host_present_ret["result"] is True
        # When Python 3.5 is gone, the following line does the job:
        # assert (
        #    zabbix_host.present(
        #        host,
        #        groups,
        #        interfaces,
        #        inventory=inventory,
        #        inventory_clean=False,
        #        **kwargs
        #    )
        #    == ret
        # )
        mock_host_inventory_set.assert_called_with(
            "31337",
            _connection_password="XXXXXXXXXX",
            _connection_url="http://XXXXXXXXX/zabbix/api_jsonrpc.php",
            _connection_user="XXXXXXXXXX",
            clear_old=False,
            inventory_mode="0",
            vendor="TrueVendor",
        )


def test_ensure_nothing_happens_when_inventory_is_not_sent(
    basic_host_configuration, existing_host_responses
):
    """
    Test to ensure that the current inventory is not erased when inventory is not sent
    """
    host, groups, interfaces, kwargs, _ = basic_host_configuration
    (
        host_get_output,
        hostgroup_get_output_up,
        hostinterface_get_output,
        _,
    ) = existing_host_responses

    host_inventory_get_output = {
        "vendor": "FakeVendor",
        "asset_tag": "ABC12345",
    }
    hostgroup_get_output = [
        [{"groupid": "16", "name": "Testing Group", "internal": "0", "flags": "0"}],
        hostgroup_get_output_up,
    ]
    host_exists_output = True

    ret = {
        "changes": {},
        "comment": "Host new_host already exists.",
        "name": "new_host",
        "result": True,
    }

    mock_hostgroup_get = MagicMock(side_effect=hostgroup_get_output)
    mock_host_exists = MagicMock(return_value=host_exists_output)
    mock_host_get = MagicMock(return_value=host_get_output)
    mock_hostinterface_get = MagicMock(return_value=hostinterface_get_output)
    mock_host_inventory_get = MagicMock(return_value=host_inventory_get_output)
    mock_host_inventory_set = MagicMock(return_value=False)
    with patch.dict(
        zabbix_host.__salt__,
        {
            "zabbix.hostgroup_get": mock_hostgroup_get,
            "zabbix.host_exists": mock_host_exists,
            "zabbix.host_get": mock_host_get,
            "zabbix.hostinterface_get": mock_hostinterface_get,
            "zabbix.host_inventory_get": mock_host_inventory_get,
            "zabbix.host_inventory_set": mock_host_inventory_set,
        },
    ):
        assert zabbix_host.present(host, groups, interfaces, **kwargs) == ret
        assert (
            not mock_host_inventory_set.called
        ), "host_inventory_set should not be called"


def test_ensure_that_inventory_is_not_sent_when_inventory_disabled(
    basic_host_configuration, existing_host_responses
):
    """
    Test to ensure that the inventory is not set when inventory_mode is disabled
    """
    host, groups, interfaces, kwargs, _ = basic_host_configuration
    (
        host_get_output,
        hostgroup_get_output_up,
        hostinterface_get_output,
        host_inventory_get_output,
    ) = existing_host_responses

    hostgroup_get_output = [
        [{"groupid": "16", "name": "Testing Group", "internal": "0", "flags": "0"}],
        hostgroup_get_output_up,
    ]
    host_exists_output = True

    kwargs["inventory_mode"] = "-1"
    inventory = ({"vendor": "TrueVendor"},)
    ret = {
        "changes": {},
        "comment": "Host new_host already exists.",
        "name": "new_host",
        "result": True,
    }

    mock_hostgroup_get = MagicMock(side_effect=hostgroup_get_output)
    mock_host_exists = MagicMock(return_value=host_exists_output)
    mock_host_get = MagicMock(return_value=host_get_output)
    mock_hostinterface_get = MagicMock(return_value=hostinterface_get_output)
    mock_host_inventory_get = MagicMock(return_value=host_inventory_get_output)
    mock_host_inventory_set = MagicMock(return_value=False)
    with patch.dict(
        zabbix_host.__salt__,
        {
            "zabbix.hostgroup_get": mock_hostgroup_get,
            "zabbix.host_exists": mock_host_exists,
            "zabbix.host_get": mock_host_get,
            "zabbix.hostinterface_get": mock_hostinterface_get,
            "zabbix.host_inventory_get": mock_host_inventory_get,
            "zabbix.host_inventory_set": mock_host_inventory_set,
        },
    ):
        assert (
            zabbix_host.present(host, groups, interfaces, inventory=inventory, **kwargs)
            == ret
        )
        assert (
            not mock_host_inventory_set.called
        ), "host_inventory_set should not be called"


def test_update_inventory_and_restore_inventory_mode(
    basic_host_configuration, existing_host_responses
):
    """
    Tests the restore of inventory_mode to automatic after update
    """
    host, groups, interfaces, kwargs, _ = basic_host_configuration
    (
        host_get_output,
        hostgroup_get_output,
        hostinterface_get_output,
        host_inventory_get_output,
    ) = existing_host_responses

    host_get_output[0]["inventory_mode"] = "1"
    host_inventory_get_output = {
        "vendor": "FakeVendor",
        "asset_tag": "ABC12345",
    }
    hostgroup_get_output = [
        {"groupid": "16", "name": "Testing Group", "internal": "0", "flags": "0"}
    ]
    host_exists_output = True
    host_inventory_set_output = {"result": {"hostids": ["31337"]}}
    host_update_output = "31337"

    kwargs["inventory_mode"] = "1"
    inventory = (
        {"vendor": "TrueVendor"},
        {"asset_tag": "ABC12345"},
    )

    ret = {
        "changes": {"inventory": "{'vendor': 'TrueVendor', 'asset_tag': 'ABC12345'}"},
        "comment": "Host new_host updated.",
        "name": "new_host",
        "result": True,
    }

    mock_hostgroup_get = MagicMock(return_value=hostgroup_get_output)
    mock_host_exists = MagicMock(return_value=host_exists_output)
    mock_host_get = MagicMock(return_value=host_get_output)
    mock_hostinterface_get = MagicMock(return_value=hostinterface_get_output)
    mock_host_inventory_get = MagicMock(return_value=host_inventory_get_output)
    mock_host_inventory_set = MagicMock(return_value=host_inventory_set_output)
    with patch.dict(
        zabbix_host.__salt__,
        {
            "zabbix.hostgroup_get": mock_hostgroup_get,
            "zabbix.host_exists": mock_host_exists,
            "zabbix.host_get": mock_host_get,
            "zabbix.hostinterface_get": mock_hostinterface_get,
            "zabbix.host_inventory_get": mock_host_inventory_get,
            "zabbix.host_inventory_set": mock_host_inventory_set,
        },
    ):
        # Blame Python 3.5 support for all this black magic
        host_present_ret = zabbix_host.present(
            host, groups, interfaces, inventory=inventory, **kwargs
        )
        host_present_changes = ast.literal_eval(
            host_present_ret["changes"]["inventory"]
        )
        assert host_present_changes == ast.literal_eval(ret["changes"]["inventory"])
        assert host_present_ret["comment"] == "Host new_host updated."
        assert host_present_ret["name"] == "new_host"
        assert host_present_ret["result"] is True
        # When Python 3.5 is gone, the following line does the job:
        # assert (
        #    zabbix_host.present(host, groups, interfaces, inventory=inventory, **kwargs)
        #    == ret
        # )
        mock_host_inventory_set.assert_called_with(
            "31337",
            _connection_password="XXXXXXXXXX",
            _connection_url="http://XXXXXXXXX/zabbix/api_jsonrpc.php",
            _connection_user="XXXXXXXXXX",
            asset_tag="ABC12345",
            clear_old=True,
            inventory_mode="1",
            vendor="TrueVendor",
        )


def test_clear_inventory_value_sending_an_empty_key(
    basic_host_configuration, existing_host_responses
):
    """
    Tests clear an specific value sending it as an empty string
    """
    host, groups, interfaces, kwargs, _ = basic_host_configuration
    (
        host_get_output,
        hostgroup_get_output,
        hostinterface_get_output,
        host_inventory_get_output,
    ) = existing_host_responses

    host_inventory_get_output = {
        "vendor": "FakeVendor",
        "asset_tag": "ABC12345",
    }
    hostgroup_get_output = [
        {"groupid": "16", "name": "Testing Group", "internal": "0", "flags": "0"}
    ]
    host_exists_output = True
    host_inventory_set_output = {"result": {"hostids": ["31337"]}}

    inventory = (
        {"vendor": "TrueVendor"},
        {"asset_tag": ""},
    )
    ret = {
        "changes": {"inventory": "{'vendor': 'TrueVendor', 'asset_tag': ''}"},
        "comment": "Host new_host updated.",
        "name": "new_host",
        "result": True,
    }

    mock_hostgroup_get = MagicMock(return_value=hostgroup_get_output)
    mock_host_exists = MagicMock(return_value=host_exists_output)
    mock_host_get = MagicMock(return_value=host_get_output)
    mock_hostinterface_get = MagicMock(return_value=hostinterface_get_output)
    mock_host_inventory_get = MagicMock(return_value=host_inventory_get_output)
    mock_host_inventory_set = MagicMock(return_value=host_inventory_set_output)
    with patch.dict(
        zabbix_host.__salt__,
        {
            "zabbix.hostgroup_get": mock_hostgroup_get,
            "zabbix.host_exists": mock_host_exists,
            "zabbix.host_get": mock_host_get,
            "zabbix.hostinterface_get": mock_hostinterface_get,
            "zabbix.host_inventory_get": mock_host_inventory_get,
            "zabbix.host_inventory_set": mock_host_inventory_set,
        },
    ):
        # Blame Python 3.5 support for all this black magic
        host_present_ret = zabbix_host.present(
            host,
            groups,
            interfaces,
            inventory=inventory,
            inventory_clean=False,
            **kwargs
        )
        host_present_changes = ast.literal_eval(
            host_present_ret["changes"]["inventory"]
        )
        assert host_present_changes == ast.literal_eval(ret["changes"]["inventory"])
        assert host_present_ret["comment"] == "Host new_host updated."
        assert host_present_ret["name"] == "new_host"
        assert host_present_ret["result"] is True
        # When Python 3.5 is gone, the following line does the job:
        # assert (
        #    zabbix_host.present(
        #        host,
        #        groups,
        #        interfaces,
        #        inventory=inventory,
        #        inventory_clean=False,
        #        **kwargs
        #    )
        #    == ret
        # )
        mock_host_inventory_set.assert_called_with(
            "31337",
            _connection_password="XXXXXXXXXX",
            _connection_url="http://XXXXXXXXX/zabbix/api_jsonrpc.php",
            _connection_user="XXXXXXXXXX",
            asset_tag="",
            clear_old=False,
            inventory_mode="0",
            vendor="TrueVendor",
        )
