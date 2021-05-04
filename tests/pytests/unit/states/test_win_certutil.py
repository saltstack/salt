import pytest
import salt.states.win_certutil as certutil
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {certutil: {}}


def test_add_serial():
    """
    Test adding a certificate to specified certificate store
    """
    expected = {
        "changes": {"added": "/path/to/cert.cer"},
        "comment": "",
        "name": "/path/to/cert.cer",
        "result": True,
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
        cache_mock.assert_called_once_with("/path/to/cert.cer", "base")
        get_cert_serial_mock.assert_called_once_with("/tmp/cert.cer")
        get_store_serials_mock.assert_called_once_with("TrustedPublisher")
        add_mock.assert_called_once_with(
            "/path/to/cert.cer", "TrustedPublisher", retcode=True
        )
        assert expected == out


def test_add_serial_missing():
    """
    Test adding a certificate to specified certificate store when the file doesn't exist
    """
    expected = {
        "changes": {},
        "comment": "Certificate file not found.",
        "name": "/path/to/cert.cer",
        "result": False,
    }

    cache_mock = MagicMock(return_value=False)
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
        cache_mock.assert_called_once_with("/path/to/cert.cer", "base")
        assert not get_cert_serial_mock.called
        assert not get_store_serials_mock.called
        assert not add_mock.called
        assert expected == out


def test_add_serial_exists():
    """
    Test adding a certificate to specified certificate store when the cert already exists
    """
    expected = {
        "changes": {},
        "comment": "/path/to/cert.cer already stored.",
        "name": "/path/to/cert.cer",
        "result": True,
    }

    cache_mock = MagicMock(return_value="/tmp/cert.cer")
    get_cert_serial_mock = MagicMock(return_value="ABCDEF")
    get_store_serials_mock = MagicMock(return_value=["123456", "ABCDEF"])
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
        cache_mock.assert_called_once_with("/path/to/cert.cer", "base")
        get_cert_serial_mock.assert_called_once_with("/tmp/cert.cer")
        get_store_serials_mock.assert_called_once_with("TrustedPublisher")
        assert not add_mock.called
        assert expected == out


def test_add_serial_fail():
    """
    Test adding a certificate when the add fails
    """
    expected = {
        "changes": {},
        "comment": "Failed to store certificate /path/to/cert.cer",
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
        cache_mock.assert_called_once_with("/path/to/cert.cer", "base")
        get_cert_serial_mock.assert_called_once_with("/tmp/cert.cer")
        get_store_serials_mock.assert_called_once_with("TrustedPublisher")
        add_mock.assert_called_once_with(
            "/path/to/cert.cer", "TrustedPublisher", retcode=True
        )
        assert expected == out


def test_del_serial():
    """
    Test deleting a certificate from a specified certificate store
    """
    expected = {
        "changes": {"removed": "/path/to/cert.cer"},
        "comment": "",
        "name": "/path/to/cert.cer",
        "result": True,
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
        cache_mock.assert_called_once_with("/path/to/cert.cer", "base")
        get_cert_serial_mock.assert_called_once_with("/tmp/cert.cer")
        get_store_serials_mock.assert_called_once_with("TrustedPublisher")
        del_mock.assert_called_once_with(
            "/tmp/cert.cer", "TrustedPublisher", retcode=True
        )
        assert expected == out


def test_del_serial_missing():
    """
    Test deleting a certificate to specified certificate store when the file doesn't exist
    """
    expected = {
        "changes": {},
        "comment": "Certificate file not found.",
        "name": "/path/to/cert.cer",
        "result": False,
    }

    cache_mock = MagicMock(return_value=False)
    get_cert_serial_mock = MagicMock(return_value="ABCDEF")
    get_store_serials_mock = MagicMock(return_value=["123456"])
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
        cache_mock.assert_called_once_with("/path/to/cert.cer", "base")
        assert not get_cert_serial_mock.called
        assert not get_store_serials_mock.called
        assert not del_mock.called
        assert expected == out


def test_del_serial_doesnt_exists():
    """
    Test deleting a certificate to specified certificate store when the cert doesn't exists
    """
    expected = {
        "changes": {},
        "comment": "/path/to/cert.cer already removed.",
        "name": "/path/to/cert.cer",
        "result": True,
    }

    cache_mock = MagicMock(return_value="/tmp/cert.cer")
    get_cert_serial_mock = MagicMock(return_value="ABCDEF")
    get_store_serials_mock = MagicMock(return_value=["123456"])
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
        cache_mock.assert_called_once_with("/path/to/cert.cer", "base")
        get_cert_serial_mock.assert_called_once_with("/tmp/cert.cer")
        get_store_serials_mock.assert_called_once_with("TrustedPublisher")
        assert not del_mock.called
        assert expected == out


def test_del_serial_fail():
    """
    Test deleting a certificate from the store when the delete fails
    """
    expected = {
        "changes": {},
        "comment": "Failed to remove the certificate /path/to/cert.cer",
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
        cache_mock.assert_called_once_with("/path/to/cert.cer", "base")
        get_cert_serial_mock.assert_called_once_with("/tmp/cert.cer")
        get_store_serials_mock.assert_called_once_with("TrustedPublisher")
        del_mock.assert_called_once_with(
            "/tmp/cert.cer", "TrustedPublisher", retcode=True
        )
        assert expected == out
