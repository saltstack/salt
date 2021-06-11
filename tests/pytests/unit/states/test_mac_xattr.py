import pytest
import salt.states.mac_xattr as xattr
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {xattr: {}}


def test_exists_not():
    """
    Test adding an attribute when it doesn't exist
    """
    with patch("os.path.exists") as exists_mock:
        expected = {
            "changes": {"key": "value"},
            "comment": "",
            "name": "/path/to/file",
            "result": True,
        }

        exists_mock.return_value = True

        list_mock = MagicMock(return_value={"other.id": "value2"})
        write_mock = MagicMock()
        with patch.dict(
            xattr.__salt__, {"xattr.list": list_mock, "xattr.write": write_mock}
        ):
            out = xattr.exists("/path/to/file", ["key=value"])

            list_mock.assert_called_once_with("/path/to/file")
            write_mock.assert_called_once_with("/path/to/file", "key", "value", False)
            assert out == expected


def test_exists_change():
    """
    Test changing an attribute value
    """
    with patch("os.path.exists") as exists_mock:
        expected = {
            "changes": {"key": "other_value"},
            "comment": "",
            "name": "/path/to/file",
            "result": True,
        }

        exists_mock.return_value = True

        list_mock = MagicMock(return_value={"key": "value"})
        write_mock = MagicMock()
        with patch.dict(
            xattr.__salt__, {"xattr.list": list_mock, "xattr.write": write_mock}
        ):
            out = xattr.exists("/path/to/file", ["key=other_value"])

            list_mock.assert_called_once_with("/path/to/file")
            write_mock.assert_called_once_with(
                "/path/to/file", "key", "other_value", False
            )
            assert out == expected


def test_exists_already():
    """
    Test with the same value does nothing
    """
    with patch("os.path.exists") as exists_mock:
        expected = {
            "changes": {},
            "comment": "All values existed correctly.",
            "name": "/path/to/file",
            "result": True,
        }

        exists_mock.return_value = True

        list_mock = MagicMock(return_value={"key": "value"})
        write_mock = MagicMock()
        with patch.dict(
            xattr.__salt__, {"xattr.list": list_mock, "xattr.write": write_mock}
        ):
            out = xattr.exists("/path/to/file", ["key=value"])

            list_mock.assert_called_once_with("/path/to/file")
            assert not write_mock.called
            assert out == expected


def test_delete():
    """
    Test deleting an attribute from a file
    """
    with patch("os.path.exists") as exists_mock:
        expected = {
            "changes": {"key": "delete"},
            "comment": "",
            "name": "/path/to/file",
            "result": True,
        }

        exists_mock.return_value = True

        list_mock = MagicMock(return_value={"key": "value2"})
        delete_mock = MagicMock()
        with patch.dict(
            xattr.__salt__, {"xattr.list": list_mock, "xattr.delete": delete_mock}
        ):
            out = xattr.delete("/path/to/file", ["key"])

            list_mock.assert_called_once_with("/path/to/file")
            delete_mock.assert_called_once_with("/path/to/file", "key")
            assert out == expected


def test_delete_not():
    """
    Test deleting an attribute that doesn't exist from a file
    """
    with patch("os.path.exists") as exists_mock:
        expected = {
            "changes": {},
            "comment": "All attributes were already deleted.",
            "name": "/path/to/file",
            "result": True,
        }

        exists_mock.return_value = True

        list_mock = MagicMock(return_value={"other.key": "value2"})
        delete_mock = MagicMock()
        with patch.dict(
            xattr.__salt__, {"xattr.list": list_mock, "xattr.delete": delete_mock}
        ):
            out = xattr.delete("/path/to/file", ["key"])

            list_mock.assert_called_once_with("/path/to/file")
            assert not delete_mock.called
            assert out == expected
