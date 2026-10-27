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
    # ``ca_certs`` seeds ``ssl.create_default_context`` so the custom CA is the
    # only trust anchor; create_default_context forwards it positionally.
    ctx.load_verify_locations.assert_called_with("ca.crt", None, None)
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
    # First location seeds create_default_context (positional), the rest are
    # loaded explicitly.
    ctx.load_verify_locations.assert_any_call("ca.crt", None, None)
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


# ---------------------------------------------------------------------------
# ssl_context: custom PKI behaviour
# ---------------------------------------------------------------------------


def _make_ca(tmp_path, name):
    """Write a throwaway self-signed CA and return its PEM path."""
    import datetime

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID

    key = ec.generate_private_key(ec.SECP256R1())
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, name)])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=1))
        .not_valid_after(now + datetime.timedelta(days=1))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), True)
        .sign(key, hashes.SHA256())
    )
    path = tmp_path / f"{name}.crt"
    path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    return str(path)


def _ca_names(ctx):
    return sorted(
        dict(rdn[0] for rdn in cert["subject"])["commonName"]
        for cert in ctx.get_ca_certs()
    )


@pytest.mark.parametrize("server_side", [True, False], ids=["server", "client"])
def test_ssl_context_ca_certs_is_exclusive_trust_anchor(tmp_path, server_side):
    """
    A custom PKI configured through ``ca_certs`` must be the *only* trust
    anchor.  Before this fix the client side also loaded the whole system /
    certifi bundle, so any publicly trusted CA could have issued a "master"
    certificate.
    """
    pytest.importorskip("cryptography")
    ca = _make_ca(tmp_path, "Example Corp Root CA")
    ctx = salt.transport.base.ssl_context(
        {"ca_certs": ca, "cert_reqs": "CERT_REQUIRED"}, server_side=server_side
    )
    assert _ca_names(ctx) == ["Example Corp Root CA"]
    assert ctx.verify_mode == ssl.CERT_REQUIRED
    assert ctx.check_hostname is (not server_side)


def test_ssl_context_verify_locations_are_exclusive_and_all_loaded(tmp_path):
    """
    Every ``verify_locations`` entry (string or dict form) is loaded and no
    default trust store is mixed in.  Covers the root + intermediate bundle
    layout enterprise PKIs ship.
    """
    pytest.importorskip("cryptography")
    root = _make_ca(tmp_path, "Example Corp Root CA")
    issuing = _make_ca(tmp_path, "Example Corp Issuing CA")
    ctx = salt.transport.base.ssl_context(
        {
            "cert_reqs": "CERT_REQUIRED",
            "verify_locations": [root, {"cafile": issuing}],
        },
        server_side=False,
    )
    assert _ca_names(ctx) == ["Example Corp Issuing CA", "Example Corp Root CA"]


def test_ssl_context_ca_certs_plus_verify_locations(tmp_path):
    """Legacy ``ca_certs`` and ``verify_locations`` combine, still exclusive."""
    pytest.importorskip("cryptography")
    root = _make_ca(tmp_path, "Example Corp Root CA")
    issuing = _make_ca(tmp_path, "Example Corp Issuing CA")
    ctx = salt.transport.base.ssl_context(
        {"ca_certs": root, "verify_locations": [issuing]}, server_side=True
    )
    assert _ca_names(ctx) == ["Example Corp Issuing CA", "Example Corp Root CA"]


def test_ssl_context_without_explicit_ca_keeps_default_trust():
    """No ``ca_certs``/``verify_locations``: Python's default store is used."""
    with patch("ssl.create_default_context") as create_default_context:
        salt.transport.base.ssl_context(
            {"cert_reqs": "CERT_REQUIRED"}, server_side=False
        )
    create_default_context.assert_called_once_with(ssl.Purpose.SERVER_AUTH)


def test_ssl_context_ssl_version_loads_every_trust_location(tmp_path):
    """
    With an explicit ``ssl_version`` a fresh SSLContext is built, so all
    configured trust locations must be loaded onto it (none is lost to the
    discarded default context).
    """
    pytest.importorskip("cryptography")
    root = _make_ca(tmp_path, "Example Corp Root CA")
    issuing = _make_ca(tmp_path, "Example Corp Issuing CA")
    ctx = salt.transport.base.ssl_context(
        {
            "ssl_version": ssl.PROTOCOL_TLS_SERVER,
            "ca_certs": root,
            "verify_locations": [issuing],
            "cert_reqs": "CERT_REQUIRED",
        },
        server_side=False,
    )
    assert _ca_names(ctx) == ["Example Corp Issuing CA", "Example Corp Root CA"]


@patch("ssl.SSLContext")
def test_ssl_context_client_certfile_overrides_on_client_side(mock):
    """
    ``client_certfile``/``client_keyfile`` let the master present a dedicated
    clientAuth certificate when master-local tooling (salt, salt-run, salt-api)
    connects to the master's own request server.
    """
    opts = {
        "certfile": "master-server.crt",
        "keyfile": "master-server.key",
        "client_certfile": "master-client.crt",
        "client_keyfile": "master-client.key",
        "cert_reqs": "CERT_REQUIRED",
    }
    ctx = salt.transport.base.ssl_context(opts, server_side=False)
    ctx.load_cert_chain.assert_called_once_with(
        "master-client.crt", "master-client.key"
    )


@patch("ssl.SSLContext")
def test_ssl_context_client_certfile_ignored_on_server_side(mock):
    opts = {
        "certfile": "master-server.crt",
        "keyfile": "master-server.key",
        "client_certfile": "master-client.crt",
        "client_keyfile": "master-client.key",
        "cert_reqs": "CERT_REQUIRED",
    }
    ctx = salt.transport.base.ssl_context(opts, server_side=True)
    ctx.load_cert_chain.assert_called_once_with(
        "master-server.crt", "master-server.key"
    )


@patch("ssl.SSLContext")
def test_ssl_context_client_certfile_without_keyfile(mock):
    """A combined PEM (key + cert) client file needs no ``client_keyfile``."""
    opts = {
        "certfile": "master-server.crt",
        "keyfile": "master-server.key",
        "client_certfile": "master-client.pem",
    }
    ctx = salt.transport.base.ssl_context(opts, server_side=False)
    ctx.load_cert_chain.assert_called_once_with("master-client.pem", None)


# ---------------------------------------------------------------------------
# tls_server_hostname
# ---------------------------------------------------------------------------


def test_tls_server_hostname_explicit_override_wins():
    ssl_opts = {"server_hostname": "salt-master.corp.example"}
    opts = {"master": "10.0.0.5", "master_ip": "10.0.0.5"}
    assert (
        salt.transport.base.tls_server_hostname(ssl_opts, opts, "10.0.0.5")
        == "salt-master.corp.example"
    )


def test_tls_server_hostname_uses_configured_master_name():
    """
    The minion resolves ``master`` to ``master_ip`` and connects to the IP.
    The certificate must still be checked against the configured name.
    """
    opts = {"master": "salt-master.corp.example", "master_ip": "10.0.0.5"}
    assert (
        salt.transport.base.tls_server_hostname({}, opts, "10.0.0.5")
        == "salt-master.corp.example"
    )


def test_tls_server_hostname_strips_port_from_master():
    opts = {"master": "salt-master.corp.example:4506", "master_ip": "10.0.0.5"}
    assert (
        salt.transport.base.tls_server_hostname({}, opts, "10.0.0.5")
        == "salt-master.corp.example"
    )


def test_tls_server_hostname_ipv6_master_ip():
    opts = {"master": "salt-master.corp.example", "master_ip": "[fd00::5]"}
    assert (
        salt.transport.base.tls_server_hostname({}, opts, "fd00::5")
        == "salt-master.corp.example"
    )


def test_tls_server_hostname_ipv6_equivalent_textual_forms():
    # The resolver may hand back a different spelling of the same address.
    opts = {"master": "salt-master.corp.example", "master_ip": "::1"}
    assert (
        salt.transport.base.tls_server_hostname({}, opts, "0:0:0:0:0:0:0:1")
        == "salt-master.corp.example"
    )


def test_tls_server_hostname_master_is_ip_literal():
    """An IP literal master keeps IP based verification (needs an IP SAN)."""
    opts = {"master": "10.0.0.5", "master_ip": "10.0.0.5"}
    assert salt.transport.base.tls_server_hostname({}, opts, "10.0.0.5") == "10.0.0.5"


def test_tls_server_hostname_host_is_not_the_master():
    """
    Connecting somewhere other than ``master_ip`` (e.g. the master-local
    ``salt`` CLI talking to ``interface``) must not borrow the master name.
    """
    opts = {"master": "salt-master.corp.example", "master_ip": "10.0.0.5"}
    assert salt.transport.base.tls_server_hostname({}, opts, "127.0.0.1") == "127.0.0.1"


def test_tls_server_hostname_no_master_in_opts():
    assert (
        salt.transport.base.tls_server_hostname(
            {}, {"interface": "0.0.0.0"}, "127.0.0.1"
        )
        == "127.0.0.1"
    )
    assert salt.transport.base.tls_server_hostname(None, {}, "127.0.0.1") == "127.0.0.1"


def test_tls_server_hostname_master_list_is_ignored():
    """Multi-master opts before per-master selection carry a list."""
    opts = {"master": ["a.corp.example", "b.corp.example"], "master_ip": "10.0.0.5"}
    assert salt.transport.base.tls_server_hostname({}, opts, "10.0.0.5") == "10.0.0.5"
