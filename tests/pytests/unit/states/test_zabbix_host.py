"""
    :codeauthor: Piter Punk <piterpunk@slackware.com>
"""

from collections import OrderedDict

import pytest
import salt.states.zabbix_host as zabbix_host
from tests.support.mock import MagicMock, patch


@pytest.fixture(autouse=True)
def setup_loader():
    setup_loader_modules = {zabbix_host: {"__opts__": {"test": False}}}
    with pytest.helpers.loader_mock(setup_loader_modules) as loader_mock:
        yield loader_mock


def test_create_a_basic_new_host():
    """
    This test creates a host with the minimum required parameters:

    host, groups, interfaces and _connection_args

    The "groups" should be converted to their numeric IDs and the
    hidden mandatory fields of interfaces should be populated.
    """
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


def test_create_a_new_host_with_multiple_groups():
    """
    This test creates a host with multiple groups, mixing names and IDs.
    """
    host = "new_host"
    groups = ["Testing Group", 15, "Tested Group"]
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


def test_create_a_new_host_with_multiple_interfaces():
    """
    Tests the creation of a host with multiple interfaces. This creates
    one interface of each type, which needs to have their default
    parameters filled. Also, tests the different dns, ip and useip
    combinations.
    """
    host = "new_host"
    groups = ["Testing Group", 15, "Tested Group"]
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
    kwargs = {
        "_connection_user": "XXXXXXXXXX",
        "_connection_password": "XXXXXXXXXX",
        "_connection_url": "http://XXXXXXXXX/zabbix/api_jsonrpc.php",
    }

    host_created_with = "a"

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
                    "ip": "",
                    "dns": "new_host",
                    "port": "10050",
                    "details": [],
                },
                {
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
                },
                {
                    "type": "3",
                    "main": "1",
                    "useip": "1",
                    "ip": "127.0.0.1",
                    "dns": "new_host",
                    "port": "623",
                    "details": [],
                },
                {
                    "type": "4",
                    "main": "1",
                    "useip": "1",
                    "ip": "127.0.0.1",
                    "dns": "new_host",
                    "port": "12345",
                    "details": [],
                },
            ],
            _connection_password="XXXXXXXXXX",
            _connection_url="http://XXXXXXXXX/zabbix/api_jsonrpc.php",
            _connection_user="XXXXXXXXXX",
            inventory={},
            proxy_hostid="0",
            visible_name=None,
        )


def test_create_a_new_host_with_additional_parameters():
    """
    Tests if additional parameters, like "description" or "inventory_mode"
    are being properly passed to host_create. Also, checks if invalid
    parameters are filtered out.
    """
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
        "visible_name": "Visible Name",
        "description": "An amazing test host entry",
        "not_valid_property": "This should be removed",
        "inventory_mode": "0",
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


def test_create_a_new_host_with_proxy_by_name():
    """
    Test the handling of proxy_host parameter when it is a name
    """
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
        "proxy_host": "RemoteProxy",
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


def test_create_a_new_host_with_proxy_by_id():
    """
    Test the handling of proxy_host parameter when it is a proxyid
    """
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
        "proxy_host": 10356,
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


def test_create_a_new_host_with_missing_groups():
    host = "new_host"
    groups = ["Testing Group", "Missing Group"]
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
    # we should never reach the host_create call, but let's prevent collateral
    # damages by keeping it mocked
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


def test_create_a_new_host_with_missing_proxy():
    """
    Tests when the given proxy_host doesn't exists
    """
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
        "proxy_host": 10356,
        "_connection_user": "XXXXXXXXXX",
        "_connection_password": "XXXXXXXXXX",
        "_connection_url": "http://XXXXXXXXX/zabbix/api_jsonrpc.php",
    }

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
    # we should never reach the host_create call, but let's prevent collateral
    # damages by keeping it mocked
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


# def test_update_an_existent_host_adding_group():
#    assert False
#
# def test_update_an_existent_host_to_different_proxy():
#    assert False
#
# def test_update_an_existent_host_existent_interfaces():
#    assert False
#
# def test_update_an_existent_host_adding_interfaces():
#    assert False
#
# def test_update_an_existent_host_with_additional_parameters():
#    assert False
