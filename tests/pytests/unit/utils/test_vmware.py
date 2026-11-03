"""
Tests for connection handling in salt.utils.vmware.get_service_instance
"""

import ssl

import pytest

import salt.utils.vmware
from tests.support.mock import MagicMock, patch

try:
    from pyVmomi import vim  # pylint: disable=no-name-in-module

    HAS_PYVMOMI = True
except ImportError:
    HAS_PYVMOMI = False

pytestmark = [
    pytest.mark.skipif(not HAS_PYVMOMI, reason="The 'pyvmomi' library is missing"),
]


@pytest.fixture
def connection_params():
    return {
        "host": "fake_host",
        "username": "fake_username",
        "password": "fake_password",
        "protocol": "fake_protocol",
        "port": 1,
        "mechanism": "fake_mechanism",
        "principal": "fake_principal",
        "domain": "fake_domain",
    }


@pytest.mark.parametrize(
    "exc",
    [
        pytest.param(vim.fault.NotAuthenticated, id="NotAuthenticated"),
        pytest.param(
            ssl.SSLError("decryption failed or bad record mac"), id="SSLError"
        ),
        pytest.param(BrokenPipeError(), id="BrokenPipeError"),
        pytest.param(ConnectionResetError(), id="ConnectionResetError"),
    ],
)
def test_stale_service_instance_reconnects(exc, connection_params):
    """
    The CurrentTime() probe in get_service_instance detects a dead cached
    connection. An expired session raises vim.fault.NotAuthenticated, while a
    connection corrupted at the socket level - for example when salt-cloud's
    map_providers_parallel inherits the cached service instance across a fork
    and the shared TLS socket is used from more than one process (issue #61983)
    - raises ssl.SSLError, BrokenPipeError or ConnectionResetError. In every
    case the connection should be transparently re-established instead of the
    error propagating to the caller.
    """
    mock_si = MagicMock()
    mock_si.CurrentTime = MagicMock(side_effect=exc)
    mock_get_si = MagicMock(return_value=mock_si)
    mock_disconnect = MagicMock()
    with patch("salt.utils.vmware.GetSi", MagicMock(return_value=None)), patch(
        "salt.utils.vmware._get_service_instance", mock_get_si
    ), patch("salt.utils.vmware.Disconnect", mock_disconnect):
        # Must not raise
        salt.utils.vmware.get_service_instance(**connection_params)
    # The probe ran once and found the connection dead
    assert mock_si.CurrentTime.call_count == 1
    # The dead connection was torn down ...
    assert mock_disconnect.call_count == 1
    # ... and a fresh one established (initial connect + reconnect)
    assert mock_get_si.call_count == 2


def test_reconnect_when_disconnecting_dead_socket_raises(connection_params):
    """
    Disconnect logs out over the same socket, so on an already broken
    connection it can raise too. That failure must not escape
    get_service_instance - we drop the connection and reconnect regardless.
    """
    mock_si = MagicMock()
    mock_si.CurrentTime = MagicMock(side_effect=ssl.SSLError("bad record mac"))
    mock_get_si = MagicMock(return_value=mock_si)
    mock_disconnect = MagicMock(side_effect=BrokenPipeError())
    with patch("salt.utils.vmware.GetSi", MagicMock(return_value=None)), patch(
        "salt.utils.vmware._get_service_instance", mock_get_si
    ), patch("salt.utils.vmware.Disconnect", mock_disconnect):
        # Must not raise even though Disconnect itself blew up
        salt.utils.vmware.get_service_instance(**connection_params)
    assert mock_disconnect.call_count == 1
    assert mock_get_si.call_count == 2


def test_userpass_does_not_pass_deprecated_b64token_mechanism():
    """
    pyvmomi 9 raises Exception('b64token and mechanism are no longer
    supported') as soon as either keyword argument is truthy. For the
    userpass mechanism Salt has no token at all, so SmartConnect must be
    called without the deprecated b64token/mechanism keywords (issue
    #68211).
    """
    mock_sc = MagicMock()
    with patch("salt.utils.vmware.SmartConnect", mock_sc), patch(
        "salt.utils.vmware.Disconnect", MagicMock()
    ):
        salt.utils.vmware._get_service_instance(
            host="fake_host.fqdn",
            username="fake_username",
            password="fake_password",
            protocol="fake_protocol",
            port=1,
            mechanism="userpass",
            principal=None,
            domain=None,
        )
    assert mock_sc.call_count == 1
    kwargs = mock_sc.call_args.kwargs
    assert "b64token" not in kwargs
    assert "mechanism" not in kwargs


def test_sspi_uses_token_and_tokenType_not_b64token_mechanism():
    """
    pyvmomi 9 replaced the deprecated b64token/mechanism keywords with
    token/tokenType. For the sspi mechanism Salt now forwards the gssapi
    token through the new keyword arguments so SmartConnect does not raise
    (issue #68211).
    """
    mock_sc = MagicMock()
    mock_token = MagicMock(return_value="fake_token")
    with patch("salt.utils.vmware.SmartConnect", mock_sc), patch(
        "salt.utils.vmware.get_gssapi_token", mock_token
    ), patch("salt.utils.vmware.Disconnect", MagicMock()):
        salt.utils.vmware._get_service_instance(
            host="fake_host.fqdn",
            username="fake_username",
            password="fake_password",
            protocol="fake_protocol",
            port=1,
            mechanism="sspi",
            principal="fake_principal",
            domain="fake_domain",
        )
    assert mock_sc.call_count == 1
    kwargs = mock_sc.call_args.kwargs
    assert "b64token" not in kwargs
    assert "mechanism" not in kwargs
    assert kwargs.get("token") == "fake_token"
    assert kwargs.get("tokenType") == "sspi"


def test_userpass_verify_ssl_false_does_not_pass_b64token_mechanism():
    """
    The verify_ssl=False code path also must not forward the deprecated
    b64token/mechanism keywords to pyvmomi 9 SmartConnect (issue #68211).
    """
    mock_sc = MagicMock()
    with patch("salt.utils.vmware.SmartConnect", mock_sc), patch(
        "salt.utils.vmware.Disconnect", MagicMock()
    ), patch("ssl._create_unverified_context", MagicMock()):
        salt.utils.vmware._get_service_instance(
            host="fake_host.fqdn",
            username="fake_username",
            password="fake_password",
            protocol="fake_protocol",
            port=1,
            mechanism="userpass",
            principal=None,
            domain=None,
            verify_ssl=False,
        )
    assert mock_sc.call_count == 1
    kwargs = mock_sc.call_args.kwargs
    assert "b64token" not in kwargs
    assert "mechanism" not in kwargs
