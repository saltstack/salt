"""
    Test cases for salt.modules.win_pki
"""

import pytest

import salt.modules.win_pki as win_pki
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {win_pki: {}}


@pytest.fixture
def cert_path():
    return r"C:\certs\testdomain.local.cer"


@pytest.fixture
def thumbprint():
    return "9988776655443322111000AAABBBCCCDDDEEEFFF"


@pytest.fixture
def certs(thumbprint):
    return {
        thumbprint: {
            "dnsnames": ["testdomain.local"],
            "serialnumber": "0123456789AABBCCDD",
            "subject": "CN=testdomain.local, OU=testou, O=testorg, S=California, C=US",
            "thumbprint": thumbprint,
            "version": 3,
        }
    }


@pytest.fixture
def stores():
    return {
        "CurrentUser": [
            "AuthRoot",
            "CA",
            "ClientAuthIssuer",
            "Disallowed",
            "MSIEHistoryJournal",
            "My",
            "Root",
            "SmartCardRoot",
            "Trust",
            "TrustedPeople",
            "TrustedPublisher",
            "UserDS",
        ],
        "LocalMachine": [
            "AuthRoot",
            "CA",
            "ClientAuthIssuer",
            "Disallowed",
            "My",
            "Remote Desktop",
            "Root",
            "SmartCardRoot",
            "Trust",
            "TrustedDevices",
            "TrustedPeople",
            "TrustedPublisher",
            "WebHosting",
        ],
    }


@pytest.fixture
def json_certs():
    return [
        {
            "DnsNameList": [
                {"Punycode": "testdomain.local", "Unicode": "testdomain.local"}
            ],
            "SerialNumber": "0123456789AABBCCDD",
            "Subject": "CN=testdomain.local, OU=testou, O=testorg, S=California, C=US",
            "Thumbprint": "9988776655443322111000AAABBBCCCDDDEEEFFF",
            "Version": 3,
        }
    ]


@pytest.fixture
def json_stores(stores):
    return [
        {"LocationName": "CurrentUser", "StoreNames": stores["CurrentUser"]},
        {"LocationName": "LocalMachine", "StoreNames": stores["LocalMachine"]},
    ]


def test_get_stores(stores, json_stores):
    """
    Test - Get the certificate location contexts and their corresponding stores.
    """
    with patch.dict(win_pki.__salt__), patch(
        "salt.modules.win_pki._cmd_run", MagicMock(return_value=json_stores)
    ):
        assert win_pki.get_stores() == stores


def test_get_certs(certs, json_certs):
    """
    Test - Get the available certificates in the given store.
    """
    with patch.dict(win_pki.__salt__), patch(
        "salt.modules.win_pki._cmd_run", MagicMock(return_value=json_certs)
    ), patch("salt.modules.win_pki._validate_cert_path", MagicMock(return_value=None)):
        assert win_pki.get_certs() == certs


def test_get_cert_file(cert_path, thumbprint, certs, json_certs):
    """
    Test - Get the details of the certificate file.
    """
    kwargs = {"name": cert_path}
    with patch.dict(win_pki.__salt__), patch(
        "os.path.isfile", MagicMock(return_value=True)
    ), patch("salt.modules.win_pki._cmd_run", MagicMock(return_value=json_certs)):
        assert win_pki.get_cert_file(**kwargs) == certs[thumbprint]


def test_import_cert(cert_path, thumbprint, certs, json_certs):
    """
    Test - Import the certificate file into the given certificate store.
    """
    kwargs = {"name": cert_path}
    mock_value = MagicMock(return_value=cert_path)
    with patch.dict(win_pki.__salt__, {"cp.cache_file": mock_value}), patch(
        "salt.modules.win_pki._cmd_run", MagicMock(return_value=json_certs)
    ), patch(
        "salt.modules.win_pki._validate_cert_path", MagicMock(return_value=None)
    ), patch(
        "salt.modules.win_pki.get_cert_file",
        MagicMock(return_value=certs[thumbprint]),
    ), patch(
        "salt.modules.win_pki.get_certs", MagicMock(return_value=certs)
    ):
        assert win_pki.import_cert(**kwargs)


def test_export_cert(cert_path, thumbprint):
    """
    Test - Export the certificate to a file from the given certificate store.
    """
    kwargs = {"name": cert_path, "thumbprint": thumbprint}
    with patch.dict(win_pki.__salt__), patch(
        "salt.modules.win_pki._cmd_run", MagicMock(return_value="True")
    ), patch(
        "salt.modules.win_pki._validate_cert_format", MagicMock(return_value=None)
    ), patch(
        "salt.modules.win_pki._validate_cert_path", MagicMock(return_value=None)
    ):
        assert win_pki.export_cert(**kwargs)


def test_test_cert(thumbprint):
    """
    Test - Check the certificate for validity.
    """
    with patch.dict(win_pki.__salt__), patch(
        "salt.modules.win_pki._cmd_run", MagicMock(return_value="True")
    ), patch("salt.modules.win_pki._validate_cert_path", MagicMock(return_value=None)):
        assert win_pki.test_cert(thumbprint=thumbprint)


def test_remove_cert(thumbprint, certs):
    """
    Test - Remove the certificate from the given certificate store.
    """
    with patch.dict(win_pki.__salt__), patch(
        "salt.modules.win_pki._cmd_run", MagicMock(return_value=None)
    ), patch(
        "salt.modules.win_pki._validate_cert_path", MagicMock(return_value=None)
    ), patch(
        "salt.modules.win_pki.get_certs", MagicMock(return_value=certs)
    ):
        assert win_pki.remove_cert(thumbprint=thumbprint[::-1])
