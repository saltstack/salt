"""
    :codeauthor: Tyler Johnson <tjohnson@saltstack.com>
"""

import io
import textwrap
import urllib

import pytest
import requests

from salt import config
from salt.cloud.clouds import proxmox
from tests.support.mock import ANY, MagicMock, call, patch


@pytest.fixture
def profile():
    return {
        "my_proxmox": {
            "provider": "my_proxmox",
            "image": "local:some_image.tgz",
        }
    }


@pytest.fixture
def provider_config(profile):
    return {
        "my_proxmox": {
            "proxmox": {
                "driver": "proxmox",
                "url": "pve@domain.com",
                "user": "cloud@pve",
                "password": "verybadpass",
                "profiles": profile,
            }
        }
    }


@pytest.fixture
def vm():
    return {
        "profile": "my_proxmox",
        "name": "vm4",
        "driver": "proxmox",
        "technology": "qemu",
        "host": "127.0.0.1",
        "clone": True,
        "ide0": "data",
        "sata0": "data",
        "scsi0": "data",
        "net0": "a=b,c=d",
    }


@pytest.fixture
def configure_loader_modules(profile, provider_config):
    return {
        proxmox: {
            "__utils__": {
                "cloud.fire_event": MagicMock(),
                "cloud.filter_event": MagicMock(),
                "cloud.bootstrap": MagicMock(),
            },
            "__opts__": {
                "sock_dir": True,
                "transport": True,
                "providers": provider_config,
                "profiles": profile,
            },
            "__active_provider_name__": "my_proxmox:proxmox",
        }
    }


def test__stringlist_to_dictionary():
    result = proxmox._stringlist_to_dictionary("")
    assert result == {}

    result = proxmox._stringlist_to_dictionary(
        "foo=bar, ignored_space=bar,internal space=bar"
    )
    assert result == {"foo": "bar", "ignored_space": "bar", "internal space": "bar"}

    # Negative cases
    pytest.raises(ValueError, proxmox._stringlist_to_dictionary, "foo=bar,foo")
    pytest.raises(
        ValueError,
        proxmox._stringlist_to_dictionary,
        "foo=bar,totally=invalid=assignment",
    )


def test__dictionary_to_stringlist():
    result = proxmox._dictionary_to_stringlist({})
    assert result == ""

    result = proxmox._dictionary_to_stringlist({"a": "a"})
    assert result == "a=a"

    result = proxmox._dictionary_to_stringlist({"a": "a", "b": "b"})
    assert result == "a=a,b=b"


def test__reconfigure_clone_net_hdd(vm):
    # The return_value is for the net reconfigure assertions, it is irrelevant for the rest
    with patch(
        "salt.cloud.clouds.proxmox._get_properties",
        MagicMock(return_value=["net0", "ide0", "sata0", "scsi0"]),
    ), patch.object(
        proxmox, "query", return_value={"net0": "c=overwritten,g=h"}
    ) as query:
        # Test a vm that lacks the required attributes
        proxmox._reconfigure_clone({}, 0)
        query.assert_not_called()

        # Test a fully mocked vm
        proxmox._reconfigure_clone(vm, 0)

        # net reconfigure
        query.assert_any_call("get", "nodes/127.0.0.1/qemu/0/config")
        query.assert_any_call(
            "post", "nodes/127.0.0.1/qemu/0/config", {"net0": "a=b,c=d,g=h"}
        )

        # hdd reconfigure
        query.assert_any_call("post", "nodes/127.0.0.1/qemu/0/config", {"ide0": "data"})
        query.assert_any_call(
            "post", "nodes/127.0.0.1/qemu/0/config", {"sata0": "data"}
        )
        query.assert_any_call(
            "post", "nodes/127.0.0.1/qemu/0/config", {"scsi0": "data"}
        )


def test__reconfigure_clone_params():
    """
    Test cloning a VM with parameters to be reconfigured.
    """
    vmid = 201
    properties = {
        "ide2": "cdrom",
        "sata1": "satatest",
        "scsi0": "bootvol",
        "net0": "model=virtio",
        "agent": "1",
        "args": "argsvalue",
        "balloon": "128",
        "ciuser": "root",
        "cores": "2",
        "description": "desc",
        "memory": "256",
        "name": "new2",
        "onboot": "0",
        "sshkeys": "ssh-rsa ABCDEF user@host\n",
    }
    query_calls = [call("get", f"nodes/myhost/qemu/{vmid}/config")]
    for key, value in properties.items():
        if key == "sshkeys":
            value = urllib.parse.quote(value, safe="")
        query_calls.append(
            call(
                "post",
                f"nodes/myhost/qemu/{vmid}/config",
                {key: value},
            )
        )

    mock_query = MagicMock(return_value="")
    with patch(
        "salt.cloud.clouds.proxmox._get_properties",
        MagicMock(return_value=list(properties.keys())),
    ), patch("salt.cloud.clouds.proxmox.query", mock_query):
        vm_ = {
            "profile": "my_proxmox",
            "driver": "proxmox",
            "technology": "qemu",
            "name": "new2",
            "host": "myhost",
            "clone": True,
            "clone_from": 123,
            "ip_address": "10.10.10.10",
        }
        vm_.update(properties)

        proxmox._reconfigure_clone(vm_, vmid)
        mock_query.assert_has_calls(query_calls, any_order=True)


def test_clone():
    """
    Test that an integer value for clone_from
    """
    mock_query = MagicMock(return_value="")
    with patch(
        "salt.cloud.clouds.proxmox._get_properties", MagicMock(return_value=[])
    ), patch("salt.cloud.clouds.proxmox.query", mock_query):
        vm_ = {
            "technology": "qemu",
            "name": "new2",
            "host": "myhost",
            "clone": True,
            "clone_from": 123,
        }

        # CASE 1: Numeric ID
        result = proxmox.create_node(vm_, ANY)
        mock_query.assert_called_once_with(
            "post",
            "nodes/myhost/qemu/123/clone",
            {"newid": ANY},
        )
        assert result == {"vmid": ANY}

        # CASE 2: host:ID notation
        mock_query.reset_mock()
        vm_["clone_from"] = "otherhost:123"
        result = proxmox.create_node(vm_, ANY)
        mock_query.assert_called_once_with(
            "post",
            "nodes/otherhost/qemu/123/clone",
            {"newid": ANY},
        )
        assert result == {"vmid": ANY}


def test_clone_pool():
    """
    Test that cloning a VM passes the pool parameter if present
    """
    mock_query = MagicMock(return_value="")
    with patch(
        "salt.cloud.clouds.proxmox._get_properties", MagicMock(return_value=[])
    ), patch("salt.cloud.clouds.proxmox.query", mock_query):
        vm_ = {
            "technology": "qemu",
            "name": "new2",
            "host": "myhost",
            "clone": True,
            "clone_from": 123,
            "pool": "mypool",
        }

        result = proxmox.create_node(vm_, ANY)
        mock_query.assert_called_once_with(
            "post",
            "nodes/myhost/qemu/123/clone",
            {"newid": ANY, "pool": "mypool"},
        )
        assert result == {"vmid": ANY}


def test_clone_id():
    """
    Test cloning a VM with a specified vmid.
    """
    next_vmid = 101
    explicit_vmid = 201
    upid = "UPID:myhost:00123456:12345678:9ABCDEF0:qmclone:123:root@pam:"

    def mock_query_response(conn_type, option, post_data=None):
        if conn_type == "get" and option == "cluster/tasks":
            return [{"upid": upid, "status": "OK"}]
        if conn_type == "post" and option.endswith("/clone"):
            return upid
        return None

    mock_wait_for_state = MagicMock(return_value=True)
    with patch(
        "salt.cloud.clouds.proxmox._get_properties",
        MagicMock(return_value=["vmid"]),
    ), patch(
        "salt.cloud.clouds.proxmox._get_next_vmid",
        MagicMock(return_value=next_vmid),
    ), patch(
        "salt.cloud.clouds.proxmox.start", MagicMock(return_value=True)
    ), patch(
        "salt.cloud.clouds.proxmox.wait_for_state", mock_wait_for_state
    ), patch(
        "salt.cloud.clouds.proxmox.query", side_effect=mock_query_response
    ):
        vm_ = {
            "profile": "my_proxmox",
            "driver": "proxmox",
            "technology": "qemu",
            "name": "new2",
            "host": "myhost",
            "clone": True,
            "clone_from": 123,
            "ip_address": "10.10.10.10",
        }

        # CASE 1: No vmid specified in profile (previous behavior)
        proxmox.create(vm_)
        mock_wait_for_state.assert_called_with(
            next_vmid,
            "running",
        )

        # CASE 2: vmid specified in profile
        vm_["vmid"] = explicit_vmid
        proxmox.create(vm_)
        mock_wait_for_state.assert_called_with(
            explicit_vmid,
            "running",
        )


def test_find_agent_ips():
    """
    Test find_agent_ip will return an IP
    """

    with patch(
        "salt.cloud.clouds.proxmox.query",
        return_value={
            "result": [
                {
                    "name": "eth0",
                    "ip-addresses": [
                        {"ip-address": "1.2.3.4", "ip-address-type": "ipv4"},
                        {"ip-address": "2001::1:2", "ip-address-type": "ipv6"},
                    ],
                },
                {
                    "name": "eth1",
                    "ip-addresses": [
                        {"ip-address": "2.3.4.5", "ip-address-type": "ipv4"},
                    ],
                },
                {
                    "name": "dummy",
                },
            ]
        },
    ) as mock_query:
        vm_ = {
            "technology": "qemu",
            "host": "myhost",
            "driver": "proxmox",
            "ignore_cidr": "1.0.0.0/8",
        }

        # CASE 1: Test ipv4 and ignore_cidr
        result = proxmox._find_agent_ip(vm_, ANY)
        mock_query.assert_any_call(
            "get", f"nodes/myhost/qemu/{ANY}/agent/network-get-interfaces"
        )

        assert result == "2.3.4.5"

        # CASE 2: Test ipv6

        vm_["protocol"] = "ipv6"
        result = proxmox._find_agent_ip(vm_, ANY)
        mock_query.assert_any_call(
            "get", f"nodes/myhost/qemu/{ANY}/agent/network-get-interfaces"
        )

        assert result == "2001::1:2"


def test__authenticate_with_custom_port():
    """
    Test the use of a custom port for Proxmox connection
    """
    get_cloud_config_mock = [
        "proxmox.connection.url",
        "9999",
        "fakeuser",
        "secretpassword",
        True,
    ]
    requests_post_mock = MagicMock()
    with patch(
        "salt.config.get_cloud_config_value",
        autospec=True,
        side_effect=get_cloud_config_mock,
    ), patch("requests.post", requests_post_mock):
        proxmox._authenticate()
        requests_post_mock.assert_called_with(
            "https://proxmox.connection.url:9999/api2/json/access/ticket",
            verify=True,
            data={"username": ("fakeuser",), "password": "secretpassword"},
            timeout=120,
        )


def _test__import_api(response):
    """
    Test _import_api recognition of varying Proxmox VE responses.
    """
    requests_get_mock = MagicMock()
    requests_get_mock.return_value.status_code = 200
    requests_get_mock.return_value.text = response
    with patch("requests.get", requests_get_mock):
        proxmox._import_api()
    assert proxmox.api == [{"info": {}}]
    return


def test__import_api_v6():
    """
    Test _import_api handling of a Proxmox VE 6 response.
    """
    response = textwrap.dedent(
        """\
        var pveapi = [
            {
                "info" : {
                }
            }
        ]
        ;
        """
    )
    _test__import_api(response)


def test__import_api_v7():
    """
    Test _import_api handling of a Proxmox VE 7 response.
    """
    response = textwrap.dedent(
        """\
        const apiSchema = [
            {
                "info" : {
                }
            }
        ]
        ;
        """
    )
    _test__import_api(response)


def test__authenticate_success():
    response = requests.Response()
    response.status_code = 200
    response.reason = "OK"
    response.raw = io.BytesIO(
        b"""{"data":{"CSRFPreventionToken":"01234567:dG9rZW4=","ticket":"PVE:cloud@pve:01234567::dGlja2V0"}}"""
    )
    with patch("requests.post", return_value=response):
        proxmox._authenticate()
    assert proxmox.csrf and proxmox.ticket
    return


def test__authenticate_failure():
    """
    Confirm that authentication failure raises an exception.
    """
    response = requests.Response()
    response.status_code = 401
    response.reason = "authentication failure"
    response.raw = io.BytesIO(b"""{"data":null}""")
    with patch("requests.post", return_value=response):
        pytest.raises(requests.exceptions.HTTPError, proxmox._authenticate)
    return


def test_creation_failure_logging(caplog):
    """
    Test detailed logging on HTTP errors during VM creation.
    """
    vm_ = {
        "profile": "my_proxmox",
        "name": "vm4",
        "technology": "lxc",
        "host": "127.0.0.1",
        "image": "local:some_image.tgz",
        "onboot": True,
    }
    assert (
        config.is_profile_configured(
            proxmox.__opts__, "my_proxmox:proxmox", "my_proxmox", vm_=vm_
        )
        is True
    )

    response = requests.Response()
    response.status_code = 400
    response.reason = "Parameter verification failed."
    response.raw = io.BytesIO(
        b"""{"data":null,"errors":{"onboot":"type check ('boolean') failed - got 'True'"}}"""
    )

    def mock_query_response(conn_type, option, post_data=None):
        if conn_type == "get" and option == "cluster/nextid":
            return 104
        if conn_type == "post" and option == "nodes/127.0.0.1/lxc":
            response.raise_for_status()
            return response
        return None

    with patch.object(proxmox, "query", side_effect=mock_query_response), patch.object(
        proxmox, "_get_properties", return_value=set()
    ):
        assert proxmox.create(vm_) is False

        # Search for these messages in a multi-line log entry.
        missing = {
            "{} Client Error: {} for url:".format(
                response.status_code, response.reason
            ),
            response.text,
        }
        for required in list(missing):
            for record in caplog.records:
                if required in record.message:
                    missing.remove(required)
                    break
        if missing:
            raise AssertionError(
                f"Did not find error messages: {sorted(list(missing))}"
            )
    return
