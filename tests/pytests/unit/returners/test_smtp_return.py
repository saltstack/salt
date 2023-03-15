"""
    :codeauthor: Mike Place (mp@saltstack.com)

    Test SMTP returner
"""
import pytest

import salt.returners.smtp_return as smtp
from salt.utils.jinja import SaltCacheLoader
from tests.support.mock import MagicMock, patch

try:
    import gnupg  # pylint: disable=unused-import

    HAS_GNUPG = True
except ImportError:
    HAS_GNUPG = False


@pytest.fixture
def configure_loader_modules():
    return {
        smtp: {
            "__opts__": {
                "extension_modules": "",
                "optimization_order": [0, 1, 2],
                "renderer": "jinja|yaml",
                "renderer_blacklist": [],
                "renderer_whitelist": [],
                "file_roots": {},
                "pillar_roots": {},
                "cachedir": "/",
                "master_uri": "tcp://127.0.0.1:4505",
                "pki_dir": "/",
                "keysize": 2048,
                "id": "test",
                "__role": "minion",
            }
        }
    }


def _test_returner(mocked_smtplib):  # pylint: disable=unused-argument
    """
    Test to see if the SMTP returner sends a message
    """
    ret = {
        "id": "12345",
        "fun": "mytest.func",
        "fun_args": "myfunc args",
        "jid": "54321",
        "return": "The room is on fire as shes fixing her hair",
    }
    options = {
        "username": "",
        "tls": "",
        "from": "",
        "fields": "id,fun,fun_args,jid,return",
        "to": "",
        "host": "",
        "renderer": "jinja|yaml",
        "template": "",
        "password": "",
        "gpgowner": "",
        "subject": "",
    }

    with patch(
        "salt.returners.smtp_return._get_options", MagicMock(return_value=options)
    ), patch.object(SaltCacheLoader, "file_client", MagicMock()):
        smtp.returner(ret)
        assert mocked_smtplib.return_value.sendmail.called is True


@pytest.mark.skipif(not HAS_GNUPG, reason="Need gnupg to run this test")
def test_returner_gnupg():
    with patch("salt.returners.smtp_return.gnupg"), patch(
        "salt.returners.smtp_return.smtplib.SMTP"
    ) as mocked_smtplib:
        _test_returner(mocked_smtplib)


@pytest.mark.skipif(HAS_GNUPG, reason="Only run this test without gnupg")
def test_returner_no_gnupg():
    with patch("salt.returners.smtp_return.smtplib.SMTP") as mocked_smtplib:
        _test_returner(mocked_smtplib)
