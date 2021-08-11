import pytest
import salt.states.macdefaults as macdefaults
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {macdefaults: {}}


def test_write():
    """
    Test writing a default setting
    """
    expected = {
        "changes": {"written": "com.apple.CrashReporter DialogType is set to Server"},
        "comment": "",
        "name": "DialogType",
        "result": True,
    }

    read_mock = MagicMock(return_value="Local")
    write_mock = MagicMock(return_value={"retcode": 0})
    with patch.dict(
        macdefaults.__salt__,
        {"macdefaults.read": read_mock, "macdefaults.write": write_mock},
    ):
        out = macdefaults.write("DialogType", "com.apple.CrashReporter", "Server")
        read_mock.assert_called_once_with("com.apple.CrashReporter", "DialogType", None)
        write_mock.assert_called_once_with(
            "com.apple.CrashReporter", "DialogType", "Server", "string", None
        )
        assert out == expected


def test_write_set():
    """
    Test writing a default setting that is already set
    """
    expected = {
        "changes": {},
        "comment": "com.apple.CrashReporter DialogType is already set to Server",
        "name": "DialogType",
        "result": True,
    }

    read_mock = MagicMock(return_value="Server")
    write_mock = MagicMock(return_value={"retcode": 0})
    with patch.dict(
        macdefaults.__salt__,
        {"macdefaults.read": read_mock, "macdefaults.write": write_mock},
    ):
        out = macdefaults.write("DialogType", "com.apple.CrashReporter", "Server")
        read_mock.assert_called_once_with("com.apple.CrashReporter", "DialogType", None)
        assert not write_mock.called
        assert out == expected


def test_write_boolean():
    """
    Test writing a default setting with a boolean
    """
    expected = {
        "changes": {"written": "com.apple.something Key is set to True"},
        "comment": "",
        "name": "Key",
        "result": True,
    }

    read_mock = MagicMock(return_value="0")
    write_mock = MagicMock(return_value={"retcode": 0})
    with patch.dict(
        macdefaults.__salt__,
        {"macdefaults.read": read_mock, "macdefaults.write": write_mock},
    ):
        out = macdefaults.write("Key", "com.apple.something", True, vtype="boolean")
        read_mock.assert_called_once_with("com.apple.something", "Key", None)
        write_mock.assert_called_once_with(
            "com.apple.something", "Key", True, "boolean", None
        )
        assert out == expected


def test_write_boolean_match():
    """
    Test writing a default setting with a boolean that is already set to the same value
    """
    expected = {
        "changes": {},
        "comment": "com.apple.something Key is already set to YES",
        "name": "Key",
        "result": True,
    }

    read_mock = MagicMock(return_value="1")
    write_mock = MagicMock(return_value={"retcode": 0})
    with patch.dict(
        macdefaults.__salt__,
        {"macdefaults.read": read_mock, "macdefaults.write": write_mock},
    ):
        out = macdefaults.write("Key", "com.apple.something", "YES", vtype="boolean")
        read_mock.assert_called_once_with("com.apple.something", "Key", None)
        assert not write_mock.called
        assert out == expected


def test_write_integer():
    """
    Test writing a default setting with a integer
    """
    expected = {
        "changes": {"written": "com.apple.something Key is set to 1337"},
        "comment": "",
        "name": "Key",
        "result": True,
    }

    read_mock = MagicMock(return_value="99")
    write_mock = MagicMock(return_value={"retcode": 0})
    with patch.dict(
        macdefaults.__salt__,
        {"macdefaults.read": read_mock, "macdefaults.write": write_mock},
    ):
        out = macdefaults.write("Key", "com.apple.something", 1337, vtype="integer")
        read_mock.assert_called_once_with("com.apple.something", "Key", None)
        write_mock.assert_called_once_with(
            "com.apple.something", "Key", 1337, "integer", None
        )
        assert out == expected


def test_write_integer_match():
    """
    Test writing a default setting with a integer that is already set to the same value
    """
    expected = {
        "changes": {},
        "comment": "com.apple.something Key is already set to 1337",
        "name": "Key",
        "result": True,
    }

    read_mock = MagicMock(return_value="1337")
    write_mock = MagicMock(return_value={"retcode": 0})
    with patch.dict(
        macdefaults.__salt__,
        {"macdefaults.read": read_mock, "macdefaults.write": write_mock},
    ):
        out = macdefaults.write("Key", "com.apple.something", 1337, vtype="integer")
        read_mock.assert_called_once_with("com.apple.something", "Key", None)
        assert not write_mock.called
        assert out == expected


def test_absent_already():
    """
    Test ensuring non-existent defaults value is absent
    """
    expected = {
        "changes": {},
        "comment": "com.apple.something Key is already absent",
        "name": "Key",
        "result": True,
    }

    mock = MagicMock(return_value={"retcode": 1})
    with patch.dict(macdefaults.__salt__, {"macdefaults.delete": mock}):
        out = macdefaults.absent("Key", "com.apple.something")
        mock.assert_called_once_with("com.apple.something", "Key", None)
        assert out == expected


def test_absent_deleting_existing():
    """
    Test removing an existing value
    """
    expected = {
        "changes": {"absent": "com.apple.something Key is now absent"},
        "comment": "",
        "name": "Key",
        "result": True,
    }

    mock = MagicMock(return_value={"retcode": 0})
    with patch.dict(macdefaults.__salt__, {"macdefaults.delete": mock}):
        out = macdefaults.absent("Key", "com.apple.something")
        mock.assert_called_once_with("com.apple.something", "Key", None)
        assert out == expected
