"""
Unit tests for salt.transport.base.
"""

import ssl

import pytest

import salt.transport.base
from tests.support.mock import MagicMock, patch

pytestmark = [
    pytest.mark.core_test,
]


# ---------------------------------------------------------------------------
# _ipc_loopback
# ---------------------------------------------------------------------------


def test_ipc_loopback_ipv4():
    assert salt.transport.base._ipc_loopback({}) == "127.0.0.1"
    assert salt.transport.base._ipc_loopback({"ipv6": False}) == "127.0.0.1"


def test_ipc_loopback_ipv6():
    assert salt.transport.base._ipc_loopback({"ipv6": True}) == "::1"


# ---------------------------------------------------------------------------
# ipc_publish_client
# ---------------------------------------------------------------------------

_IPC_TCP_OPTS = {
    "ipc_mode": "tcp",
    "ipv6": False,
    "tcp_pub_port": 4510,
    "tcp_pull_port": 4511,
    "tcp_master_pub_port": 4512,
    "tcp_master_pull_port": 4513,
    "hash_type": "sha256",
    "id": "test-minion",
    "sock_dir": "/var/run/salt",
}


def test_ipc_publish_client_minion_ipv4():
    """ipc_publish_client uses 127.0.0.1 for minion when ipv6 is False."""
    opts = {**_IPC_TCP_OPTS, "ipv6": False}
    mock_client = MagicMock()
    with patch("salt.transport.base.publish_client", return_value=mock_client) as mock:
        salt.transport.base.ipc_publish_client("minion", opts, io_loop=None)
    _, kwargs = mock.call_args
    assert kwargs["host"] == "127.0.0.1"


def test_ipc_publish_client_minion_ipv6():
    """ipc_publish_client uses ::1 for minion when ipv6 is True."""
    opts = {**_IPC_TCP_OPTS, "ipv6": True}
    mock_client = MagicMock()
    with patch("salt.transport.base.publish_client", return_value=mock_client) as mock:
        salt.transport.base.ipc_publish_client("minion", opts, io_loop=None)
    _, kwargs = mock.call_args
    assert kwargs["host"] == "::1"


def test_ipc_publish_client_master_ipv4():
    """ipc_publish_client uses 127.0.0.1 for master when ipv6 is False."""
    opts = {**_IPC_TCP_OPTS, "ipv6": False}
    mock_client = MagicMock()
    with patch("salt.transport.base.publish_client", return_value=mock_client) as mock:
        salt.transport.base.ipc_publish_client("master", opts, io_loop=None)
    _, kwargs = mock.call_args
    assert kwargs["host"] == "127.0.0.1"


def test_ipc_publish_client_master_ipv6():
    """ipc_publish_client uses ::1 for master when ipv6 is True."""
    opts = {**_IPC_TCP_OPTS, "ipv6": True}
    mock_client = MagicMock()
    with patch("salt.transport.base.publish_client", return_value=mock_client) as mock:
        salt.transport.base.ipc_publish_client("master", opts, io_loop=None)
    _, kwargs = mock.call_args
    assert kwargs["host"] == "::1"


# ---------------------------------------------------------------------------
# ipc_publish_server
# ---------------------------------------------------------------------------


def test_ipc_publish_server_minion_ipv4():
    """ipc_publish_server uses 127.0.0.1 for minion when ipv6 is False."""
    opts = {**_IPC_TCP_OPTS, "ipv6": False}
    mock_server = MagicMock()
    with patch("salt.transport.base.publish_server", return_value=mock_server) as mock:
        salt.transport.base.ipc_publish_server("minion", opts)
    _, kwargs = mock.call_args
    assert kwargs["pub_host"] == "127.0.0.1"
    assert kwargs["pull_host"] == "127.0.0.1"


def test_ipc_publish_server_minion_ipv6():
    """ipc_publish_server uses ::1 for minion when ipv6 is True."""
    opts = {**_IPC_TCP_OPTS, "ipv6": True}
    mock_server = MagicMock()
    with patch("salt.transport.base.publish_server", return_value=mock_server) as mock:
        salt.transport.base.ipc_publish_server("minion", opts)
    _, kwargs = mock.call_args
    assert kwargs["pub_host"] == "::1"
    assert kwargs["pull_host"] == "::1"


def test_ipc_publish_server_master_ipv4():
    """ipc_publish_server uses 127.0.0.1 for master when ipv6 is False."""
    opts = {**_IPC_TCP_OPTS, "ipv6": False}
    mock_server = MagicMock()
    with patch("salt.transport.base.publish_server", return_value=mock_server) as mock:
        salt.transport.base.ipc_publish_server("master", opts)
    _, kwargs = mock.call_args
    assert kwargs["pub_host"] == "127.0.0.1"
    assert kwargs["pull_host"] == "127.0.0.1"


def test_ipc_publish_server_master_ipv6():
    """ipc_publish_server uses ::1 for master when ipv6 is True."""
    opts = {**_IPC_TCP_OPTS, "ipv6": True}
    mock_server = MagicMock()
    with patch("salt.transport.base.publish_server", return_value=mock_server) as mock:
        salt.transport.base.ipc_publish_server("master", opts)
    _, kwargs = mock.call_args
    assert kwargs["pub_host"] == "::1"
    assert kwargs["pull_host"] == "::1"


def test_unclosed_warning():

    transport = salt.transport.base.Transport()
    assert transport._closing is False
    assert transport._connect_called is False
    transport.connect()
    assert transport._connect_called is True
    with pytest.warns(salt.transport.base.TransportWarning):
        del transport


@patch("ssl.SSLContext")
def test_ssl_context_legacy_opts(mock):
    ctx = salt.transport.base.ssl_context(
        {
            "certfile": "server.crt",
            "keyfile": "server.key",
            "cert_reqs": "CERT_NONE",
            "ca_certs": "ca.crt",
        }
    )
    ctx.load_cert_chain.assert_called_with(
        "server.crt",
        "server.key",
    )
    ctx.load_verify_locations.assert_called_with("ca.crt")
    assert ssl.VerifyMode.CERT_NONE == ctx.verify_mode
    assert not ctx.check_hostname


@patch("ssl.SSLContext")
def test_ssl_context_opts(mock):
    mock.verify_flags = ssl.VerifyFlags.VERIFY_X509_TRUSTED_FIRST
    ctx = salt.transport.base.ssl_context(
        {
            "certfile": "server.crt",
            "keyfile": "server.key",
            "cert_reqs": "CERT_OPTIONAL",
            "verify_locations": [
                "ca.crt",
                {"cafile": "crl.pem"},
                {"capath": "/tmp/mycapathsdf"},
                {"cadata": "mycadataother"},
                {"CADATA": "mycadatasdf"},
            ],
            "verify_flags": [
                "VERIFY_CRL_CHECK_CHAIN",
            ],
        }
    )
    ctx.load_cert_chain.assert_called_with(
        "server.crt",
        "server.key",
    )
    ctx.load_verify_locations.assert_any_call(cafile="ca.crt")
    ctx.load_verify_locations.assert_any_call(cafile="crl.pem")
    ctx.load_verify_locations.assert_any_call(capath="/tmp/mycapathsdf")
    ctx.load_verify_locations.assert_any_call(cadata="mycadataother")
    ctx.load_verify_locations.assert_called_with(cadata="mycadatasdf")
    assert ssl.VerifyMode.CERT_OPTIONAL == ctx.verify_mode
    assert ctx.check_hostname
    assert ssl.VerifyFlags.VERIFY_CRL_CHECK_CHAIN & ctx.verify_flags


def test_ssl_context_server_side_none_raises_error():
    """Test that server_side=None raises ValueError."""
    with pytest.raises(ValueError, match="server_side must be True or False"):
        salt.transport.base.ssl_context({}, server_side=None)
