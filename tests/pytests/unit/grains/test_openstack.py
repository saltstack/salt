"""
Test module for Openstack metadata grains module

:maintainer: Zane Mingee <zmingee@gmail.com>
"""
import json
import socket

import pytest
import salt.grains.openstack
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {
        salt.grains.openstack: {
            "__opts__": {
                "openstack_metadata_grains": True,
                "openstack_metadata_version": "latest",
            }
        }
    }


@pytest.fixture(scope="function")
def _socket():
    sock = MagicMock()
    sock.settimeout = MagicMock(return_value=True)
    sock.connect = MagicMock(side_effect=BlockingIOError)

    _socket = MagicMock()
    _socket.socket = MagicMock(return_value=sock)

    return _socket


@pytest.fixture(scope="function")
def _http(return_value=None):
    http = MagicMock()
    http.query = MagicMock(return_value=return_value)

    return http


class TestOpenStackMetadataGrains:
    """
    TestCase for OpenStack metadata grains module
    """

    def test_module_loader(self, _socket, _http):
        _http.query.return_value = {"status": 200}

        with patch("salt.grains.openstack.socket", _socket), patch(
            "salt.utils.http", _http
        ):
            rv = salt.grains.openstack.__virtual__()

            assert rv is True
            assert _socket.socket.called
            assert _socket.socket.return_value.settimeout.called
            assert _socket.socket.return_value.settimeout.call_args[0][0] == 0
            assert _socket.socket.return_value.connect.called
            assert (
                _socket.socket.return_value.connect.call_args[0][0][0]
                == salt.grains.openstack.METADATA_IP
            )
            assert _socket.socket.return_value.connect.call_args[0][0][1] == 80
            assert _http.query.called

    def test_module_loader_socket_unavailable(self, _socket, _http):
        _socket.socket.return_value.connect = MagicMock(side_effect=socket.timeout)

        with patch("salt.grains.openstack.socket", _socket), patch(
            "salt.utils.http", _http
        ):
            rv = salt.grains.openstack.__virtual__()

            assert rv is False
            assert _socket.socket.called
            assert _socket.socket.return_value.settimeout.called
            assert _socket.socket.return_value.settimeout.call_args[0][0] == 0
            assert _socket.socket.return_value.connect.called
            assert (
                _socket.socket.return_value.connect.call_args[0][0][0]
                == salt.grains.openstack.METADATA_IP
            )
            assert _socket.socket.return_value.connect.call_args[0][0][1] == 80
            assert not _http.query.called

    def test_module_loader_service_unavailable(self, _socket, _http):
        _http.query.return_value = {"status": 500}

        with patch("salt.grains.openstack.socket", _socket), patch(
            "salt.utils.http", _http
        ):
            rv = salt.grains.openstack.__virtual__()

            assert rv is False
            assert _socket.socket.called
            assert _socket.socket.return_value.settimeout.called
            assert _socket.socket.return_value.settimeout.call_args[0][0] == 0
            assert _socket.socket.return_value.connect.called
            assert (
                _socket.socket.return_value.connect.call_args[0][0][0]
                == salt.grains.openstack.METADATA_IP
            )
            assert _socket.socket.return_value.connect.call_args[0][0][1] == 80
            assert _http.query.called

    def test_grain(self, _http):
        body = json.dumps(
            {
                "coerce_true": "true",
                "coerce_false": "false",
                "coerce_none": "none",
                "coerce_null": "null",
            }
        )
        _http.query.return_value = {"body": body}

        with patch("salt.utils.http", _http):
            rv = salt.grains.openstack.get_metadata()

            assert rv
            assert "openstack" in rv
            assert "nova" in rv["openstack"]
            assert rv["openstack"]["nova"]["coerce_true"] is True
            assert rv["openstack"]["nova"]["coerce_false"] is False
            assert rv["openstack"]["nova"]["coerce_none"] is None
            assert rv["openstack"]["nova"]["coerce_null"] is None
            assert "neutron" in rv["openstack"]
            assert rv["openstack"]["neutron"]["coerce_true"] is True
            assert rv["openstack"]["neutron"]["coerce_false"] is False
            assert rv["openstack"]["neutron"]["coerce_none"] is None
            assert rv["openstack"]["neutron"]["coerce_null"] is None

    def test_grain_error(self, _http):
        _http.query.return_value = {"error": "HTTP 404: Not found"}

        with patch("salt.utils.http", _http):
            rv = salt.grains.openstack.get_metadata()
            assert rv is None

    def test_grain_invalid_data(self, _http):
        _http.query.return_value = {"body": "invalid data"}

        with patch("salt.utils.http", _http):
            rv = salt.grains.openstack.get_metadata()
            assert rv is None
