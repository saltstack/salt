import pytest

import salt.modules.macdefaults as macdefaults
from tests.support.mock import MagicMock, call, patch


@pytest.fixture
def configure_loader_modules():
    return {macdefaults: {}}


def test_run_defaults_cmd():
    """
    Test caling _run_defaults_cmd
    """
    mock = MagicMock(return_value={"retcode": 0, "stdout": "Server", "stderr": ""})
    with patch.dict(macdefaults.__salt__, {"cmd.run_all": mock}):
        result = macdefaults._run_defaults_cmd(
            'read "com.apple.CrashReporter" "DialogType"'
        )
        mock.assert_called_once_with(
            'defaults read "com.apple.CrashReporter" "DialogType"', runas=None
        )
        assert result == {"retcode": 0, "stdout": "Server", "stderr": ""}


def test_run_defaults_cmd_with_user():
    """
    Test caling _run_defaults_cmd
    """
    mock = MagicMock(return_value={"retcode": 0, "stdout": "Server", "stderr": ""})
    with patch.dict(macdefaults.__salt__, {"cmd.run_all": mock}):
        result = macdefaults._run_defaults_cmd(
            'read "com.apple.CrashReporter" "DialogType"', runas="frank"
        )
        mock.assert_called_once_with(
            'defaults read "com.apple.CrashReporter" "DialogType"', runas="frank"
        )
        assert result == {"retcode": 0, "stdout": "Server", "stderr": ""}


def test_write_default():
    """
    Test writing a default setting
    """
    mock = MagicMock(return_value={"retcode": 0})
    with patch("salt.modules.macdefaults._run_defaults_cmd", mock):
        macdefaults.write("com.apple.CrashReporter", "DialogType", "Server")
        mock.assert_called_once_with(
            'write "com.apple.CrashReporter" "DialogType" -string "Server"',
            runas=None,
        )


def test_write_default_with_user():
    """
    Test writing a default setting with a specific user
    """
    mock = MagicMock(return_value={"retcode": 0})
    with patch("salt.modules.macdefaults._run_defaults_cmd", mock):
        macdefaults.write(
            "com.apple.CrashReporter", "DialogType", "Server", user="frank"
        )
        mock.assert_called_once_with(
            'write "com.apple.CrashReporter" "DialogType" -string "Server"',
            runas="frank",
        )


def test_write_default_true_boolean():
    """
    Test writing a default True boolean setting
    """
    mock = MagicMock(return_value={"retcode": 0})
    with patch("salt.modules.macdefaults._run_defaults_cmd", mock):
        macdefaults.write("com.apple.CrashReporter", "Crash", True, vtype="boolean")
        mock.assert_called_once_with(
            'write "com.apple.CrashReporter" "Crash" -boolean "TRUE"',
            runas=None,
        )


def test_write_default_false_bool():
    """
    Test writing a default False boolean setting
    """
    mock = MagicMock(return_value={"retcode": 0})
    with patch("salt.modules.macdefaults._run_defaults_cmd", mock):
        macdefaults.write("com.apple.CrashReporter", "Crash", False, vtype="bool")
        mock.assert_called_once_with(
            'write "com.apple.CrashReporter" "Crash" -bool "FALSE"',
            runas=None,
        )


def test_write_default_int():
    """
    Test writing a default int setting
    """
    mock = MagicMock(return_value={"retcode": 0})
    with patch("salt.modules.macdefaults._run_defaults_cmd", mock):
        macdefaults.write("com.apple.CrashReporter", "Crash", 1, vtype="int")
        mock.assert_called_once_with(
            'write "com.apple.CrashReporter" "Crash" -int 1',
            runas=None,
        )


def test_write_default_integer():
    """
    Test writing a default integer setting
    """
    mock = MagicMock(return_value={"retcode": 0})
    with patch("salt.modules.macdefaults._run_defaults_cmd", mock):
        macdefaults.write("com.apple.CrashReporter", "Crash", 1, vtype="integer")
        mock.assert_called_once_with(
            'write "com.apple.CrashReporter" "Crash" -integer 1',
            runas=None,
        )


def test_write_default_float():
    """
    Test writing a default float setting
    """
    mock = MagicMock(return_value={"retcode": 0})
    with patch("salt.modules.macdefaults._run_defaults_cmd", mock):
        macdefaults.write("com.apple.CrashReporter", "Crash", 0.85, vtype="float")
        mock.assert_called_once_with(
            'write "com.apple.CrashReporter" "Crash" -float 0.85',
            runas=None,
        )


def test_write_default_array():
    """
    Test writing a default array setting
    """
    mock = MagicMock(return_value={"retcode": 0})
    with patch("salt.modules.macdefaults._run_defaults_cmd", mock):
        macdefaults.write(
            "com.apple.CrashReporter", "Crash", [0.1, 0.2, 0.4], vtype="array"
        )
        mock.assert_called_once_with(
            'write "com.apple.CrashReporter" "Crash" -array 0.1 0.2 0.4',
            runas=None,
        )


def test_write_default_dictionary():
    """
    Test writing a default dictionary setting
    """
    mock = MagicMock(return_value={"retcode": 0})
    with patch("salt.modules.macdefaults._run_defaults_cmd", mock):
        macdefaults.write(
            "com.apple.CrashReporter", "Crash", {"foo": "bar", "baz": 0}, vtype="dict"
        )
        mock.assert_called_once_with(
            'write "com.apple.CrashReporter" "Crash" -dict "foo" "bar" "baz" 0',
            runas=None,
        )


def test_read_default():
    """
    Test reading a default setting
    """

    def custom_run_defaults_cmd(action, runas=None):
        if action == 'read-type "com.apple.CrashReporter" "Crash"':
            return {"retcode": 0, "stdout": "string"}
        elif action == 'read "com.apple.CrashReporter" "Crash"':
            return {"retcode": 0, "stdout": "Server"}
        return {"retcode": 1, "stderr": f"Unknown action: {action}", "stdout": ""}

    mock = MagicMock(side_effect=custom_run_defaults_cmd)
    with patch("salt.modules.macdefaults._run_defaults_cmd", mock):
        result = macdefaults.read("com.apple.CrashReporter", "Crash")
        mock.assert_has_calls(
            [
                call('read "com.apple.CrashReporter" "Crash"', runas=None),
                call('read-type "com.apple.CrashReporter" "Crash"', runas=None),
            ]
        )
        assert result == "Server"


def test_read_default_with_user():
    """
    Test reading a default setting as a specific user
    """

    def custom_run_defaults_cmd(action, runas=None):
        if action == 'read-type "com.apple.CrashReporter" "Crash"':
            return {"retcode": 0, "stdout": "string"}
        elif action == 'read "com.apple.CrashReporter" "Crash"':
            return {"retcode": 0, "stdout": "Server"}
        return {"retcode": 1, "stderr": f"Unknown action: {action}", "stdout": ""}

    mock = MagicMock(side_effect=custom_run_defaults_cmd)
    with patch("salt.modules.macdefaults._run_defaults_cmd", mock):
        result = macdefaults.read("com.apple.CrashReporter", "Crash", user="frank")
        mock.assert_has_calls(
            [
                call('read "com.apple.CrashReporter" "Crash"', runas="frank"),
                call('read-type "com.apple.CrashReporter" "Crash"', runas="frank"),
            ]
        )
        assert result == "Server"


def test_read_default_integer():
    """
    Test reading a default integer setting
    """

    def custom_run_defaults_cmd(action, runas=None):
        if action == 'read-type "com.apple.CrashReporter" "Crash"':
            return {"retcode": 0, "stdout": "integer"}
        elif action == 'read "com.apple.CrashReporter" "Crash"':
            return {"retcode": 0, "stdout": "12"}
        return {"retcode": 1, "stderr": f"Unknown action: {action}", "stdout": ""}

    mock = MagicMock(side_effect=custom_run_defaults_cmd)
    with patch("salt.modules.macdefaults._run_defaults_cmd", mock):
        result = macdefaults.read("com.apple.CrashReporter", "Crash")
        mock.assert_has_calls(
            [
                call('read "com.apple.CrashReporter" "Crash"', runas=None),
                call('read-type "com.apple.CrashReporter" "Crash"', runas=None),
            ]
        )
        assert result == 12


def test_read_default_float():
    """
    Test reading a default float setting
    """

    def custom_run_defaults_cmd(action, runas=None):
        if action == 'read-type "com.apple.CrashReporter" "Crash"':
            return {"retcode": 0, "stdout": "float"}
        elif action == 'read "com.apple.CrashReporter" "Crash"':
            return {"retcode": 0, "stdout": "0.85"}
        return {"retcode": 1, "stderr": f"Unknown action: {action}", "stdout": ""}

    mock = MagicMock(side_effect=custom_run_defaults_cmd)
    with patch("salt.modules.macdefaults._run_defaults_cmd", mock):
        result = macdefaults.read("com.apple.CrashReporter", "Crash")
        mock.assert_has_calls(
            [
                call('read "com.apple.CrashReporter" "Crash"', runas=None),
                call('read-type "com.apple.CrashReporter" "Crash"', runas=None),
            ]
        )
        assert result == 0.85


def test_read_default_array():
    """
    Test reading a default array setting
    """

    defaults_output = """(
        element 1,
        element 2,
        0.1000,
        1
    )"""

    def custom_run_defaults_cmd(action, runas=None):
        if action == 'read-type "com.apple.CrashReporter" "Crash"':
            return {"retcode": 0, "stdout": "array"}
        elif action == 'read "com.apple.CrashReporter" "Crash"':
            return {"retcode": 0, "stdout": defaults_output}
        return {"retcode": 1, "stderr": f"Unknown action: {action}", "stdout": ""}

    mock = MagicMock(side_effect=custom_run_defaults_cmd)
    with patch("salt.modules.macdefaults._run_defaults_cmd", mock):
        result = macdefaults.read("com.apple.CrashReporter", "Crash")
        mock.assert_has_calls(
            [
                call('read "com.apple.CrashReporter" "Crash"', runas=None),
                call('read-type "com.apple.CrashReporter" "Crash"', runas=None),
            ]
        )
        assert result == ["element 1", "element 2", 0.1, 1]


def test_read_default_dictionary():
    """
    Test reading a default dictionary setting
    """

    defaults_output = """{
        keyCode = 36;
        modifierFlags = 786432;
        anotherKey = "another value with spaces";
        floatNumber = 0.8500;
    }"""

    def custom_run_defaults_cmd(action, runas=None):
        if action == 'read-type "com.apple.CrashReporter" "Crash"':
            return {"retcode": 0, "stdout": "dictionary"}
        elif action == 'read "com.apple.CrashReporter" "Crash"':
            return {"retcode": 0, "stdout": defaults_output}
        return {"retcode": 1, "stderr": f"Unknown action: {action}", "stdout": ""}

    mock = MagicMock(side_effect=custom_run_defaults_cmd)
    with patch("salt.modules.macdefaults._run_defaults_cmd", mock):
        result = macdefaults.read("com.apple.CrashReporter", "Crash")
        mock.assert_has_calls(
            [
                call('read "com.apple.CrashReporter" "Crash"', runas=None),
                call('read-type "com.apple.CrashReporter" "Crash"', runas=None),
            ]
        )
        assert result == {
            "keyCode": 36,
            "modifierFlags": 786432,
            "anotherKey": "another value with spaces",
            "floatNumber": 0.85,
        }


def test_delete_default():
    """
    Test delete a default setting
    """
    mock = MagicMock(return_value={"retcode": 0})
    with patch("salt.modules.macdefaults._run_defaults_cmd", mock):
        macdefaults.delete("com.apple.CrashReporter", "Crash")
        mock.assert_called_once_with(
            'delete "com.apple.CrashReporter" "Crash"',
            runas=None,
        )


def test_delete_default_with_user():
    """
    Test delete a default setting as a specific user
    """
    mock = MagicMock(return_value={"retcode": 0})
    with patch("salt.modules.macdefaults._run_defaults_cmd", mock):
        macdefaults.delete("com.apple.CrashReporter", "Crash", user="frank")
        mock.assert_called_once_with(
            'delete "com.apple.CrashReporter" "Crash"',
            runas="frank",
        )
