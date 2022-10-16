import pytest

import salt.modules.mac_xattr as xattr
import salt.utils.mac_utils
from salt.exceptions import CommandExecutionError
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {xattr: {}}


def test_list():
    """
    Test xattr.list
    """
    expected = {"spongebob": "squarepants", "squidward": "patrick"}
    with patch.object(
        xattr, "read", MagicMock(side_effect=["squarepants", "patrick"])
    ), patch(
        "salt.utils.mac_utils.execute_return_result",
        MagicMock(return_value="spongebob\nsquidward"),
    ):
        assert xattr.list_("path/to/file") == expected


def test_list_missing():
    """
    Test listing attributes of a missing file
    """
    with patch(
        "salt.utils.mac_utils.execute_return_result",
        MagicMock(side_effect=CommandExecutionError("No such file")),
    ):
        pytest.raises(CommandExecutionError, xattr.list_, "/path/to/file")


def test_read():
    """
    Test reading a specific attribute from a file
    """
    with patch(
        "salt.utils.mac_utils.execute_return_result",
        MagicMock(return_value="expected results"),
    ):
        assert xattr.read("/path/to/file", "com.attr") == "expected results"


def test_read_hex():
    """
    Test reading a specific attribute from a file
    """
    with patch.object(
        salt.utils.mac_utils,
        "execute_return_result",
        MagicMock(return_value="expected results"),
    ) as mock:
        assert (
            xattr.read("/path/to/file", "com.attr", **{"hex": True})
            == "expected results"
        )
        mock.assert_called_once_with(["xattr", "-p", "-x", "com.attr", "/path/to/file"])


def test_read_missing():
    """
    Test reading a specific attribute from a file
    """
    with patch(
        "salt.utils.mac_utils.execute_return_result",
        MagicMock(side_effect=CommandExecutionError("No such file")),
    ):
        pytest.raises(CommandExecutionError, xattr.read, "/path/to/file", "attribute")


def test_write():
    """
    Test writing a specific attribute to a file
    """
    mock_cmd = MagicMock(return_value="squarepants")
    with patch.object(xattr, "read", mock_cmd), patch(
        "salt.utils.mac_utils.execute_return_success", MagicMock(return_value=True)
    ):
        assert xattr.write("/path/to/file", "spongebob", "squarepants")


def test_write_missing():
    """
    Test writing a specific attribute to a file
    """
    with patch(
        "salt.utils.mac_utils.execute_return_success",
        MagicMock(side_effect=CommandExecutionError("No such file")),
    ):
        pytest.raises(
            CommandExecutionError,
            xattr.write,
            "/path/to/file",
            "attribute",
            "value",
        )


def test_delete():
    """
    Test deleting a specific attribute from a file
    """
    mock_cmd = MagicMock(return_value={"spongebob": "squarepants"})
    with patch.object(xattr, "list_", mock_cmd), patch(
        "salt.utils.mac_utils.execute_return_success", MagicMock(return_value=True)
    ):
        assert xattr.delete("/path/to/file", "attribute")


def test_delete_missing():
    """
    Test deleting a specific attribute from a file
    """
    with patch(
        "salt.utils.mac_utils.execute_return_success",
        MagicMock(side_effect=CommandExecutionError("No such file")),
    ):
        pytest.raises(CommandExecutionError, xattr.delete, "/path/to/file", "attribute")


def test_clear():
    """
    Test clearing all attributes on a file
    """
    mock_cmd = MagicMock(return_value={})
    with patch.object(xattr, "list_", mock_cmd), patch(
        "salt.utils.mac_utils.execute_return_success", MagicMock(return_value=True)
    ):
        assert xattr.clear("/path/to/file")


def test_clear_missing():
    """
    Test clearing all attributes on a file
    """
    with patch(
        "salt.utils.mac_utils.execute_return_success",
        MagicMock(side_effect=CommandExecutionError("No such file")),
    ):
        pytest.raises(CommandExecutionError, xattr.clear, "/path/to/file")
