"""
:codeauthor: Herbert Buurman <herbert.buurman@ogd.nl>
"""


import datetime
import os
import textwrap

import pytest

# Import Salt Module
import salt.modules.acme as acme
import salt.utils.dictupdate
import salt.utils.platform
from salt.exceptions import SaltInvocationError
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {acme: {}}


def test_certs():
    """
    Test listing certs
    """
    with patch.dict(
        acme.__salt__,
        {  # pylint: disable=no-member
            "file.readdir": MagicMock(
                return_value=[".", "..", "README", "test_expired", "test_valid"]
            )
        },
    ), patch(
        "os.path.isdir",
        side_effect=lambda path: path
        in [
            os.path.join(acme.LE_LIVE, "test_expired"),
            os.path.join(acme.LE_LIVE, "test_valid"),
        ],
    ):
        assert acme.certs() == ["test_expired", "test_valid"]


def test_has():
    """
    Test checking if certificate (does not) exist.
    """
    with patch.dict(
        acme.__salt__, {"file.file_exists": MagicMock(return_value=True)}
    ):  # pylint: disable=no-member
        assert acme.has("test_expired")
    with patch.dict(
        acme.__salt__, {"file.file_exists": MagicMock(return_value=False)}
    ):  # pylint: disable=no-member
        assert not acme.has("test_invalid")


def test_needs_renewal():
    """
    Test if expired certs do indeed need renewal.
    """
    expired = (
        datetime.date.today() - datetime.timedelta(days=3) - datetime.date(1970, 1, 1)
    )
    valid = (
        datetime.date.today() + datetime.timedelta(days=3) - datetime.date(1970, 1, 1)
    )
    with patch.dict(
        acme.__salt__,
        {  # pylint: disable=no-member
            "tls.cert_info": MagicMock(
                return_value={"not_after": expired.total_seconds()}
            )
        },
    ):
        assert acme.needs_renewal("test_expired")
    with patch.dict(
        acme.__salt__,
        {  # pylint: disable=no-member
            "tls.cert_info": MagicMock(
                return_value={"not_after": valid.total_seconds()}
            )
        },
    ):
        assert not acme.needs_renewal("test_valid")
        # Test with integer window parameter
        assert acme.needs_renewal("test_valid", window=5)
        # Test with string-like window parameter
        assert acme.needs_renewal("test_valid", window="5")
        # Test with 'force' parameter
        assert acme.needs_renewal("test_valid", window="force")
        # Test with 'true' parameter
        assert acme.needs_renewal("test_valid", window=True)
        # Test with invalid window parameter
        pytest.raises(
            SaltInvocationError, acme.needs_renewal, "test_valid", window="foo"
        )


def test_expires():
    """
    Test if expires function functions properly.
    """
    test_value = datetime.datetime.today() - datetime.timedelta(days=3)
    test_stamp = test_value - datetime.datetime(1970, 1, 1)
    with patch.dict(
        acme.__salt__,
        {  # pylint: disable=no-member
            "tls.cert_info": MagicMock(
                return_value={"not_after": test_stamp.total_seconds()}
            )
        },
    ):
        assert (
            acme.expires("test_expired")
            == datetime.datetime.fromtimestamp(test_stamp.total_seconds()).isoformat()
        )


def test_info():
    """
    Test certificate information retrieval.
    """
    certinfo_tls_result = {
        "not_after": 1559471377,
        "signature_algorithm": "sha256WithRSAEncryption",
        "extensions": {},
        "fingerprint": (
            "FB:A4:5F:71:D6:5D:6C:B6:1D:2C:FD:91:09:2C:1C:52:"
            "3C:EC:B6:4D:1A:95:65:37:04:D0:E2:5E:C7:64:0C:9C"
        ),
        "serial_number": 6461481982668892235,
        "issuer": {},
        "not_before": 1559557777,
        "subject": {},
    }
    certinfo_x509_result = {
        "Not After": "2019-06-02 10:29:37",
        "Subject Hash": "54:3B:6C:A4",
        "Serial Number": "59:AB:CB:A0:FB:90:E8:4B",
        "SHA1 Finger Print": (
            "F1:8D:F3:26:1B:D3:88:32:CD:B6:FA:3B:85:58:DA:C7:6F:62:BE:7E"
        ),
        "SHA-256 Finger Print": (
            "FB:A4:5F:71:D6:5D:6C:B6:1D:2C:FD:91:09:2C:1C:52:"
            "3C:EC:B6:4D:1A:95:65:37:04:D0:E2:5E:C7:64:0C:9C"
        ),
        "MD5 Finger Print": "95:B5:96:9B:42:A5:9E:20:78:FD:99:09:4B:21:1E:97",
        "Version": 3,
        "Key Size": 2048,
        "Public Key": (
            "-----BEGIN PUBLIC KEY-----\n"
            "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAsVO2vwQPKU92PSBnuGid\n"
            "k8t6KWVE2jEBM10u7CgqQmD/JCnYflEHAo1nOsD7wxdhBrxhf5Qs+pEX1HOsh8VA\n"
            "HDTim0iE8nQVJ0Iuen2SrwaWMhwKmZTSJRYMgd46oCMi2RdlCvcgF2Hw6RTwF7FT\n"
            "hnksc4HBT91XddnP32N558tOT3YejafQNvClz5WcR+E0JzqGrV/+wfe3o+j/q5eK\n"
            "UowttWazeSMvuROtqj/fEk0rop4D14pgzZqWi30tjwhJNl6fSPFWBrLEHGNyDJ+O\n"
            "zfov0B2MRLJibH7GMkOCwsP2g1lVOReqcml+ju6zAKW8nHBTRg0iXB18Ifxef57Y\n"
            "AQIDAQAB\n"
            "-----END PUBLIC KEY-----\n"
        ),
        "Issuer": {},
        "Issuer Hash": "54:3B:6C:A4",
        "Not Before": "2019-06-03 10:29:37",
        "Subject": {},
    }

    with patch.dict(
        acme.__salt__,
        {  # pylint: disable=no-member
            "file.file_exists": MagicMock(return_value=True),
            "tls.cert_info": MagicMock(return_value=certinfo_tls_result),
        },
    ):
        assert acme.info("test") == certinfo_tls_result
    with patch.dict(
        acme.__salt__,
        {  # pylint: disable=no-member
            "file.file_exists": MagicMock(return_value=True),
            "x509.read_certificate": MagicMock(return_value=certinfo_x509_result),
        },
    ):
        assert acme.info("test") == certinfo_x509_result
    with patch.dict(
        acme.__salt__,
        {  # pylint: disable=no-member
            "file.file_exists": MagicMock(return_value=True),
            "cmd.run": MagicMock(return_value="foo"),
        },
    ):
        assert acme.info("test") == {"text": "foo"}


def test_cert():
    """
    Test certificate retrieval/renewal
    """
    valid_timestamp = (
        datetime.datetime.now()
        + datetime.timedelta(days=30)
        - datetime.datetime(1970, 1, 1, 0, 0, 0, 0)
    ).total_seconds()
    expired_timestamp = (
        datetime.datetime.now()
        - datetime.timedelta(days=3)
        - datetime.datetime(1970, 1, 1, 0, 0, 0, 0)
    ).total_seconds()
    cmd_new_cert = {
        "stdout": textwrap.dedent(
            """
            IMPORTANT NOTES:
             - Congratulations! Your certificate and chain have been saved at:
               /etc/letsencrypt/live/test/fullchain.pem
               Your key file has been saved at:
               /etc/letsencrypt/live/test/privkey.pem
               Your cert will expire on 2019-08-07. To obtain a new or tweaked
               version of this certificate in the future, simply run certbot
               again. To non-interactively renew *all* of your certificates, run
               "certbot renew"
             - If you like Certbot, please consider supporting our work by:

               Donating to ISRG / Let's Encrypt:   https://letsencrypt.org/donate
               Donating to EFF:                    https://eff.org/donate-le
            """
        ),
        "stderr": textwrap.dedent(
            """
            Saving debug log to /var/log/letsencrypt/letsencrypt.log
            Plugins selected: Authenticator standalone, Installer None
            Starting new HTTPS connection (1): acme-v02.api.letsencrypt.org
            Obtaining a new certificate
            Resetting dropped connection: acme-v02.api.letsencrypt.org
            """
        ),
        "retcode": 0,
    }
    result_new_cert = {
        "comment": "Certificate test obtained",
        "not_after": datetime.datetime.fromtimestamp(valid_timestamp).isoformat(),
        "changes": {"mode": "0640"},
        "result": True,
    }

    cmd_no_renew = {
        "stdout": textwrap.dedent(
            """
            - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
            Certificate not yet due for renewal; no action taken.
            - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
            """
        ),
        "stderr": textwrap.dedent(
            """Saving debug log to /var/log/letsencrypt/letsencrypt.log
            Plugins selected: Authenticator standalone, Installer None
            Starting new HTTPS connection (1): acme-v02.api.letsencrypt.org
            Cert not yet due for renewal
            Keeping the existing certificate
            """
        ),
        "retcode": 0,
    }
    if salt.utils.platform.is_freebsd():
        result_no_renew = {
            "comment": "Certificate "
            + os.path.join("/usr/local/etc/letsencrypt/live/test", "cert.pem")
            + " unchanged",
            "not_after": datetime.datetime.fromtimestamp(valid_timestamp).isoformat(),
            "changes": {},
            "result": True,
        }
    else:
        result_no_renew = {
            "comment": "Certificate "
            + os.path.join("/etc/letsencrypt/live/test", "cert.pem")
            + " unchanged",
            "not_after": datetime.datetime.fromtimestamp(valid_timestamp).isoformat(),
            "changes": {},
            "result": True,
        }
    result_renew = {
        "comment": "Certificate test renewed",
        "not_after": datetime.datetime.fromtimestamp(expired_timestamp).isoformat(),
        "changes": {},
        "result": True,
    }

    # Test fetching new certificate
    with patch("salt.modules.acme.LEA", "certbot"), patch.dict(
        acme.__salt__,
        {  # pylint: disable=no-member
            "cmd.run_all": MagicMock(return_value=cmd_new_cert),
            "file.file_exists": MagicMock(return_value=False),
            "tls.cert_info": MagicMock(return_value={"not_after": valid_timestamp}),
            "file.check_perms": MagicMock(
                side_effect=lambda a, x, b, c, d, follow_symlinks: (
                    salt.utils.dictupdate.set_dict_key_value(x, "changes:mode", "0640"),
                    None,
                )
            ),
        },
    ):
        assert acme.cert("test") == result_new_cert
        assert acme.cert("testing.example.com", certname="test") == result_new_cert
    # Test not renewing a valid certificate
    with patch("salt.modules.acme.LEA", "certbot"), patch.dict(
        acme.__salt__,
        {  # pylint: disable=no-member
            "cmd.run_all": MagicMock(return_value=cmd_no_renew),
            "file.file_exists": MagicMock(return_value=True),
            "tls.cert_info": MagicMock(return_value={"not_after": valid_timestamp}),
            "file.check_perms": MagicMock(
                side_effect=lambda a, x, b, c, d, follow_symlinks: (
                    salt.utils.dictupdate.set_dict_key_value(x, "result", True),
                    None,
                )
            ),
        },
    ):
        assert acme.cert("test") == result_no_renew
        assert acme.cert("testing.example.com", certname="test") == result_no_renew
    # Test renewing an expired certificate
    with patch("salt.modules.acme.LEA", "certbot"), patch.dict(
        acme.__salt__,
        {  # pylint: disable=no-member
            "cmd.run_all": MagicMock(return_value=cmd_new_cert),
            "file.file_exists": MagicMock(return_value=True),
            "tls.cert_info": MagicMock(return_value={"not_after": expired_timestamp}),
            "file.check_perms": MagicMock(
                side_effect=lambda a, x, b, c, d, follow_symlinks: (
                    salt.utils.dictupdate.set_dict_key_value(x, "result", True),
                    None,
                )
            ),
        },
    ):
        assert acme.cert("test") == result_renew
        assert acme.cert("testing.example.com", certname="test") == result_renew
