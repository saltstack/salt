import logging

import pytest

import salt.modules.tls as tls
from salt.utils.versions import Version
from tests.support.helpers import SKIP_INITIAL_PHOTONOS_FAILURES
from tests.support.mock import MagicMock, mock_open, patch

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


@pytest.mark.parametrize(
    "expected_path, ca_path, config_option",
    (
        # Nothing passed in, nothing in config
        (None, None, {}),
        # fnord passed in so fnord should come out. Probably? This was based on
        # the existing code when the test was written.
        ("fnord", "fnord", {}),
        # same as above - config should be ignored.
        (
            "fnord",
            "fnord",
            {
                "ca.contextual_cert_base_path": "not fnord",
                "ca.cert_base_path": "also not fnord",
            },
        ),
        # Nothing passed in, look in contextual_cert_base_path first
        (
            "pick me",
            None,
            {
                "ca.contextual_cert_base_path": "pick me",
                "ca.cert_base_path": "also not fnord",
            },
        ),
        # Nothing passed in, or in contextual_cert_base_path first, fallback to cert_base_path
        (
            "now pick me!",
            None,
            {"ca.contextual_cert_base_path": "", "ca.cert_base_path": "now pick me!"},
        ),
        (
            "me too",
            None,
            {"ca.contextual_cert_base_path": None, "ca.cert_base_path": "me too"},
        ),
        ("me three", None, {"ca.cert_base_path": "me three"}),
    ),
)
def test_cert_base_path(expected_path, ca_path, config_option):
    """
    Test for retrieving cert base path
    """

    def path_getter(key):
        return config_option.get(key)

    mock_opt = MagicMock(side_effect=path_getter)
    with patch.dict(tls.__salt__, {"config.option": mock_opt}):
        assert tls.cert_base_path(ca_path) == expected_path


def test_when_ca_path_not_provided_and_no_contextual_cert_base_path_should_be_context_cert_base_path():
    # It's unclear on whether or not this is necessary. salt.modules.tls
    # doesn't have a specific way to set the context value, but it's possible
    # that it's getting set out of band somewhere. This at least ensures that
    # the behavior doesn't unexpectedly change, but it may be useless.
    with patch.dict(
        tls.__salt__, {"config.option": MagicMock(side_effect=(None, "blorp"))}
    ), patch.dict(tls.__context__, {"ca.cert_base_path": "expected path"}):
        actual_path = tls.cert_base_path()
        assert actual_path == "expected path"


@pytest.mark.parametrize(
    "expected_path, new_path, context",
    (
        (None, "", {}),
        (None, None, {}),
        ("fnord", None, {"ca.cert_base_path": "fnord"}),
        (
            "fnord",
            None,
            {"ca.contextual_cert_base_path": "fnord", "ca.cert_base_path": "not fnord"},
        ),
        (
            "fnord",
            "fnord",
            {
                "ca.contextual_cert_base_path": "not fnord",
                "ca.cert_base_path": "not fnord",
            },
        ),
    ),
)
def test_set_ca_cert_path(expected_path, new_path, context):
    """
    Test for setting the cert base path
    """
    with patch.dict(tls.__context__, context), patch.dict(
        tls.__salt__, {"config.option": MagicMock(return_value=None)}
    ):
        tls.set_ca_path(new_path)
        actual_path = tls.cert_base_path()
        assert actual_path == expected_path


@pytest.mark.parametrize("exists", [True, False])
def test_ca_exists(exists):
    """
    Test to see if ca does not exist
    """
    ca_path = "/tmp/test_tls"
    ca_name = "test_ca"
    mock_opt = MagicMock(return_value=ca_path)
    with patch.dict(tls.__salt__, {"config.option": mock_opt}), patch(
        "os.path.exists", MagicMock(return_value=exists)
    ), patch("salt.modules.tls.maybe_fix_ssl_version", MagicMock(return_value=exists)):
        assert tls.ca_exists(ca_name) is exists


def test_get_ca_fail():
    """
    Test get_ca failure
    """
    ca_path = "/tmp/test_tls"
    ca_name = "test_ca"
    mock_opt = MagicMock(return_value=ca_path)
    with patch.dict(tls.__salt__, {"config.option": mock_opt}), patch(
        "os.path.exists", MagicMock(return_value=False)
    ), patch("salt.modules.tls.maybe_fix_ssl_version", MagicMock(return_value=True)):
        with pytest.raises(ValueError):
            tls.get_ca(ca_name)


def test_get_ca_text(tls_test_data):
    """
    Test get_ca text
    """
    ca_path = "/tmp/test_tls"
    ca_name = "test_ca"
    mock_opt = MagicMock(return_value=ca_path)
    with patch(
        "salt.utils.files.fopen", mock_open(read_data=tls_test_data["ca_cert"])
    ), patch.dict(tls.__salt__, {"config.option": mock_opt}), patch(
        "os.path.exists", MagicMock(return_value=True)
    ), patch(
        "salt.modules.tls.maybe_fix_ssl_version", MagicMock(return_value=True)
    ):
        assert tls.get_ca(ca_name, as_text=True) == tls_test_data["ca_cert"]


def test_get_ca():
    """
    Test get_ca
    """
    ca_path = "/tmp/test_tls"
    ca_name = "test_ca"
    certp = "{0}/{1}/{1}_ca_cert.crt".format(ca_path, ca_name)
    mock_opt = MagicMock(return_value=ca_path)
    with patch.dict(tls.__salt__, {"config.option": mock_opt}), patch(
        "os.path.exists", MagicMock(return_value=True)
    ), patch("salt.modules.tls.maybe_fix_ssl_version", MagicMock(return_value=True)):
        assert tls.get_ca(ca_name) == certp


def test_cert_info(tls_test_data):
    """
    Test cert info
    """
    with patch("os.path.exists", MagicMock(return_value=True)), patch(
        "salt.modules.tls.maybe_fix_ssl_version", MagicMock(return_value=True)
    ):
        ca_path = "/tmp/test_tls"
        ca_name = "test_ca"
        certp = "{0}/{1}/{1}_ca_cert.crt".format(ca_path, ca_name)
        ret = {
            "not_after": 1462379961,
            "signature_algorithm": "sha256WithRSAEncryption",
            "extensions": None,
            "fingerprint": (
                "96:72:B3:0A:1D:34:37:05:75:57:44:7E:08:81:A7:09:"
                "0C:E1:8F:5F:4D:0C:49:CE:5B:D2:6B:45:D3:4D:FF:31"
            ),
            "serial_number": 284092004844685647925744086791559203700,
            "subject": {
                "C": "US",
                "CN": "localhost",
                "L": "Salt Lake City",
                "O": "SaltStack",
                "ST": "Utah",
                "emailAddress": "xyz@pdq.net",
            },
            "not_before": 1430843961,
            "issuer": {
                "C": "US",
                "CN": "localhost",
                "L": "Salt Lake City",
                "O": "SaltStack",
                "ST": "Utah",
                "emailAddress": "xyz@pdq.net",
            },
        }

        def ignore_extensions(data):
            """
            Ignore extensions pending a resolution of issue 24338
            """
            if "extensions" in data.keys():
                data["extensions"] = None
            return data

        # older pyopenssl versions don't have extensions or
        # signature_algorithms
        def remove_not_in_result(source, reference):
            if "signature_algorithm" not in reference:
                del source["signature_algorithm"]
            if "extensions" not in reference:
                del source["extensions"]

        with patch(
            "salt.utils.files.fopen", mock_open(read_data=tls_test_data["ca_cert"])
        ):
            try:
                result = ignore_extensions(tls.cert_info(certp))
            except AttributeError as err:
                # PyOpenSSL version 16.0.0 has an upstream bug in it where a call is made
                # in OpenSSL/crypto.py in the get_signature_algorithm function referencing
                # the cert_info attribute, which doesn't exist. This was fixed in subsequent
                # releases of PyOpenSSL with https://github.com/pyca/pyopenssl/pull/476
                if (
                    "'_cffi_backend.CDataGCP' object has no attribute 'cert_info'"
                    == str(err)
                ):
                    log.exception(err)
                    pytest.skip(
                        "Encountered an upstream error with PyOpenSSL: {}".format(err)
                    )
                if "'_cffi_backend.CDataGCP' object has no attribute 'object'" == str(
                    err
                ):
                    log.exception(err)
                    pytest.skip(
                        "Encountered an upstream error with PyOpenSSL: {}".format(err)
                    )
                # python-openssl version 0.14, when installed with the "junos-eznc" pip
                # package, causes an error on this test. Newer versions of PyOpenSSL do not have
                # this issue. If 0.14 is installed and we hit this error, skip the test.
                OpenSSL = pytest.importorskip("OpenSSL")
                if Version(OpenSSL.__version__) == Version("0.14"):
                    log.exception(err)
                    pytest.skip(
                        "Encountered a package conflict. OpenSSL version 0.14"
                        ' cannot be used with the "junos-eznc" pip package on this'
                        " test. Skipping."
                    )
                result = {}

        remove_not_in_result(ret, result)
        assert result == ret


def test_create_ca(tmp_path, tls_test_data):
    """
    Test creating CA cert
    """
    ca_path = tmp_path
    ca_name = "test_ca"
    certp = "{0}/{1}/{1}_ca_cert.crt".format(ca_path, ca_name)
    certk = "{0}/{1}/{1}_ca_cert.key".format(ca_path, ca_name)
    ret = 'Created Private Key: "{}" Created CA "{}": "{}"'.format(
        certk, ca_name, certp
    )
    mock_opt = MagicMock(return_value=ca_path)
    mock_ret = MagicMock(return_value=0)
    with patch.dict(
        tls.__salt__, {"config.option": mock_opt, "cmd.retcode": mock_ret}
    ), patch.dict(tls.__opts__, {"hash_type": "sha256", "cachedir": ca_path}), patch(
        "salt.modules.tls.maybe_fix_ssl_version", MagicMock(return_value=True)
    ):
        assert (
            tls.create_ca(
                ca_name, days=365, fixmode=False, **tls_test_data["create_ca"]
            )
            == ret
        )


def test_recreate_ca(tmp_path, tls_test_data):
    """
    Test creating CA cert when one already exists
    """
    ca_path = tmp_path
    ca_name = "test_ca"
    certp = "{0}/{1}/{1}_ca_cert.crt".format(ca_path, ca_name)
    certk = "{0}/{1}/{1}_ca_cert.key".format(ca_path, ca_name)
    ret = f'Created Private Key: "{certk}" Created CA "{ca_name}": "{certp}"'
    mock_opt = MagicMock(return_value=ca_path)
    mock_ret = MagicMock(return_value=0)
    with patch(
        "salt.modules.tls.maybe_fix_ssl_version", MagicMock(return_value=True)
    ), patch.dict(
        tls.__salt__, {"config.option": mock_opt, "cmd.retcode": mock_ret}
    ), patch.dict(
        tls.__opts__, {"hash_type": "sha256", "cachedir": ca_path}
    ), patch.dict(
        tls_test_data["create_ca"], {"replace": True}
    ):
        tls.create_ca(ca_name)
        assert (
            tls.create_ca(
                ca_name, days=365, fixmode=False, **tls_test_data["create_ca"]
            )
            == ret
        )


def test_create_csr(tmp_path, tls_test_data):
    """
    Test creating certificate signing request
    """
    ca_path = tmp_path
    ca_name = "test_ca"
    certp = "{}/{}/certs/{}.csr".format(
        ca_path, ca_name, tls_test_data["create_ca"]["CN"]
    )
    certk = "{}/{}/certs/{}.key".format(
        ca_path, ca_name, tls_test_data["create_ca"]["CN"]
    )
    ret = 'Created Private Key: "{}" Created CSR for "{}": "{}"'.format(
        certk, tls_test_data["create_ca"]["CN"], certp
    )
    mock_opt = MagicMock(return_value=ca_path)
    mock_ret = MagicMock(return_value=0)
    mock_pgt = MagicMock(return_value=False)
    with patch.dict(
        tls.__salt__,
        {
            "config.option": mock_opt,
            "cmd.retcode": mock_ret,
            "pillar.get": mock_pgt,
        },
    ), patch.dict(tls.__opts__, {"hash_type": "sha256", "cachedir": ca_path}), patch(
        "salt.modules.tls.maybe_fix_ssl_version", MagicMock(return_value=True)
    ):
        tls.create_ca(ca_name)
        assert tls.create_csr(ca_name, **tls_test_data["create_ca"]) == ret


def test_recreate_csr(tmp_path, tls_test_data):
    """
    Test creating certificate signing request when one already exists
    """
    ca_path = tmp_path
    ca_name = "test_ca"
    certp = "{}/{}/certs/{}.csr".format(
        ca_path, ca_name, tls_test_data["create_ca"]["CN"]
    )
    certk = "{}/{}/certs/{}.key".format(
        ca_path, ca_name, tls_test_data["create_ca"]["CN"]
    )
    ret = 'Created Private Key: "{}" Created CSR for "{}": "{}"'.format(
        certk, tls_test_data["create_ca"]["CN"], certp
    )
    mock_opt = MagicMock(return_value=ca_path)
    mock_ret = MagicMock(return_value=0)
    mock_pgt = MagicMock(return_value=False)
    with patch.dict(
        tls.__salt__,
        {
            "config.option": mock_opt,
            "cmd.retcode": mock_ret,
            "pillar.get": mock_pgt,
        },
    ), patch.dict(
        tls.__opts__, {"hash_type": "sha256", "cachedir": ca_path}
    ), patch.dict(
        tls_test_data["create_ca"], {"replace": True}
    ), patch(
        "salt.modules.tls.maybe_fix_ssl_version", MagicMock(return_value=True)
    ):
        tls.create_ca(ca_name)
        tls.create_csr(ca_name)
        assert tls.create_csr(ca_name, **tls_test_data["create_ca"]) == ret


def test_create_self_signed_cert(tmp_path, tls_test_data):
    """
    Test creating self signed certificate
    """
    ca_path = tmp_path
    tls_dir = "test_tls"
    certp = "{}/{}/certs/{}.crt".format(
        ca_path, tls_dir, tls_test_data["create_ca"]["CN"]
    )
    certk = "{}/{}/certs/{}.key".format(
        ca_path, tls_dir, tls_test_data["create_ca"]["CN"]
    )
    ret = 'Created Private Key: "{}" Created Certificate: "{}"'.format(certk, certp)
    mock_opt = MagicMock(return_value=ca_path)
    with patch.dict(tls.__salt__, {"config.option": mock_opt}), patch.dict(
        tls.__opts__, {"hash_type": "sha256", "cachedir": ca_path}
    ), patch("salt.modules.tls.maybe_fix_ssl_version", MagicMock(return_value=True)):
        assert (
            tls.create_self_signed_cert(
                tls_dir=tls_dir, days=365, **tls_test_data["create_ca"]
            )
            == ret
        )


def test_recreate_self_signed_cert(tmp_path, tls_test_data):
    """
    Test creating self signed certificate when one already exists
    """
    ca_path = tmp_path
    tls_dir = "test_tls"
    certp = "{}/{}/certs/{}.crt".format(
        ca_path, tls_dir, tls_test_data["create_ca"]["CN"]
    )
    certk = "{}/{}/certs/{}.key".format(
        ca_path, tls_dir, tls_test_data["create_ca"]["CN"]
    )
    ret = 'Created Private Key: "{}" Created Certificate: "{}"'.format(certk, certp)
    mock_opt = MagicMock(return_value=ca_path)
    with patch.dict(tls.__salt__, {"config.option": mock_opt}), patch.dict(
        tls.__opts__, {"hash_type": "sha256", "cachedir": ca_path}
    ), patch("salt.modules.tls.maybe_fix_ssl_version", MagicMock(return_value=True)):
        assert (
            tls.create_self_signed_cert(
                tls_dir=tls_dir, days=365, **tls_test_data["create_ca"]
            )
            == ret
        )


def test_create_ca_signed_cert(tmp_path, tls_test_data):
    """
    Test signing certificate from request
    """
    ca_path = tmp_path
    ca_name = "test_ca"
    certp = "{}/{}/certs/{}.crt".format(
        ca_path, ca_name, tls_test_data["create_ca"]["CN"]
    )
    ret = 'Created Certificate for "{}": "{}"'.format(
        tls_test_data["create_ca"]["CN"], certp
    )
    mock_opt = MagicMock(return_value=ca_path)
    mock_ret = MagicMock(return_value=0)
    mock_pgt = MagicMock(return_value=False)
    with patch.dict(
        tls.__salt__,
        {
            "config.option": mock_opt,
            "cmd.retcode": mock_ret,
            "pillar.get": mock_pgt,
        },
    ), patch.dict(tls.__opts__, {"hash_type": "sha256", "cachedir": ca_path}), patch(
        "salt.modules.tls.maybe_fix_ssl_version", MagicMock(return_value=True)
    ):
        tls.create_ca(ca_name)
        tls.create_csr(ca_name, **tls_test_data["create_ca"])
        assert (
            tls.create_ca_signed_cert(ca_name, tls_test_data["create_ca"]["CN"]) == ret
        )


def test_recreate_ca_signed_cert(tmp_path, tls_test_data):
    """
    Test signing certificate from request when certificate exists
    """
    ca_path = tmp_path
    ca_name = "test_ca"
    certp = "{}/{}/certs/{}.crt".format(
        ca_path, ca_name, tls_test_data["create_ca"]["CN"]
    )
    ret = 'Created Certificate for "{}": "{}"'.format(
        tls_test_data["create_ca"]["CN"], certp
    )
    mock_opt = MagicMock(return_value=ca_path)
    mock_ret = MagicMock(return_value=0)
    mock_pgt = MagicMock(return_value=False)
    with patch.dict(
        tls.__salt__,
        {
            "config.option": mock_opt,
            "cmd.retcode": mock_ret,
            "pillar.get": mock_pgt,
        },
    ), patch.dict(tls.__opts__, {"hash_type": "sha256", "cachedir": ca_path}), patch(
        "salt.modules.tls.maybe_fix_ssl_version", MagicMock(return_value=True)
    ):
        tls.create_ca(ca_name)
        tls.create_csr(ca_name)
        tls.create_ca_signed_cert(ca_name, tls_test_data["create_ca"]["CN"])
        assert (
            tls.create_ca_signed_cert(
                ca_name, tls_test_data["create_ca"]["CN"], replace=True
            )
            == ret
        )


def test_create_pkcs12(tmp_path, tls_test_data):
    """
    Test creating pkcs12
    """
    ca_path = tmp_path
    ca_name = "test_ca"
    certp = "{}/{}/certs/{}.p12".format(
        ca_path, ca_name, tls_test_data["create_ca"]["CN"]
    )
    ret = 'Created PKCS#12 Certificate for "{}": "{}"'.format(
        tls_test_data["create_ca"]["CN"], certp
    )
    mock_opt = MagicMock(return_value=ca_path)
    mock_ret = MagicMock(return_value=0)
    mock_pgt = MagicMock(return_value=False)
    with patch.dict(
        tls.__salt__,
        {
            "config.option": mock_opt,
            "cmd.retcode": mock_ret,
            "pillar.get": mock_pgt,
        },
    ), patch.dict(tls.__opts__, {"hash_type": "sha256", "cachedir": ca_path}), patch(
        "salt.modules.tls.maybe_fix_ssl_version", MagicMock(return_value=True)
    ):
        tls.create_ca(ca_name)
        tls.create_csr(ca_name, **tls_test_data["create_ca"])
        tls.create_ca_signed_cert(ca_name, tls_test_data["create_ca"]["CN"])
        assert (
            tls.create_pkcs12(ca_name, tls_test_data["create_ca"]["CN"], "password")
            == ret
        )


def test_recreate_pkcs12(tmp_path, tls_test_data):
    """
    Test creating pkcs12 when it already exists
    """
    ca_path = tmp_path
    ca_name = "test_ca"
    certp = "{}/{}/certs/{}.p12".format(
        ca_path, ca_name, tls_test_data["create_ca"]["CN"]
    )
    ret = 'Created PKCS#12 Certificate for "{}": "{}"'.format(
        tls_test_data["create_ca"]["CN"], certp
    )
    mock_opt = MagicMock(return_value=ca_path)
    mock_ret = MagicMock(return_value=0)
    mock_pgt = MagicMock(return_value=False)
    with patch.dict(
        tls.__salt__,
        {
            "config.option": mock_opt,
            "cmd.retcode": mock_ret,
            "pillar.get": mock_pgt,
        },
    ), patch.dict(
        tls.__opts__, {"hash_type": "sha256", "cachedir": ca_path}
    ), patch.dict(
        tls_test_data["create_ca"], {"replace": True}
    ), patch(
        "salt.modules.tls.maybe_fix_ssl_version", MagicMock(return_value=True)
    ):
        tls.create_ca(ca_name)
        tls.create_csr(ca_name)
        tls.create_ca_signed_cert(ca_name, tls_test_data["create_ca"]["CN"])
        tls.create_pkcs12(ca_name, tls_test_data["create_ca"]["CN"], "password")
        assert (
            tls.create_pkcs12(
                ca_name, tls_test_data["create_ca"]["CN"], "password", replace=True
            )
            == ret
        )


def test_pyOpenSSL_version():
    """
    Test extension logic with different pyOpenSSL versions
    """
    pillarval = {"csr": {"extendedKeyUsage": "serverAuth"}}
    mock_pgt = MagicMock(return_value=pillarval)
    with patch.dict(
        tls.__dict__,
        {"OpenSSL_version": Version("0.1.1"), "X509_EXT_ENABLED": False},
    ):
        assert tls.__virtual__() == (
            False,
            "PyOpenSSL version 0.10 or later must be installed before this module can be used.",
        )
        with patch.dict(tls.__salt__, {"pillar.get": mock_pgt}):
            for thing in ("server", "client"):
                with pytest.raises(AssertionError):
                    tls.get_extensions(thing)
    with patch.dict(
        tls.__dict__,
        {"OpenSSL_version": Version("0.14.1"), "X509_EXT_ENABLED": True},
    ):
        assert tls.__virtual__()
        with patch.dict(tls.__salt__, {"pillar.get": mock_pgt}):
            assert tls.get_extensions("server") == pillarval
            assert tls.get_extensions("client") == pillarval
    with patch.dict(
        tls.__dict__,
        {"OpenSSL_version": Version("0.15.1"), "X509_EXT_ENABLED": True},
    ):
        assert tls.__virtual__()
        with patch.dict(tls.__salt__, {"pillar.get": mock_pgt}):
            assert tls.get_extensions("server") == pillarval
            assert tls.get_extensions("client") == pillarval


def test_pyOpenSSL_version_destructive(tmp_path, tls_test_data):
    """
    Test extension logic with different pyOpenSSL versions
    """
    ca_path = tmp_path
    pillarval = {"csr": {"extendedKeyUsage": "serverAuth"}}
    mock_pgt = MagicMock(return_value=pillarval)
    ca_name = "test_ca"
    certp = "{0}/{1}/{1}_ca_cert.crt".format(ca_path, ca_name)
    certk = "{0}/{1}/{1}_ca_cert.key".format(ca_path, ca_name)
    ret = 'Created Private Key: "{}" Created CA "{}": "{}"'.format(
        certk, ca_name, certp
    )
    mock_opt = MagicMock(return_value=ca_path)
    mock_ret = MagicMock(return_value=0)
    with patch.dict(tls.__salt__, {"config.option": mock_opt, "cmd.retcode": mock_ret}):
        with patch.dict(tls.__opts__, {"hash_type": "sha256", "cachedir": ca_path}):
            with patch.dict(tls_test_data["create_ca"], {"replace": True}):
                with patch.dict(
                    tls.__dict__,
                    {
                        "OpenSSL_version": Version("0.1.1"),
                        "X509_EXT_ENABLED": False,
                    },
                ):
                    assert (
                        tls.create_ca(
                            ca_name,
                            days=365,
                            fixmode=False,
                            **tls_test_data["create_ca"],
                        )
                        == ret
                    )
                with patch.dict(
                    tls.__dict__,
                    {
                        "OpenSSL_version": Version("0.14.1"),
                        "X509_EXT_ENABLED": True,
                    },
                ):
                    assert (
                        tls.create_ca(
                            ca_name,
                            days=365,
                            fixmode=False,
                            **tls_test_data["create_ca"],
                        )
                        == ret
                    )
                with patch.dict(
                    tls.__dict__,
                    {
                        "OpenSSL_version": Version("0.15.1"),
                        "X509_EXT_ENABLED": True,
                    },
                ):
                    assert (
                        tls.create_ca(
                            ca_name,
                            days=365,
                            fixmode=False,
                            **tls_test_data["create_ca"],
                        )
                        == ret
                    )

    certp = "{}/{}/certs/{}.csr".format(
        ca_path, ca_name, tls_test_data["create_ca"]["CN"]
    )
    certk = "{}/{}/certs/{}.key".format(
        ca_path, ca_name, tls_test_data["create_ca"]["CN"]
    )
    ret = 'Created Private Key: "{}" Created CSR for "{}": "{}"'.format(
        certk, tls_test_data["create_ca"]["CN"], certp
    )
    with patch.dict(
        tls.__salt__,
        {
            "config.option": mock_opt,
            "cmd.retcode": mock_ret,
            "pillar.get": mock_pgt,
        },
    ):
        with patch.dict(tls.__opts__, {"hash_type": "sha256", "cachedir": ca_path}):
            with patch.dict(
                tls_test_data["create_ca"],
                {"subjectAltName": "DNS:foo.bar", "replace": True},
            ):
                with patch.dict(
                    tls.__dict__,
                    {
                        "OpenSSL_version": Version("0.1.1"),
                        "X509_EXT_ENABLED": False,
                    },
                ):
                    tls.create_ca(ca_name)
                    tls.create_csr(ca_name)
                    with pytest.raises(ValueError):
                        tls.create_csr(ca_name, **tls_test_data["create_ca"])
                with patch.dict(
                    tls.__dict__,
                    {
                        "OpenSSL_version": Version("0.14.1"),
                        "X509_EXT_ENABLED": True,
                    },
                ):
                    tls.create_ca(ca_name)
                    tls.create_csr(ca_name)
                    assert tls.create_csr(ca_name, **tls_test_data["create_ca"]) == ret
                with patch.dict(
                    tls.__dict__,
                    {
                        "OpenSSL_version": Version("0.15.1"),
                        "X509_EXT_ENABLED": True,
                    },
                ):
                    tls.create_ca(ca_name)
                    tls.create_csr(ca_name)
                    assert tls.create_csr(ca_name, **tls_test_data["create_ca"]) == ret


def test_get_expiration_date(tls_test_data):
    with patch("salt.utils.files.fopen", mock_open(read_data=tls_test_data["ca_cert"])):
        assert tls.get_expiration_date("/path/to/cert") == "2016-05-04"
    with patch("salt.utils.files.fopen", mock_open(read_data=tls_test_data["ca_cert"])):
        assert (
            tls.get_expiration_date("/path/to/cert", date_format="%d/%m/%y")
            == "04/05/16"
        )
