import os

import pytest
import salt.modules.tls as tls
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {tls: {}}


@pytest.fixture(scope="module")
def tls_test_data():
    return {
        "create_ca": {
            "bits": 2048,
            "CN": "localhost",
            "C": "US",
            "ST": "Utah",
            "L": "Salt Lake City",
            "O": "SaltStack",
            "OU": "Test Unit",
            "emailAddress": "xyz@pdq.net",
            "digest": "sha256",
            "replace": False,
        }
    }


@pytest.mark.skip_on_windows(reason="Skipping on Windows per Shane's suggestion")
def test_create_ca_permissions_on_cert_and_key(tmpdir, tls_test_data):
    ca_name = "test_ca"
    certp = tmpdir.join(ca_name).join("{}_ca_cert.crt".format(ca_name)).strpath
    certk = tmpdir.join(ca_name).join("{}_ca_cert.key".format(ca_name)).strpath
    mock_opt = MagicMock(return_value=tmpdir)
    mock_ret = MagicMock(return_value=0)

    with patch.dict(
        tls.__salt__, {"config.option": mock_opt, "cmd.retcode": mock_ret}
    ), patch.dict(tls.__opts__, {"hash_type": "sha256", "cachedir": str(tmpdir)}):
        tls.create_ca(ca_name, days=365, fixmode=False, **tls_test_data["create_ca"])
        certp_mode = os.stat(certp).st_mode & 0o7777
        certk_mode = os.stat(certk).st_mode & 0o7777

        assert 0o644 == certp_mode
        assert 0o600 == certk_mode


@pytest.mark.skip_on_windows(reason="Skipping on Windows per Shane's suggestion")
def test_create_csr_permissions_on_csr_and_key(tmpdir, tls_test_data):
    ca_name = "test_ca"
    csrp = (
        tmpdir.join(ca_name)
        .join("certs")
        .join("{}.csr".format(tls_test_data["create_ca"]["CN"]))
        .strpath
    )
    keyp = (
        tmpdir.join(ca_name)
        .join("certs")
        .join("{}.key".format(tls_test_data["create_ca"]["CN"]))
        .strpath
    )

    mock_opt = MagicMock(return_value=tmpdir)
    mock_ret = MagicMock(return_value=0)
    mock_pgt = MagicMock(return_value=False)

    with patch.dict(
        tls.__salt__,
        {"config.option": mock_opt, "cmd.retcode": mock_ret, "pillar.get": mock_pgt},
    ), patch.dict(tls.__opts__, {"hash_type": "sha256", "cachedir": str(tmpdir)}):
        tls.create_ca(ca_name, days=365, **tls_test_data["create_ca"])
        tls.create_csr(ca_name, **tls_test_data["create_ca"])

        csrp_mode = os.stat(csrp).st_mode & 0o7777
        keyp_mode = os.stat(keyp).st_mode & 0o7777

        assert 0o644 == csrp_mode
        assert 0o600 == keyp_mode


@pytest.mark.skip_on_windows(reason="Skipping on Windows per Shane's suggestion")
def test_create_self_signed_cert_permissions_on_csr_cert_and_key(tmpdir, tls_test_data):
    ca_name = "test_ca"
    certp = (
        tmpdir.join(ca_name)
        .join("certs")
        .join("{}.crt".format(tls_test_data["create_ca"]["CN"]))
        .strpath
    )
    keyp = (
        tmpdir.join(ca_name)
        .join("certs")
        .join("{}.key".format(tls_test_data["create_ca"]["CN"]))
        .strpath
    )

    mock_opt = MagicMock(return_value=tmpdir)
    mock_ret = MagicMock(return_value=0)
    mock_pgt = MagicMock(return_value=False)

    with patch.dict(
        tls.__salt__,
        {"config.option": mock_opt, "cmd.retcode": mock_ret, "pillar.get": mock_pgt},
    ), patch.dict(tls.__opts__, {"hash_type": "sha256", "cachedir": str(tmpdir)}):
        tls.create_self_signed_cert(ca_name, days=365, **tls_test_data["create_ca"])

        certp_mode = os.stat(certp).st_mode & 0o7777
        keyp_mode = os.stat(keyp).st_mode & 0o7777

        assert 0o644 == certp_mode
        assert 0o600 == keyp_mode
