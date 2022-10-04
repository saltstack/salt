import logging

import pytest

import salt.modules.tls as tls
from tests.support.helpers import SKIP_INITIAL_PHOTONOS_FAILURES
from tests.support.mock import MagicMock, patch

log = logging.getLogger(__name__)


pytestmark = [
    SKIP_INITIAL_PHOTONOS_FAILURES,
]


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
def test_create_ca_permissions_on_cert_and_key(tmp_path, tls_test_data):
    ca_name = "test_ca"
    certp = tmp_path / ca_name / "{}_ca_cert.crt".format(ca_name)
    certk = tmp_path / ca_name / "{}_ca_cert.key".format(ca_name)
    mock_opt = MagicMock(return_value=str(tmp_path))
    mock_ret = MagicMock(return_value=0)

    with patch.dict(
        tls.__salt__, {"config.option": mock_opt, "cmd.retcode": mock_ret}
    ), patch.dict(tls.__opts__, {"hash_type": "sha256", "cachedir": str(tmp_path)}):
        tls.create_ca(ca_name, days=365, fixmode=False, **tls_test_data["create_ca"])
        assert certp.stat().st_mode & 0o7777 == 0o644
        assert certk.stat().st_mode & 0o7777 == 0o600


@pytest.mark.skip_on_windows(reason="Skipping on Windows per Shane's suggestion")
def test_create_csr_permissions_on_csr_and_key(tmp_path, tls_test_data):
    ca_name = "test_ca"
    csrp = (
        tmp_path / ca_name / "certs" / "{}.csr".format(tls_test_data["create_ca"]["CN"])
    )
    keyp = (
        tmp_path / ca_name / "certs" / "{}.key".format(tls_test_data["create_ca"]["CN"])
    )

    mock_opt = MagicMock(return_value=str(tmp_path))
    mock_ret = MagicMock(return_value=0)
    mock_pgt = MagicMock(return_value=False)

    with patch.dict(
        tls.__salt__,
        {"config.option": mock_opt, "cmd.retcode": mock_ret, "pillar.get": mock_pgt},
    ), patch.dict(tls.__opts__, {"hash_type": "sha256", "cachedir": str(tmp_path)}):
        ca_ret = tls.create_ca(ca_name, days=365, **tls_test_data["create_ca"])
        assert ca_ret
        csr_ret = tls.create_csr(ca_name, **tls_test_data["create_ca"])
        assert csr_ret

        assert csrp.exists()
        assert keyp.exists()

        assert csrp.stat().st_mode & 0o7777 == 0o644
        assert keyp.stat().st_mode & 0o7777 == 0o600


@pytest.mark.skip_on_windows(reason="Skipping on Windows per Shane's suggestion")
def test_create_self_signed_cert_permissions_on_csr_cert_and_key(
    tmp_path, tls_test_data
):
    ca_name = "test_ca"
    certp = (
        tmp_path / ca_name / "certs" / "{}.crt".format(tls_test_data["create_ca"]["CN"])
    )
    keyp = (
        tmp_path / ca_name / "certs" / "{}.key".format(tls_test_data["create_ca"]["CN"])
    )

    mock_opt = MagicMock(return_value=str(tmp_path))
    mock_ret = MagicMock(return_value=0)
    mock_pgt = MagicMock(return_value=False)

    with patch.dict(
        tls.__salt__,
        {"config.option": mock_opt, "cmd.retcode": mock_ret, "pillar.get": mock_pgt},
    ), patch.dict(tls.__opts__, {"hash_type": "sha256", "cachedir": str(tmp_path)}):
        tls.create_self_signed_cert(ca_name, days=365, **tls_test_data["create_ca"])

        assert certp.stat().st_mode & 0o7777 == 0o644
        assert keyp.stat().st_mode & 0o7777 == 0o600
