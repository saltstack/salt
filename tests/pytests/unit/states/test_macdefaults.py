import pytest

import salt.states.macdefaults as macdefaults
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {macdefaults: {}}


def test_write_default():
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


def test_write_default_already_set():
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


def test_write_default_boolean():
    """
    Test writing a default setting with a boolean
    """
    expected = {
        "changes": {"written": "com.apple.something Key is set to True"},
        "comment": "",
        "name": "Key",
        "result": True,
    }

    read_mock = MagicMock(return_value=False)
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


def test_write_default_boolean_already_set():
    """
    Test writing a default setting with a boolean that is already set
    """
    expected = {
        "changes": {},
        "comment": "com.apple.something Key is already set to True",
        "name": "Key",
        "result": True,
    }

    read_mock = MagicMock(return_value=True)
    write_mock = MagicMock(return_value={"retcode": 0})
    with patch.dict(
        macdefaults.__salt__,
        {"macdefaults.read": read_mock, "macdefaults.write": write_mock},
    ):
        out = macdefaults.write("Key", "com.apple.something", "YES", vtype="boolean")
        read_mock.assert_called_once_with("com.apple.something", "Key", None)
        assert not write_mock.called
        assert out == expected


def test_write_default_integer():
    """
    Test writing a default setting with a integer
    """
    expected = {
        "changes": {"written": "com.apple.something Key is set to 1337"},
        "comment": "",
        "name": "Key",
        "result": True,
    }

    read_mock = MagicMock(return_value=99)
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


def test_write_default_integer_already_set():
    """
    Test writing a default setting with an integer that is already set
    """
    expected = {
        "changes": {},
        "comment": "com.apple.something Key is already set to 1337",
        "name": "Key",
        "result": True,
    }

    read_mock = MagicMock(return_value=1337)
    write_mock = MagicMock(return_value={"retcode": 0})
    with patch.dict(
        macdefaults.__salt__,
        {"macdefaults.read": read_mock, "macdefaults.write": write_mock},
    ):
        out = macdefaults.write("Key", "com.apple.something", 1337, vtype="integer")
        read_mock.assert_called_once_with("com.apple.something", "Key", None)
        assert not write_mock.called
        assert out == expected


def test_write_default_float():
    """
    Test writing a default setting with a float
    """
    expected = {
        "changes": {"written": "com.apple.something Key is set to 0.865"},
        "comment": "",
        "name": "Key",
        "result": True,
    }

    read_mock = MagicMock(return_value=0.4)
    write_mock = MagicMock(return_value={"retcode": 0})
    with patch.dict(
        macdefaults.__salt__,
        {"macdefaults.read": read_mock, "macdefaults.write": write_mock},
    ):
        out = macdefaults.write("Key", "com.apple.something", 0.865, vtype="float")
        read_mock.assert_called_once_with("com.apple.something", "Key", None)
        write_mock.assert_called_once_with(
            "com.apple.something", "Key", 0.865, "float", None
        )
        assert out == expected


def test_write_default_float_already_set():
    """
    Test writing a default setting with a float that is already set_default
    """
    expected = {
        "changes": {},
        "comment": "com.apple.something Key is already set to 0.865",
        "name": "Key",
        "result": True,
    }

    read_mock = MagicMock(return_value=0.865)
    write_mock = MagicMock(return_value={"retcode": 0})
    with patch.dict(
        macdefaults.__salt__,
        {"macdefaults.read": read_mock, "macdefaults.write": write_mock},
    ):
        out = macdefaults.write("Key", "com.apple.something", 0.86500, vtype="float")
        read_mock.assert_called_once_with("com.apple.something", "Key", None)
        assert not write_mock.called
        assert out == expected


def test_write_default_array():
    """
    Test writing a default setting with an array
    """
    value = ["a", 1, 0.5, True]
    expected = {
        "changes": {"written": f"com.apple.something Key is set to {value}"},
        "comment": "",
        "name": "Key",
        "result": True,
    }

    read_mock = MagicMock(return_value=None)
    write_mock = MagicMock(return_value={"retcode": 0})
    with patch.dict(
        macdefaults.__salt__,
        {"macdefaults.read": read_mock, "macdefaults.write": write_mock},
    ):
        out = macdefaults.write("Key", "com.apple.something", value, vtype="array")
        read_mock.assert_called_once_with("com.apple.something", "Key", None)
        write_mock.assert_called_once_with(
            "com.apple.something", "Key", value, "array", None
        )
        assert out == expected


def test_write_default_array_already_set():
    """
    Test writing a default setting with an array that is already set
    """
    value = ["a", 1, 0.5, True]
    expected = {
        "changes": {},
        "comment": f"com.apple.something Key is already set to {value}",
        "name": "Key",
        "result": True,
    }

    read_mock = MagicMock(return_value=value)
    write_mock = MagicMock(return_value={"retcode": 0})
    with patch.dict(
        macdefaults.__salt__,
        {"macdefaults.read": read_mock, "macdefaults.write": write_mock},
    ):
        out = macdefaults.write("Key", "com.apple.something", value, vtype="array")
        read_mock.assert_called_once_with("com.apple.something", "Key", None)
        assert not write_mock.called
        assert out == expected


def test_write_default_array_add():
    """
    Test writing a default setting adding an array to another
    """
    write_value = ["a", 1]
    read_value = ["b", 2]
    expected = {
        "changes": {"written": f"com.apple.something Key is set to {write_value}"},
        "comment": "",
        "name": "Key",
        "result": True,
    }

    read_mock = MagicMock(return_value=read_value)
    write_mock = MagicMock(return_value={"retcode": 0})
    with patch.dict(
        macdefaults.__salt__,
        {"macdefaults.read": read_mock, "macdefaults.write": write_mock},
    ):
        out = macdefaults.write(
            "Key", "com.apple.something", write_value, vtype="array-add"
        )
        read_mock.assert_called_once_with("com.apple.something", "Key", None)
        write_mock.assert_called_once_with(
            "com.apple.something", "Key", write_value, "array-add", None
        )
        assert out == expected


def test_write_default_array_add_already_set_distinct_order():
    """
    Test writing a default setting adding an array to another that is already set
    The new array is in a different order than the existing one
    """
    write_value = ["a", 1]
    read_value = ["b", 1, "a", 2]
    expected = {
        "changes": {"written": f"com.apple.something Key is set to {write_value}"},
        "comment": "",
        "name": "Key",
        "result": True,
    }

    read_mock = MagicMock(return_value=read_value)
    write_mock = MagicMock(return_value={"retcode": 0})
    with patch.dict(
        macdefaults.__salt__,
        {"macdefaults.read": read_mock, "macdefaults.write": write_mock},
    ):
        out = macdefaults.write(
            "Key", "com.apple.something", write_value, vtype="array-add"
        )
        read_mock.assert_called_once_with("com.apple.something", "Key", None)
        write_mock.assert_called_once_with(
            "com.apple.something", "Key", write_value, "array-add", None
        )
        assert out == expected


def test_write_default_array_add_already_set_same_order():
    """
    Test writing a default setting adding an array to another that is already set
    The new array is already in the same order as the existing one
    """
    write_value = ["a", 1]
    read_value = ["b", "a", 1, 2]
    expected = {
        "changes": {},
        "comment": f"com.apple.something Key is already set to {write_value}",
        "name": "Key",
        "result": True,
    }

    read_mock = MagicMock(return_value=read_value)
    write_mock = MagicMock(return_value={"retcode": 0})
    with patch.dict(
        macdefaults.__salt__,
        {"macdefaults.read": read_mock, "macdefaults.write": write_mock},
    ):
        out = macdefaults.write(
            "Key", "com.apple.something", write_value, vtype="array-add"
        )
        read_mock.assert_called_once_with("com.apple.something", "Key", None)
        assert not write_mock.called
        assert out == expected


def test_write_default_dict():
    """
    Test writing a default setting with a dictionary
    """
    value = {"string": "bar", "integer": 1, "float": 0.5, "boolean": True}
    expected = {
        "changes": {"written": f"com.apple.something Key is set to {value}"},
        "comment": "",
        "name": "Key",
        "result": True,
    }

    read_mock = MagicMock(return_value=None)
    write_mock = MagicMock(return_value={"retcode": 0})
    with patch.dict(
        macdefaults.__salt__,
        {"macdefaults.read": read_mock, "macdefaults.write": write_mock},
    ):
        out = macdefaults.write("Key", "com.apple.something", value, vtype="dict")
        read_mock.assert_called_once_with("com.apple.something", "Key", None)
        write_mock.assert_called_once_with(
            "com.apple.something", "Key", value, "dict", None
        )
        assert out == expected


def test_write_default_dict_already_set():
    """
    Test writing a default setting with a dictionary that is already set
    """
    value = {"string": "bar", "integer": 1, "float": 0.5, "boolean": True}
    expected = {
        "changes": {},
        "comment": f"com.apple.something Key is already set to {value}",
        "name": "Key",
        "result": True,
    }

    read_mock = MagicMock(return_value=value)
    write_mock = MagicMock(return_value={"retcode": 0})
    with patch.dict(
        macdefaults.__salt__,
        {"macdefaults.read": read_mock, "macdefaults.write": write_mock},
    ):
        out = macdefaults.write("Key", "com.apple.something", value, vtype="dict")
        read_mock.assert_called_once_with("com.apple.something", "Key", None)
        assert not write_mock.called
        assert out == expected


def test_write_default_dict_add():
    """
    Test writing a default setting adding elements to a dictionary
    """
    write_value = {"string": "bar", "integer": 1}
    read_value = {"integer": 1, "float": 0.5, "boolean": True}
    expected = {
        "changes": {"written": f"com.apple.something Key is set to {write_value}"},
        "comment": "",
        "name": "Key",
        "result": True,
    }

    read_mock = MagicMock(return_value=read_value)
    write_mock = MagicMock(return_value={"retcode": 0})
    with patch.dict(
        macdefaults.__salt__,
        {"macdefaults.read": read_mock, "macdefaults.write": write_mock},
    ):
        out = macdefaults.write(
            "Key", "com.apple.something", write_value, vtype="dict-add"
        )
        read_mock.assert_called_once_with("com.apple.something", "Key", None)
        write_mock.assert_called_once_with(
            "com.apple.something", "Key", write_value, "dict-add", None
        )
        assert out == expected


def test_write_default_dict_add_already_set():
    """
    Test writing a default setting adding elements to a dictionary that is already set
    """
    write_value = {"string": "bar", "integer": 1}
    read_value = {"string": "bar", "integer": 1, "float": 0.5, "boolean": True}
    expected = {
        "changes": {},
        "comment": f"com.apple.something Key is already set to {write_value}",
        "name": "Key",
        "result": True,
    }

    read_mock = MagicMock(return_value=read_value)
    write_mock = MagicMock(return_value={"retcode": 0})
    with patch.dict(
        macdefaults.__salt__,
        {"macdefaults.read": read_mock, "macdefaults.write": write_mock},
    ):
        out = macdefaults.write(
            "Key", "com.apple.something", write_value, vtype="dict-add"
        )
        read_mock.assert_called_once_with("com.apple.something", "Key", None)
        assert not write_mock.called
        assert out == expected


def test_absent_default_already():
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


def test_absent_default_deleting_existing():
    """
    Test removing an existing default value
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
