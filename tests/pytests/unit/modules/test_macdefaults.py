import tempfile
from datetime import datetime

import pytest

import salt.modules.file
import salt.modules.macdefaults as macdefaults
from tests.support.mock import ANY, MagicMock, call, patch


@pytest.fixture
def configure_loader_modules():
    return {macdefaults: {}}


@pytest.fixture
def PLIST_OUTPUT():
    return """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>AdjustWindowForFontSizeChange</key>
	<false/>
	<key>AllowClipboardAccess</key>
	<true/>
	<key>AppleAntiAliasingThreshold</key>
	<integer>1024</integer>
	<key>Default Bookmark Guid</key>
	<string>C7EED71F-6B5F-4822-B735-D20CAE8AD57D</string>
	<key>NSNavPanelExpandedSizeForOpenMode</key>
	<string>{800, 448}</string>
	<key>NSSplitView Subview Frames NSColorPanelSplitView</key>
	<array>
		<string>0.000000, 0.000000, 224.000000, 222.000000, NO, NO</string>
		<string>0.000000, 223.000000, 224.000000, 48.000000, NO, NO</string>
	</array>
	<key>NSToolbar Configuration com.apple.NSColorPanel</key>
	<dict>
		<key>TB Is Shown</key>
		<integer>1</integer>
	</dict>
	<key>NeverWarnAboutShortLivedSessions_C7EED71F-6B5F-4822-B735-D20CAE8AD57D_selection</key>
	<integer>0</integer>
	<key>NoSyncBFPRecents</key>
	<array>
		<string>MonoLisa Variable</string>
		<string>Menlo</string>
		<string>MonoLisa</string>
	</array>
	<key>NoSyncFrame_SharedPreferences</key>
	<dict>
		<key>screenFrame</key>
		<string>{{0, 0}, {1920, 1200}}</string>
		<key>topLeft</key>
		<string>{668, 1004}</string>
	</dict>
	<key>NoSyncNextAnnoyanceTime</key>
	<real>699041775.9120981</real>
	<key>NoSyncTipOfTheDayEligibilityBeganTime</key>
	<real>697356008.723986</real>
	<key>PointerActions</key>
	<dict>
		<key>Button,1,1,,</key>
		<dict>
			<key>Action</key>
			<string>kContextMenuPointerAction</string>
		</dict>
		<key>Button,2,1,,</key>
		<dict>
			<key>Action</key>
			<string>kPasteFromSelectionPointerAction</string>
		</dict>
	</dict>
	<key>SULastCheckTime</key>
	<date>2024-06-23T09:33:44Z</date>
</dict>
</plist>
"""


def test_run_defaults_cmd():
    """
    Test calling _run_defaults_cmd
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


def test_load_plist(PLIST_OUTPUT):
    """
    Test loading a plist
    """
    expected_result = {"Crash": "Server"}
    run_defaults_cmd_mock = MagicMock(
        return_value={"retcode": 0, "stdout": PLIST_OUTPUT, "stderr": ""}
    )

    with patch(
        "salt.modules.macdefaults._run_defaults_cmd", run_defaults_cmd_mock
    ), patch("plistlib.loads", return_value=expected_result) as plist_mock:
        result = macdefaults._load_plist("com.googlecode.iterm2")
        run_defaults_cmd_mock.assert_called_once_with(
            'export "com.googlecode.iterm2" -', runas=None
        )
        plist_mock.assert_called_once_with(PLIST_OUTPUT.encode())
        assert result == expected_result


def test_load_plist_no_domain():
    """
    Test loading a plist with a non-existent domain
    """
    empty_plist = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict/>
</plist>"""

    run_defaults_cmd_mock = MagicMock(
        return_value={"retcode": 0, "stdout": empty_plist, "stderr": ""}
    )

    with patch("salt.modules.macdefaults._run_defaults_cmd", run_defaults_cmd_mock):
        result = macdefaults._load_plist("com.googlecode.iterm2", user="cdalvaro")
        run_defaults_cmd_mock.assert_called_once_with(
            'export "com.googlecode.iterm2" -', runas="cdalvaro"
        )
        assert result is None


def test_save_plist_no_user():
    """
    Test saving a plist
    """
    new_plist = {"Crash": "Server"}
    expected_result = {"retcode": 0, "stdout": "", "stderr": ""}

    chown_mock = MagicMock()

    tempdir = tempfile.TemporaryDirectory()
    tempdir_name = tempdir.name

    tempfile_mock = MagicMock()
    tempfile_mock.__enter__.return_value = tempdir_name

    domain = "com.googlecode.iterm2"
    tmp_file_name = salt.modules.file.join(tempdir_name, f"{domain}.plist")

    with patch(
        "salt.modules.macdefaults._run_defaults_cmd", return_value=expected_result
    ) as run_defaults_cmd_mock, patch(
        "tempfile.TemporaryDirectory", return_value=tempfile_mock
    ), patch(
        "plistlib.dump"
    ) as plist_mock, patch.dict(
        macdefaults.__salt__,
        {"file.chown": chown_mock, "file.join": salt.modules.file.join},
    ):
        result = macdefaults._save_plist("com.googlecode.iterm2", new_plist)
        assert result == expected_result

        plist_mock.assert_called_once_with(new_plist, ANY)  # ANY for filehandler
        run_defaults_cmd_mock.assert_called_once_with(
            f'import "{domain}" "{tmp_file_name}"',
            runas=None,
        )
        chown_mock.assert_not_called()


def test_save_plist_with_user():
    """
    Test saving a plist
    """
    new_plist = {"Crash": "Server"}
    expected_result = {"retcode": 0, "stdout": "", "stderr": ""}

    chown_mock = MagicMock()

    tempdir = tempfile.TemporaryDirectory()
    tempdir_name = tempdir.name

    tempfile_mock = MagicMock()
    tempfile_mock.__enter__.return_value = tempdir_name

    user = "cdalvaro"
    domain = "com.googlecode.iterm2"
    tmp_file_name = salt.modules.file.join(tempdir_name, f"{domain}.plist")

    chown_expected_calls = [
        call(tempdir_name, user, None),
        call(tmp_file_name, user, None),
    ]

    with patch(
        "salt.modules.macdefaults._run_defaults_cmd", return_value=expected_result
    ) as run_defaults_cmd_mock, patch(
        "tempfile.TemporaryDirectory", return_value=tempfile_mock
    ), patch(
        "plistlib.dump"
    ) as plist_mock, patch.dict(
        macdefaults.__salt__,
        {"file.chown": chown_mock, "file.join": salt.modules.file.join},
    ):
        result = macdefaults._save_plist("com.googlecode.iterm2", new_plist, user=user)
        assert result == expected_result

        plist_mock.assert_called_once_with(new_plist, ANY)  # ANY for filehandler
        run_defaults_cmd_mock.assert_called_once_with(
            f'import "{domain}" "{tmp_file_name}"',
            runas=user,
        )
        chown_mock.assert_has_calls(chown_expected_calls)


def test_cast_value_to_bool():
    assert macdefaults.cast_value_to_vtype("TRUE", "bool") is True
    assert macdefaults.cast_value_to_vtype("YES", "bool") is True
    assert macdefaults.cast_value_to_vtype("1", "bool") is True
    assert macdefaults.cast_value_to_vtype(1, "bool") is True

    assert macdefaults.cast_value_to_vtype("FALSE", "boolean") is False
    assert macdefaults.cast_value_to_vtype("NO", "boolean") is False
    assert macdefaults.cast_value_to_vtype("0", "boolean") is False
    assert macdefaults.cast_value_to_vtype(0, "boolean") is False

    with pytest.raises(ValueError):
        macdefaults.cast_value_to_vtype("foo", "bool")

    with pytest.raises(ValueError):
        macdefaults.cast_value_to_vtype(1.1, "bool")


def test_cast_value_to_string():
    assert macdefaults.cast_value_to_vtype(124.120, "string") == "124.12"
    assert macdefaults.cast_value_to_vtype(True, "string") == "YES"
    assert macdefaults.cast_value_to_vtype(False, "string") == "NO"
    assert macdefaults.cast_value_to_vtype(124120, "string") == "124120"

    expected_date = "2024-06-26T16:45:05Z"
    test_date = datetime.strptime(expected_date, "%Y-%m-%dT%H:%M:%SZ")
    assert macdefaults.cast_value_to_vtype(test_date, "string") == expected_date

    expected_data = "foo"
    test_data = expected_data.encode()
    assert macdefaults.cast_value_to_vtype(test_data, "string") == expected_data


def test_cast_value_to_int():
    assert macdefaults.cast_value_to_vtype("124", "int") == 124
    assert macdefaults.cast_value_to_vtype(124.0, "int") == 124
    assert macdefaults.cast_value_to_vtype(True, "integer") == 1
    assert macdefaults.cast_value_to_vtype(False, "integer") == 0

    with pytest.raises(ValueError):
        macdefaults.cast_value_to_vtype("foo", "int")


def test_cast_value_to_float():
    assert macdefaults.cast_value_to_vtype("124.12", "float") == 124.12
    assert macdefaults.cast_value_to_vtype(124, "float") == 124.0
    assert macdefaults.cast_value_to_vtype(True, "float") == 1.0
    assert macdefaults.cast_value_to_vtype(False, "float") == 0.0

    with pytest.raises(ValueError):
        macdefaults.cast_value_to_vtype("foo", "float")


def test_cast_value_to_date():
    expected_date = datetime(2024, 6, 26, 16, 45, 5)

    # Date -> Date
    assert macdefaults.cast_value_to_vtype(expected_date, "date") == expected_date

    # String -> Date
    test_date = datetime.strftime(expected_date, "%Y-%m-%dT%H:%M:%SZ")
    assert macdefaults.cast_value_to_vtype(test_date, "date") == expected_date

    # Timestamp -> Date
    test_timestamp = expected_date.timestamp()
    assert macdefaults.cast_value_to_vtype(test_timestamp, "date") == expected_date

    with pytest.raises(ValueError):
        macdefaults.cast_value_to_vtype("foo", "date")


def test_cast_value_to_data():
    expected_data = b"foo"

    # String -> Data
    test_data = expected_data.decode()
    assert macdefaults.cast_value_to_vtype(test_data, "data") == expected_data

    # Data -> Data
    assert macdefaults.cast_value_to_vtype(expected_data, "data") == expected_data

    with pytest.raises(ValueError):
        macdefaults.cast_value_to_vtype(123, "data")


def test_write_default():
    """
    Test writing a default setting
    """
    with patch("salt.modules.macdefaults._load_plist", return_value={}), patch(
        "salt.modules.macdefaults._save_plist", return_value={"retcode": 0}
    ) as save_plist_mock:
        macdefaults.write("com.apple.CrashReporter", "DialogType", "Server")
        save_plist_mock.assert_called_once_with(
            "com.apple.CrashReporter",
            {"DialogType": "Server"},
            user=None,
        )


def test_write_default_with_user():
    """
    Test writing a default setting with a specific user
    """
    with patch("salt.modules.macdefaults._load_plist", return_value={}), patch(
        "salt.modules.macdefaults._save_plist", return_value={"retcode": 0}
    ) as save_plist_mock:
        macdefaults.write(
            "com.apple.CrashReporter", "DialogType", "Server", user="cdalvaro"
        )
        save_plist_mock.assert_called_once_with(
            "com.apple.CrashReporter",
            {"DialogType": "Server"},
            user="cdalvaro",
        )


def test_write_default_true_boolean():
    """
    Test writing a default True boolean setting
    """
    with patch(
        "salt.modules.macdefaults._load_plist", return_value={"Crash": False}
    ), patch(
        "salt.modules.macdefaults._save_plist", return_value={"retcode": 0}
    ) as save_plist_mock:
        macdefaults.write("com.apple.CrashReporter", "Crash", True)
        save_plist_mock.assert_called_once_with(
            "com.apple.CrashReporter",
            {"Crash": True},
            user=None,
        )

    with patch(
        "salt.modules.macdefaults._load_plist", return_value={"Crash": False}
    ), patch(
        "salt.modules.macdefaults._save_plist", return_value={"retcode": 0}
    ) as save_plist_mock:
        macdefaults.write("com.apple.CrashReporter", "Crash", "YES", vtype="boolean")
        save_plist_mock.assert_called_once_with(
            "com.apple.CrashReporter",
            {"Crash": True},
            user=None,
        )


def test_write_default_false_bool():
    """
    Test writing a default False boolean setting
    """
    with patch(
        "salt.modules.macdefaults._load_plist", return_value={"Crash": True}
    ), patch(
        "salt.modules.macdefaults._save_plist", return_value={"retcode": 0}
    ) as save_plist_mock:
        macdefaults.write("com.apple.CrashReporter", "Crash", False)
        save_plist_mock.assert_called_once_with(
            "com.apple.CrashReporter",
            {"Crash": False},
            user=None,
        )

    with patch(
        "salt.modules.macdefaults._load_plist", return_value={"Crash": True}
    ), patch(
        "salt.modules.macdefaults._save_plist", return_value={"retcode": 0}
    ) as save_plist_mock:
        macdefaults.write("com.apple.CrashReporter", "Crash", "NO", vtype="bool")
        save_plist_mock.assert_called_once_with(
            "com.apple.CrashReporter",
            {"Crash": False},
            user=None,
        )


def test_write_default_int():
    """
    Test writing a default int setting
    """
    with patch(
        "salt.modules.macdefaults._load_plist", return_value={"Crash": 0}
    ), patch(
        "salt.modules.macdefaults._save_plist", return_value={"retcode": 0}
    ) as save_plist_mock:
        macdefaults.write("com.apple.CrashReporter", "Crash", 1)
        save_plist_mock.assert_called_once_with(
            "com.apple.CrashReporter",
            {"Crash": 1},
            user=None,
        )

    with patch(
        "salt.modules.macdefaults._load_plist", return_value={"Crash": 3}
    ), patch(
        "salt.modules.macdefaults._save_plist", return_value={"retcode": 0}
    ) as save_plist_mock:
        macdefaults.write("com.apple.CrashReporter", "Crash", "3", vtype="int")
        save_plist_mock.assert_called_once_with(
            "com.apple.CrashReporter",
            {"Crash": 3},
            user=None,
        )

    with patch(
        "salt.modules.macdefaults._load_plist", return_value={"Crash": 0}
    ), patch(
        "salt.modules.macdefaults._save_plist", return_value={"retcode": 0}
    ) as save_plist_mock:
        macdefaults.write("com.apple.CrashReporter", "Crash", "15", vtype="integer")
        save_plist_mock.assert_called_once_with(
            "com.apple.CrashReporter",
            {"Crash": 15},
            user=None,
        )


def test_write_default_float():
    """
    Test writing a default float setting
    """
    with patch(
        "salt.modules.macdefaults._load_plist", return_value={"Crash": 0}
    ), patch(
        "salt.modules.macdefaults._save_plist", return_value={"retcode": 0}
    ) as save_plist_mock:
        macdefaults.write("com.apple.CrashReporter", "Crash", 1.234)
        save_plist_mock.assert_called_once_with(
            "com.apple.CrashReporter",
            {"Crash": 1.234},
            user=None,
        )

    with patch(
        "salt.modules.macdefaults._load_plist", return_value={"Crash": 0}
    ), patch(
        "salt.modules.macdefaults._save_plist", return_value={"retcode": 0}
    ) as save_plist_mock:
        macdefaults.write("com.apple.CrashReporter", "Crash", "14.350", vtype="float")
        save_plist_mock.assert_called_once_with(
            "com.apple.CrashReporter",
            {"Crash": 14.35},
            user=None,
        )


def test_write_default_array():
    """
    Test writing a default array setting
    """

    # Key does not exist
    with patch("salt.modules.macdefaults._load_plist", return_value={}), patch(
        "salt.modules.macdefaults._save_plist", return_value={"retcode": 0}
    ) as save_plist_mock:
        macdefaults.write("com.apple.CrashReporter", "Crash", [0.7, 0.9, 1.0])
        save_plist_mock.assert_called_once_with(
            "com.apple.CrashReporter",
            {"Crash": [0.7, 0.9, 1.0]},
            user=None,
        )

    # Key already exists with different values
    with patch(
        "salt.modules.macdefaults._load_plist", return_value={"Crash": [0.1, 0.2, 0.4]}
    ), patch(
        "salt.modules.macdefaults._save_plist", return_value={"retcode": 0}
    ) as save_plist_mock:
        macdefaults.write("com.apple.CrashReporter", "Crash", [0.7, 0.9, 1.0])
        save_plist_mock.assert_called_once_with(
            "com.apple.CrashReporter",
            {"Crash": [0.7, 0.9, 1.0]},
            user=None,
        )

    # Array already exists and the new value (float) is appended
    with patch(
        "salt.modules.macdefaults._load_plist", return_value={"Crash": [0.1, 0.2, 0.4]}
    ), patch(
        "salt.modules.macdefaults._save_plist", return_value={"retcode": 0}
    ) as save_plist_mock:
        macdefaults.write(
            "com.apple.CrashReporter", "Crash", "0.5", vtype="float", array_add=True
        )
        save_plist_mock.assert_called_once_with(
            "com.apple.CrashReporter",
            {"Crash": [0.1, 0.2, 0.4, 0.5]},
            user=None,
        )

    # Array already exists and the new value (array) is appended (using array_add=True)
    with patch(
        "salt.modules.macdefaults._load_plist", return_value={"Crash": [0.1, 0.2, 0.4]}
    ), patch(
        "salt.modules.macdefaults._save_plist", return_value={"retcode": 0}
    ) as save_plist_mock:
        macdefaults.write(
            "com.apple.CrashReporter", "Crash", [2.0, 4.0], array_add=True
        )
        save_plist_mock.assert_called_once_with(
            "com.apple.CrashReporter",
            {"Crash": [0.1, 0.2, 0.4, 2.0, 4.0]},
            user=None,
        )

    # Array already exists and the new value (array) is appended (using vtype="array-add")
    with patch(
        "salt.modules.macdefaults._load_plist", return_value={"Crash": [0.1, 0.2, 0.4]}
    ), patch(
        "salt.modules.macdefaults._save_plist", return_value={"retcode": 0}
    ) as save_plist_mock:
        macdefaults.write(
            "com.apple.CrashReporter", "Crash", [2.0, 4.0], vtype="array-add"
        )
        save_plist_mock.assert_called_once_with(
            "com.apple.CrashReporter",
            {"Crash": [0.1, 0.2, 0.4, 2.0, 4.0]},
            user=None,
        )

    with patch(
        "salt.modules.macdefaults._load_plist", return_value={"Crash": [0.1, 0.2, 0.4]}
    ), patch(
        "salt.modules.macdefaults._save_plist", return_value={"retcode": 0}
    ) as save_plist_mock, pytest.raises(
        ValueError
    ) as excinfo:
        macdefaults.write("com.apple.CrashReporter", "Crash", "0.5", vtype="array")
        save_plist_mock.assert_not_called()
        excinfo.match("Invalid value for array")


def test_write_default_dictionary():
    """
    Test writing a default dictionary setting
    """

    # Key does not exist
    with patch("salt.modules.macdefaults._load_plist", return_value={}), patch(
        "salt.modules.macdefaults._save_plist", return_value={"retcode": 0}
    ) as save_plist_mock:
        macdefaults.write("com.apple.CrashReporter", "Crash", {"foo:": "bar", "baz": 0})
        save_plist_mock.assert_called_once_with(
            "com.apple.CrashReporter",
            {"Crash": {"foo:": "bar", "baz": 0}},
            user=None,
        )

    # Key already exists with different values
    with patch(
        "salt.modules.macdefaults._load_plist", return_value={"Crash": {"foo": "bar"}}
    ), patch(
        "salt.modules.macdefaults._save_plist", return_value={"retcode": 0}
    ) as save_plist_mock:
        macdefaults.write("com.apple.CrashReporter", "Crash", {"baz": 1})
        save_plist_mock.assert_called_once_with(
            "com.apple.CrashReporter",
            {"Crash": {"baz": 1}},
            user=None,
        )

    # Dictionary already exists and the new value is merged (using dict_merge=True)
    with patch(
        "salt.modules.macdefaults._load_plist", return_value={"Crash": {"foo": "bar"}}
    ), patch(
        "salt.modules.macdefaults._save_plist", return_value={"retcode": 0}
    ) as save_plist_mock:
        macdefaults.write(
            "com.apple.CrashReporter", "Crash", {"baz": 10}, dict_merge=True
        )
        save_plist_mock.assert_called_once_with(
            "com.apple.CrashReporter",
            {"Crash": {"foo": "bar", "baz": 10}},
            user=None,
        )

    # Dictionary already exists and the new value is merged (using vtype="dict-add")
    with patch(
        "salt.modules.macdefaults._load_plist", return_value={"Crash": {"foo": "bar"}}
    ), patch(
        "salt.modules.macdefaults._save_plist", return_value={"retcode": 0}
    ) as save_plist_mock:
        macdefaults.write(
            "com.apple.CrashReporter", "Crash", {"baz": 10}, vtype="dict-add"
        )
        save_plist_mock.assert_called_once_with(
            "com.apple.CrashReporter",
            {"Crash": {"foo": "bar", "baz": 10}},
            user=None,
        )

    with patch(
        "salt.modules.macdefaults._load_plist", return_value={"Crash": {}}
    ), patch(
        "salt.modules.macdefaults._save_plist", return_value={"retcode": 0}
    ) as save_plist_mock, pytest.raises(
        ValueError
    ) as excinfo:
        macdefaults.write("com.apple.CrashReporter", "Crash", "0.5", vtype="dict")
        save_plist_mock.assert_not_called()
        excinfo.match("Invalid value for dictionary")


def test_read_default_string(PLIST_OUTPUT):
    """
    Test reading a default string setting
    """

    def custom_run_defaults_cmd(action, runas):
        return {"retcode": 0, "stdout": PLIST_OUTPUT}

    mock = MagicMock(side_effect=custom_run_defaults_cmd)
    with patch("salt.modules.macdefaults._run_defaults_cmd", mock):
        result = macdefaults.read("com.googlecode.iterm2", "Default Bookmark Guid")
        mock.assert_called_once_with('export "com.googlecode.iterm2" -', runas=None)
        assert result == "C7EED71F-6B5F-4822-B735-D20CAE8AD57D"


def test_read_default_string_with_user(PLIST_OUTPUT):
    """
    Test reading a default string setting as a specific user
    """

    def custom_run_defaults_cmd(action, runas):
        return {"retcode": 0, "stdout": PLIST_OUTPUT}

    mock = MagicMock(side_effect=custom_run_defaults_cmd)
    with patch("salt.modules.macdefaults._run_defaults_cmd", mock):
        result = macdefaults.read(
            "com.googlecode.iterm2", "NSNavPanelExpandedSizeForOpenMode", user="frank"
        )
        mock.assert_called_once_with('export "com.googlecode.iterm2" -', runas="frank")
        assert result == "{800, 448}"


def test_read_default_integer(PLIST_OUTPUT):
    """
    Test reading a default integer setting
    """

    def custom_run_defaults_cmd(action, runas):
        return {"retcode": 0, "stdout": PLIST_OUTPUT}

    mock = MagicMock(side_effect=custom_run_defaults_cmd)
    with patch("salt.modules.macdefaults._run_defaults_cmd", mock):
        result = macdefaults.read("com.googlecode.iterm2", "AppleAntiAliasingThreshold")
        mock.assert_called_once_with('export "com.googlecode.iterm2" -', runas=None)
        assert result == 1024


def test_read_default_float(PLIST_OUTPUT):
    """
    Test reading a default float setting
    """

    def custom_run_defaults_cmd(action, runas):
        return {"retcode": 0, "stdout": PLIST_OUTPUT}

    mock = MagicMock(side_effect=custom_run_defaults_cmd)
    with patch("salt.modules.macdefaults._run_defaults_cmd", mock):
        result = macdefaults.read("com.googlecode.iterm2", "NoSyncNextAnnoyanceTime")
        mock.assert_called_once_with('export "com.googlecode.iterm2" -', runas=None)
        assert result == 699041775.9120981


def test_read_default_array(PLIST_OUTPUT):
    """
    Test reading a default array setting
    """

    def custom_run_defaults_cmd(action, runas):
        return {"retcode": 0, "stdout": PLIST_OUTPUT}

    mock = MagicMock(side_effect=custom_run_defaults_cmd)
    with patch("salt.modules.macdefaults._run_defaults_cmd", mock):
        result = macdefaults.read("com.googlecode.iterm2", "NoSyncBFPRecents")
        mock.assert_called_once_with('export "com.googlecode.iterm2" -', runas=None)
        assert result == ["MonoLisa Variable", "Menlo", "MonoLisa"]


def test_read_default_dictionary(PLIST_OUTPUT):
    """
    Test reading a default dictionary setting
    """

    def custom_run_defaults_cmd(action, runas):
        return {"retcode": 0, "stdout": PLIST_OUTPUT}

    mock = MagicMock(side_effect=custom_run_defaults_cmd)
    with patch("salt.modules.macdefaults._run_defaults_cmd", mock):
        result = macdefaults.read(
            "com.googlecode.iterm2", "NoSyncFrame_SharedPreferences"
        )
        mock.assert_called_once_with('export "com.googlecode.iterm2" -', runas=None)
        assert result == {
            "screenFrame": "{{0, 0}, {1920, 1200}}",
            "topLeft": "{668, 1004}",
        }


def test_read_default_dictionary_nested_key(PLIST_OUTPUT):
    """
    Test reading a default dictionary setting with a nested key
    """

    def custom_run_defaults_cmd(action, runas):
        return {"retcode": 0, "stdout": PLIST_OUTPUT}

    mock = MagicMock(side_effect=custom_run_defaults_cmd)
    with patch("salt.modules.macdefaults._run_defaults_cmd", mock):
        result = macdefaults.read(
            "com.googlecode.iterm2",
            "PointerActions.Button,1,1,,.Action",
            key_separator=".",
        )
        mock.assert_called_once_with('export "com.googlecode.iterm2" -', runas=None)
        assert result == "kContextMenuPointerAction"


def test_read_default_dictionary_nested_key_with_array_indexes(PLIST_OUTPUT):
    """
    Test reading a default dictionary setting with a nested key and array indexes
    """

    def custom_run_defaults_cmd(action, runas):
        return {"retcode": 0, "stdout": PLIST_OUTPUT}

    mock = MagicMock(side_effect=custom_run_defaults_cmd)
    with patch("salt.modules.macdefaults._run_defaults_cmd", mock):
        # First index (exists)
        result = macdefaults.read(
            "com.googlecode.iterm2",
            "NSSplitView Subview Frames NSColorPanelSplitView.0",
            key_separator=".",
        )
        mock.assert_called_once_with('export "com.googlecode.iterm2" -', runas=None)
        assert result == "0.000000, 0.000000, 224.000000, 222.000000, NO, NO"

        # Second index (exists)
        result = macdefaults.read(
            "com.googlecode.iterm2",
            "NSSplitView Subview Frames NSColorPanelSplitView.1",
            key_separator=".",
        )
        assert result == "0.000000, 223.000000, 224.000000, 48.000000, NO, NO"

        # Third index (does not exist)
        result = macdefaults.read(
            "com.googlecode.iterm2",
            "NSSplitView Subview Frames NSColorPanelSplitView.2",
            key_separator=".",
        )
        assert result is None


def test_read_default_date(PLIST_OUTPUT):
    """
    Test reading a default date setting
    """

    def custom_run_defaults_cmd(action, runas):
        return {"retcode": 0, "stdout": PLIST_OUTPUT}

    mock = MagicMock(side_effect=custom_run_defaults_cmd)
    with patch("salt.modules.macdefaults._run_defaults_cmd", mock):
        result = macdefaults.read("com.googlecode.iterm2", "SULastCheckTime")
        mock.assert_called_once_with('export "com.googlecode.iterm2" -', runas=None)
        assert result == datetime.strptime("2024-06-23T09:33:44Z", "%Y-%m-%dT%H:%M:%SZ")


def test_delete_default():
    """
    Test delete a default setting
    """
    original_plist = {
        "Crash": "bar",
        "foo": 0,
    }

    updated_plist = {
        "foo": 0,
    }

    result = {"retcode": 0, "stdout": "Removed key", "stderr": ""}

    load_plist_mock = MagicMock(return_value=original_plist)
    export_plist_mock = MagicMock(return_value=result)

    with patch("salt.modules.macdefaults._load_plist", load_plist_mock), patch(
        "salt.modules.macdefaults._save_plist", export_plist_mock
    ):
        assert result == macdefaults.delete("com.apple.CrashReporter", "Crash")
        load_plist_mock.assert_called_once_with(
            "com.apple.CrashReporter",
            user=None,
        )
        export_plist_mock.assert_called_once_with(
            "com.apple.CrashReporter",
            updated_plist,
            user=None,
        )


def test_delete_default_with_user():
    """
    Test delete a default setting as a specific user
    """
    original_plist = {
        "Crash": {
            "foo": "bar",
            "baz": 0,
        },
        "Crash.baz": 0,
    }

    updated_plist = {
        "Crash": {
            "foo": "bar",
            "baz": 0,
        },
    }

    result = {"retcode": 0, "stdout": "Removed key", "stderr": ""}

    load_plist_mock = MagicMock(return_value=original_plist)
    export_plist_mock = MagicMock(return_value=result)

    with patch("salt.modules.macdefaults._load_plist", load_plist_mock), patch(
        "salt.modules.macdefaults._save_plist", export_plist_mock
    ):
        macdefaults.delete("com.apple.CrashReporter", "Crash.baz", user="frank")
        load_plist_mock.assert_called_once_with(
            "com.apple.CrashReporter",
            user="frank",
        )
        export_plist_mock.assert_called_once_with(
            "com.apple.CrashReporter",
            updated_plist,
            user="frank",
        )


def test_delete_default_with_nested_key():
    """
    Test delete a default setting with a nested key
    """
    original_plist = {
        "Crash": {
            "foo": "bar",
            "baz": 0,
        }
    }

    updated_plist = {
        "Crash": {
            "foo": "bar",
        }
    }

    result = {"retcode": 0, "stdout": "Removed key", "stderr": ""}

    load_plist_mock = MagicMock(return_value=original_plist)
    export_plist_mock = MagicMock(return_value=result)

    with patch("salt.modules.macdefaults._load_plist", load_plist_mock), patch(
        "salt.modules.macdefaults._save_plist", export_plist_mock
    ):
        assert result == macdefaults.delete(
            "com.apple.CrashReporter",
            "Crash.baz",
            key_separator=".",
        )
        load_plist_mock.assert_called_once_with(
            "com.apple.CrashReporter",
            user=None,
        )
        export_plist_mock.assert_called_once_with(
            "com.apple.CrashReporter",
            updated_plist,
            user=None,
        )


def test_delete_default_dictionary_nested_key_with_array_indexes():
    """
    Test delete a default dictionary setting with a nested key and array indexes
    """
    original_plist = {
        "Crash": {
            "foo": "bar",
            "baz": [
                {"internalKey1": 1, "internalKey2": "a"},
                {"internalKey1": 2, "internalKey2": "b"},
                {"internalKey1": 3, "internalKey2": "c"},
            ],
        }
    }

    updated_plist = {
        "Crash": {
            "foo": "bar",
            "baz": [
                {"internalKey1": 1, "internalKey2": "a"},
                {"internalKey2": "b"},
                {"internalKey1": 3, "internalKey2": "c"},
            ],
        }
    }

    result = {"retcode": 0, "stdout": "Removed key", "stderr": ""}

    load_plist_mock = MagicMock(return_value=original_plist)
    export_plist_mock = MagicMock(return_value=result)

    with patch("salt.modules.macdefaults._load_plist", load_plist_mock), patch(
        "salt.modules.macdefaults._save_plist", export_plist_mock
    ):
        assert result == macdefaults.delete(
            "com.apple.CrashReporter",
            "Crash.baz.1.internalKey1",
            key_separator=".",
        )
        load_plist_mock.assert_called_once_with(
            "com.apple.CrashReporter",
            user=None,
        )
        export_plist_mock.assert_called_once_with(
            "com.apple.CrashReporter",
            updated_plist,
            user=None,
        )


def test_delete_default_dictionary_nested_key_with_array_index_as_last_key():
    """
    Test delete a default dictionary setting with a nested key and array indexes
    and the last element of the key is an array index
    """
    original_plist = {
        "Crash": {
            "foo": "bar",
            "baz": [
                {"internalKey1": 1, "internalKey2": "a"},
                {"internalKey1": 2, "internalKey2": "b"},
                {"internalKey1": 3, "internalKey2": "c"},
            ],
        }
    }

    updated_plist = {
        "Crash": {
            "foo": "bar",
            "baz": [
                {"internalKey1": 1, "internalKey2": "a"},
                {"internalKey1": 3, "internalKey2": "c"},
            ],
        }
    }

    result = {"retcode": 0, "stdout": "Removed key", "stderr": ""}

    load_plist_mock = MagicMock(return_value=original_plist)
    export_plist_mock = MagicMock(return_value=result)

    with patch("salt.modules.macdefaults._load_plist", load_plist_mock), patch(
        "salt.modules.macdefaults._save_plist", export_plist_mock
    ):
        assert result == macdefaults.delete(
            "com.apple.CrashReporter",
            "Crash.baz.1",
            key_separator=".",
        )
        load_plist_mock.assert_called_once_with(
            "com.apple.CrashReporter",
            user=None,
        )
        export_plist_mock.assert_called_once_with(
            "com.apple.CrashReporter",
            updated_plist,
            user=None,
        )
