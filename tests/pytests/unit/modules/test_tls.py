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
        },
        "ca_signed_cert": "",
        "ca_signed_key": "",
        "ca_cert": """-----BEGIN CERTIFICATE-----
MIIEejCCA2KgAwIBAgIRANW6IUG5rMez0vPi3cSmS3QwDQYJKoZIhvcNAQELBQAw
eTELMAkGA1UEBhMCVVMxDTALBgNVBAgMBFV0YWgxFzAVBgNVBAcMDlNhbHQgTGFr
ZSBDaXR5MRIwEAYDVQQKDAlTYWx0U3RhY2sxEjAQBgNVBAMMCWxvY2FsaG9zdDEa
MBgGCSqGSIb3DQEJARYLeHl6QHBkcS5uZXQwHhcNMTUwNTA1MTYzOTIxWhcNMTYw
NTA0MTYzOTIxWjB5MQswCQYDVQQGEwJVUzENMAsGA1UECAwEVXRhaDEXMBUGA1UE
BwwOU2FsdCBMYWtlIENpdHkxEjAQBgNVBAoMCVNhbHRTdGFjazESMBAGA1UEAwwJ
bG9jYWxob3N0MRowGAYJKoZIhvcNAQkBFgt4eXpAcGRxLm5ldDCCASIwDQYJKoZI
hvcNAQEBBQADggEPADCCAQoCggEBAMNvHc8LwpI5/NiwRTWYG34WQ5vau8gkj+8p
5KehXDNmDcCY8QW9xNaCxY6Atg2Dwh5vEacubKRcnQL9SFKYHa4ddtnkISzSkdZN
ImY7ZVQteDIVNJmy7DrZ4RvWTr2ezXYLv8oNkqrKhynt5xIBXZWslWUav1pOp8z8
N+LeXaASVyajqB5TiN8HJR/up9MlSfy/zhtm6x6SIUsEZa+zK7m06/Glrr4WZFOV
LbOwxl36JpjywWTNcrXJd052U/377tUATXpepALBUUOIvWeGF7mrSTZkdhqRZRTe
Jr2+48zIuyMeB+JlY4UpR04pQNqstHimkyjxFfN/TKFqlhYqYjkCAwEAAaOB/DCB
+TASBgNVHRMBAf8ECDAGAQH/AgEAMA4GA1UdDwEB/wQEAwIBBjAdBgNVHQ4EFgQU
WBvk3qjnltkxKtEQxqYn5+KwYWkwgbMGA1UdIwSBqzCBqIAUWBvk3qjnltkxKtEQ
xqYn5+KwYWmhfaR7MHkxCzAJBgNVBAYTAlVTMQ0wCwYDVQQIDARVdGFoMRcwFQYD
VQQHDA5TYWx0IExha2UgQ2l0eTESMBAGA1UECgwJU2FsdFN0YWNrMRIwEAYDVQQD
DAlsb2NhbGhvc3QxGjAYBgkqhkiG9w0BCQEWC3h5ekBwZHEubmV0ghEA1bohQbms
x7PS8+LdxKZLdDANBgkqhkiG9w0BAQsFAAOCAQEALe312Oe8e+VjhnItcjQFuwcP
TaLf3+DTWaQLU1C8H78E75WE9UiRiVCyTpOLt/nONFkIKE275nCLPGCXn5JTZYVB
CxGFTRqnQ+8bdhZA6LYQPXieGikjTy+P2oiKOvPnYsATUXLbZ3ee+zEgBFGbbxNX
Argd3Vahg7Onu3ynsJz9a+hmwVqTX70Ykrrm+b/YtwKPfHeXTMxkX23jc4R7D+ED
VvROFJ27hFPLVaJrsq3EHb8ZkQHmRCzK2sMIPyJb2e0BOKDEZEphNxiIjerDnH7n
xDSMW0jK9FEv/W/sSBwoEolh3Q2e0gfd2vo7bEGvNF4eTqFsoAfeiAjWk65q0Q==
-----END CERTIFICATE-----""",
        "ca_cert_key": """-----BEGIN PRIVATE KEY-----
MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQDDbx3PC8KSOfzY
sEU1mBt+FkOb2rvIJI/vKeSnoVwzZg3AmPEFvcTWgsWOgLYNg8IebxGnLmykXJ0C
/UhSmB2uHXbZ5CEs0pHWTSJmO2VULXgyFTSZsuw62eEb1k69ns12C7/KDZKqyocp
7ecSAV2VrJVlGr9aTqfM/Dfi3l2gElcmo6geU4jfByUf7qfTJUn8v84bZusekiFL
BGWvsyu5tOvxpa6+FmRTlS2zsMZd+iaY8sFkzXK1yXdOdlP9++7VAE16XqQCwVFD
iL1nhhe5q0k2ZHYakWUU3ia9vuPMyLsjHgfiZWOFKUdOKUDarLR4ppMo8RXzf0yh
apYWKmI5AgMBAAECggEBAIRqIRRLr4VL7NkUdZAeg2Imy6Apz9mHjE5LYDWDyui4
WNEJzyRIs7lz2U74PmFhyIC+WIOhnNKwPWHtIrdzgYibRg/T1fZ8pXtBv/DshXdH
Z4zneUA6TnyBa1hlF+y6UBOPWl8YWyuFFZd/LXSxoCrtSDu8p7IUYPUuXt9EMsNk
+rQhBZH7iiOx2M7ckLb/gG4tElqh/QQ0Qhuy1e80oMfO9w1XxIThETx0LxQ7Uad5
vk5BQoEI+n/W1tPhXwQ/hndn3ub3pgfpKXIKi7AdySsdxTda4pJLyEwAm9MHrMNm
XvlBdQ+/vq4NSRk2oVVFzJ1yX7bfmrw+6ZqY36oOrUECgYEA4KvnSgeUyG4ouwA9
zTehvFhEWfFyj/y8Tl2OcaIeCvHahN3n6n++Rx25JYrQDhguMGgMHJ0dcZr0Wvvc
EPOAxjam96p2HJMYdpYmrwpguHDu4Jk+fOqgc8Ms541P3+sMej1UQxRaQ6c/g1EM
Pl0g2GdDN4bw60nbEwOXp0qFI1UCgYEA3q+GJDA+gkXcMqKN06VEdjPvm+BpOygx
VvO0cG6njcmVjJKPePIYbjcBHduQRbCGxLmntLOyVg6Ign1+r/LaG7AADYXMdURD
cn4J9ANKuT1lZcs/JRatA1qigwlk8E7vIqq0E/1EiEbRWVE34lgN3dkUOqAXLBfi
9p2aJMOtC1UCgYAKnDOtDFSbbpBf3HAOu/zYXzbDJKLrZ90gukxa03Qlwiw2sCAe
s++xfhbbTgXrVHsB8Df6NfVJAy9dCJ3o8wb21WfnNFalnNC/8PFcvNm6fCLb2oDX
92Ciduos+UB3a6tILpNHI7Prk/9s3Sv92foOHjpPagEAq5k7+aR00xEcjQKBgEhn
r+kCWsDG8ELygcToPqtkVatMO0sF1Y0dLnVENWyvt9V+LfI4XWMwtUc9Bdry+87p
QrNJnlnG3fH31gJlpy9Leajr8T/L01ZdzuStUVWLtfV0MXLgvZ6SkLakjlJoh+6w
rF63gdoBlL5C3zXURaX1mFM7jG1E0wI22lDL4u8FAoGAaeghxaW4V0keS0KpdPvL
kmEhQ5VDAG92fmzQa0wkBoTbsS4kitHj5QTfNJgdCDJbZ7srkMbQR7oVGeZKIDBk
L7lyhyrtHaR/r/fdUNEJAVsQt3Shaa5c5srLh6vzGcBsV7/nQqrEP+GadvGSbHNT
bymYbi0l2pWqQLA2sPoRHNw=
-----END PRIVATE KEY-----""",
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


def test_cert_base_path(self):
    """
    Test for retrieving cert base path
    """
    ca_path = "/etc/tls"
    mock_opt = MagicMock(return_value=ca_path)
    with patch.dict(tls.__salt__, {"config.option": mock_opt}):
        assert tls.cert_base_path() == ca_path
