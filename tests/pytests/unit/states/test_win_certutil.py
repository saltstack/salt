import pytest

import salt.states.win_certutil as certutil
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {certutil: {"__opts__": {"test": False}}}


def test_add_store_fail_retcode():
    """
    Test adding a certificate when the add fails
    """
    expected = {
        "changes": {},
        "comment": "Error adding certificate: /path/to/cert.cer",
        "name": "/path/to/cert.cer",
        "result": False,
    }

    cache_mock = MagicMock(return_value="/tmp/cert.cer")
    get_cert_serial_mock = MagicMock(return_value="ABCDEF")
    get_store_serials_mock = MagicMock(return_value=["123456"])
    add_mock = MagicMock(return_value=2146885628)
    with patch.dict(
        certutil.__salt__,
        {
            "cp.cache_file": cache_mock,
            "certutil.get_cert_serial": get_cert_serial_mock,
            "certutil.get_stored_cert_serials": get_store_serials_mock,
            "certutil.add_store": add_mock,
        },
    ):
        out = certutil.add_store("/path/to/cert.cer", "TrustedPublisher")
        assert expected == out


def test_add_store_fail_check():
    """
    Test adding a certificate when serial not in store after add
    """
    expected = {
        "changes": {},
        "comment": "Failed to add certificate: /path/to/cert.cer",
        "name": "/path/to/cert.cer",
        "result": False,
    }

    cache_mock = MagicMock(return_value="/tmp/cert.cer")
    get_cert_serial_mock = MagicMock(return_value="ABCDEF")
    get_store_serials_mock = MagicMock(return_value=["123456"])
    add_mock = MagicMock(return_value=0)
    with patch.dict(
        certutil.__salt__,
        {
            "cp.cache_file": cache_mock,
            "certutil.get_cert_serial": get_cert_serial_mock,
            "certutil.get_stored_cert_serials": get_store_serials_mock,
            "certutil.add_store": add_mock,
        },
    ):
        out = certutil.add_store("/path/to/cert.cer", "TrustedPublisher")
        assert expected == out


def test_del_store_fail_retcode():
    """
    Test deleting a certificate from the store when the delete fails
    """
    expected = {
        "changes": {},
        "comment": "Error removing certificate: /path/to/cert.cer",
        "name": "/path/to/cert.cer",
        "result": False,
    }

    cache_mock = MagicMock(return_value="/tmp/cert.cer")
    get_cert_serial_mock = MagicMock(return_value="ABCDEF")
    get_store_serials_mock = MagicMock(return_value=["123456", "ABCDEF"])
    del_mock = MagicMock(return_value=2146885628)
    with patch.dict(
        certutil.__salt__,
        {
            "cp.cache_file": cache_mock,
            "certutil.get_cert_serial": get_cert_serial_mock,
            "certutil.get_stored_cert_serials": get_store_serials_mock,
            "certutil.del_store": del_mock,
        },
    ):
        out = certutil.del_store("/path/to/cert.cer", "TrustedPublisher")
        assert expected == out


def test_del_store_fail_check():
    """
    Test deleting a certificate from the store when the delete fails
    """
    expected = {
        "changes": {},
        "comment": "Failed to remove certificate: /path/to/cert.cer",
        "name": "/path/to/cert.cer",
        "result": False,
    }

    cache_mock = MagicMock(return_value="/tmp/cert.cer")
    get_cert_serial_mock = MagicMock(return_value="ABCDEF")
    get_store_serials_mock = MagicMock(return_value=["123456", "ABCDEF"])
    del_mock = MagicMock(return_value=0)
    with patch.dict(
        certutil.__salt__,
        {
            "cp.cache_file": cache_mock,
            "certutil.get_cert_serial": get_cert_serial_mock,
            "certutil.get_stored_cert_serials": get_store_serials_mock,
            "certutil.del_store": del_mock,
        },
    ):
        out = certutil.del_store("/path/to/cert.cer", "TrustedPublisher")
        assert expected == out
