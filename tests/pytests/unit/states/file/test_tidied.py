import logging
import os
from datetime import datetime, timedelta

import pytest

import salt.states.file as filestate
import salt.utils.files
import salt.utils.json
import salt.utils.platform
import salt.utils.win_functions
import salt.utils.yaml
from tests.support.mock import MagicMock, PropertyMock, patch

log = logging.getLogger(__name__)


@pytest.fixture
def configure_loader_modules():
    return {filestate: {"__salt__": {}, "__opts__": {}}}


def test__tidied():
    name = os.sep + "test"
    if salt.utils.platform.is_windows():
        name = "c:" + name
    walker = [
        (os.path.join("test", "test1"), [], ["file1"]),
        (os.path.join("test", "test2", "test3"), [], []),
        (os.path.join("test", "test2"), ["test3"], ["file2"]),
        ("test", ["test1", "test2"], ["file3"]),
    ]
    today_delta = datetime.today() - datetime.utcfromtimestamp(0)
    remove = MagicMock(name="file.remove")

    mystat = MagicMock()
    mystat.st_atime = today_delta.total_seconds()
    # dir = 16877
    # file = 33188
    mock_st_mode = PropertyMock(
        side_effect=[
            33188,
            33188,
            16877,
            33188,
            16877,
            16877,
            33188,
            33188,
            16877,
            33188,
            16877,
            16877,
        ]
    )
    type(mystat).st_mode = mock_st_mode
    mystat.st_size = 10

    with patch("os.walk", return_value=walker), patch(
        "os.path.islink", return_value=False
    ), patch("os.stat", return_value=mystat), patch.dict(
        filestate.__opts__, {"test": False}
    ), patch.dict(
        filestate.__salt__, {"file.remove": remove}
    ), patch(
        "os.path.isdir", return_value=True
    ):
        ret = filestate.tidied(name=name)
    exp = {
        "name": name,
        "changes": {
            "removed": [
                os.path.join("test", "test1", "file1"),
                os.path.join("test", "test2", "file2"),
                os.path.join("test", "file3"),
            ]
        },
        "result": True,
        "comment": f"Removed 3 files or directories from directory {name}",
    }
    assert ret == exp
    assert remove.call_count == 3

    remove.reset_mock()
    mock_st_mode.reset_mock()

    with patch("os.walk", return_value=walker), patch(
        "os.path.islink", return_value=False
    ), patch("os.stat", return_value=mystat), patch.dict(
        filestate.__opts__, {"test": False}
    ), patch.dict(
        filestate.__salt__, {"file.remove": remove}
    ), patch(
        "os.path.isdir", return_value=True
    ):
        ret = filestate.tidied(name=name, rmdirs=True)
    exp = {
        "name": name,
        "changes": {
            "removed": [
                os.path.join("test", "test1", "file1"),
                os.path.join("test", "test2", "file2"),
                os.path.join("test", "test2", "test3"),
                os.path.join("test", "file3"),
                os.path.join("test", "test1"),
                os.path.join("test", "test2"),
            ]
        },
        "result": True,
        "comment": f"Removed 6 files or directories from directory {name}",
    }
    assert ret == exp
    assert remove.call_count == 6


def test__bad_input():
    exp = {
        "name": "test/",
        "changes": {},
        "result": False,
        "comment": "Specified file test/ is not an absolute path",
    }
    assert filestate.tidied(name="test/") == exp
    exp = {
        "name": "/bad-directory-name/",
        "changes": {},
        "result": False,
        "comment": "/bad-directory-name/ does not exist or is not a directory.",
    }
    assert filestate.tidied(name="/bad-directory-name/") == exp


def test_tidied_with_exclude():
    name = os.sep + "test"
    if salt.utils.platform.is_windows():
        name = "c:" + name
    walker = [
        (os.path.join("test", "test1"), [], ["file1"]),
        (os.path.join("test", "test2", "test3"), [], []),
        (os.path.join("test", "test2"), ["test3"], ["file2"]),
        ("test", ["test1", "test2"], ["file3"]),
    ]
    today_delta = datetime.today() - datetime.utcfromtimestamp(0)

    mystat = MagicMock()
    mystat.st_atime = today_delta.total_seconds()
    # dir = 16877
    # file = 33188
    mock_st_mode = PropertyMock(
        side_effect=[
            33188,
            33188,
            16877,
            33188,
            16877,
            16877,
            33188,
            33188,
            16877,
            33188,
            16877,
            16877,
            33188,
            33188,
            16877,
            33188,
            16877,
            16877,
        ]
    )
    type(mystat).st_mode = mock_st_mode
    mystat.st_size = 10

    remove = MagicMock(name="file.remove")

    with patch("os.walk", return_value=walker), patch(
        "os.path.islink", return_value=False
    ), patch("os.stat", return_value=mystat), patch.dict(
        filestate.__opts__, {"test": False}
    ), patch.dict(
        filestate.__salt__, {"file.remove": remove}
    ), patch(
        "os.path.isdir", return_value=True
    ):
        ret = filestate.tidied(name=name, exclude=["notfound", "file2"])
    exp = {
        "name": name,
        "changes": {
            "removed": [
                os.path.join("test", "test1", "file1"),
                os.path.join("test", "file3"),
            ]
        },
        "result": True,
        "comment": f"Removed 2 files or directories from directory {name}",
    }
    assert ret == exp
    assert remove.call_count == 2

    remove.reset_mock()
    with patch("os.walk", return_value=walker), patch(
        "os.path.islink", return_value=False
    ), patch("os.stat", return_value=mystat), patch.dict(
        filestate.__opts__, {"test": False}
    ), patch.dict(
        filestate.__salt__, {"file.remove": remove}
    ), patch(
        "os.path.isdir", return_value=True
    ):
        ret = filestate.tidied(name=name, rmdirs=True, exclude=["notfound", "file2"])
    exp = {
        "name": name,
        "changes": {
            "removed": [
                os.path.join("test", "test1", "file1"),
                os.path.join("test", "test2", "test3"),
                os.path.join("test", "file3"),
                os.path.join("test", "test1"),
                os.path.join("test", "test2"),
            ]
        },
        "result": True,
        "comment": f"Removed 5 files or directories from directory {name}",
    }
    assert ret == exp
    assert remove.call_count == 5

    remove.reset_mock()
    with patch("os.walk", return_value=walker), patch(
        "os.path.islink", return_value=False
    ), patch("os.stat", return_value=mystat), patch.dict(
        filestate.__opts__, {"test": False}
    ), patch.dict(
        filestate.__salt__, {"file.remove": remove}
    ), patch(
        "os.path.isdir", return_value=True
    ):
        ret = filestate.tidied(
            name=name,
            rmdirs=True,
            exclude=[
                "notfound",
                os.path.join("test", "test2", "file2").replace("\\", "\\\\"),
            ],
        )
    exp = {
        "name": name,
        "changes": {
            "removed": [
                os.path.join("test", "test1", "file1"),
                os.path.join("test", "test2", "file2"),
                os.path.join("test", "test2", "test3"),
                os.path.join("test", "file3"),
                os.path.join("test", "test1"),
                os.path.join("test", "test2"),
            ]
        },
        "result": True,
        "comment": f"Removed 6 files or directories from directory {name}",
    }
    assert ret == exp
    assert remove.call_count == 6


def test_tidied_with_full_path_exclude():
    name = os.sep + "test"
    if salt.utils.platform.is_windows():
        name = "c:" + name
    walker = [
        (os.path.join("test", "test1"), [], ["file1"]),
        (os.path.join("test", "test2", "test3"), [], []),
        (os.path.join("test", "test2"), ["test3"], ["file2"]),
        ("test", ["test1", "test2"], ["file3"]),
    ]
    today_delta = datetime.today() - datetime.utcfromtimestamp(0)

    mystat = MagicMock()
    mystat.st_atime = today_delta.total_seconds()
    # dir = 16877
    # file = 33188
    mock_st_mode = PropertyMock(
        side_effect=[
            33188,
            33188,
            16877,
            33188,
            16877,
            16877,
            33188,
            33188,
            16877,
            33188,
            16877,
            16877,
            33188,
            33188,
            16877,
            33188,
            16877,
            16877,
        ]
    )
    type(mystat).st_mode = mock_st_mode
    mystat.st_size = 10

    remove = MagicMock(name="file.remove")

    with patch("os.walk", return_value=walker), patch(
        "os.path.islink", return_value=False
    ), patch("os.stat", return_value=mystat), patch.dict(
        filestate.__opts__, {"test": False}
    ), patch.dict(
        filestate.__salt__, {"file.remove": remove}
    ), patch(
        "os.path.isdir", return_value=True
    ):
        ret = filestate.tidied(
            name=name,
            exclude=[os.path.join("test", "test2", "file2").replace("\\", "\\\\")],
            full_path_match=True,
        )
    exp = {
        "name": name,
        "changes": {
            "removed": [
                os.path.join("test", "test1", "file1"),
                os.path.join("test", "file3"),
            ]
        },
        "result": True,
        "comment": f"Removed 2 files or directories from directory {name}",
    }
    assert ret == exp
    assert remove.call_count == 2

    remove.reset_mock()
    with patch("os.walk", return_value=walker), patch(
        "os.path.islink", return_value=False
    ), patch("os.stat", return_value=mystat), patch.dict(
        filestate.__opts__, {"test": False}
    ), patch.dict(
        filestate.__salt__, {"file.remove": remove}
    ), patch(
        "os.path.isdir", return_value=True
    ):
        ret = filestate.tidied(
            name=name,
            rmdirs=True,
            exclude=[os.path.join("test", "test2", "file2").replace("\\", "\\\\")],
            full_path_match=True,
        )
    exp = {
        "name": name,
        "changes": {
            "removed": [
                os.path.join("test", "test1", "file1"),
                os.path.join("test", "test2", "test3"),
                os.path.join("test", "file3"),
                os.path.join("test", "test1"),
                os.path.join("test", "test2"),
            ]
        },
        "result": True,
        "comment": f"Removed 5 files or directories from directory {name}",
    }
    assert ret == exp
    assert remove.call_count == 5

    remove.reset_mock()
    with patch("os.walk", return_value=walker), patch(
        "os.path.islink", return_value=False
    ), patch("os.stat", return_value=mystat), patch.dict(
        filestate.__opts__, {"test": False}
    ), patch.dict(
        filestate.__salt__, {"file.remove": remove}
    ), patch(
        "os.path.isdir", return_value=True
    ):
        ret = filestate.tidied(
            name=name,
            rmdirs=True,
            exclude=[os.path.join("test", "test2", "file2").replace("\\", "\\\\")],
            full_path_match=False,
        )
    exp = {
        "name": name,
        "changes": {
            "removed": [
                os.path.join("test", "test1", "file1"),
                os.path.join("test", "test2", "file2"),
                os.path.join("test", "test2", "test3"),
                os.path.join("test", "file3"),
                os.path.join("test", "test1"),
                os.path.join("test", "test2"),
            ]
        },
        "result": True,
        "comment": f"Removed 6 files or directories from directory {name}",
    }
    assert ret == exp
    assert remove.call_count == 6


def test_tidied_age_size_args_AND_operator_age_not_size():
    name = os.sep + "test"
    if salt.utils.platform.is_windows():
        name = "c:" + name
    walker = [
        (os.path.join("test", "test1"), [], ["file1"]),
        (os.path.join("test", "test2", "test3"), [], []),
        (os.path.join("test", "test2"), ["test3"], ["file2"]),
        ("test", ["test1", "test2"], ["file3"]),
    ]
    today_delta = (datetime.today() - timedelta(days=14)) - datetime.utcfromtimestamp(0)
    remove = MagicMock(name="file.remove")
    with patch("os.walk", return_value=walker), patch(
        "os.path.islink", return_value=False
    ), patch("os.path.getatime", return_value=today_delta.total_seconds()), patch(
        "os.path.getsize", return_value=10
    ), patch.dict(
        filestate.__opts__, {"test": False}
    ), patch.dict(
        filestate.__salt__, {"file.remove": remove}
    ), patch(
        "os.path.isdir", return_value=True
    ):
        ret = filestate.tidied(
            name=name,
            exclude=[os.path.join("test", "test2", "file2").replace("\\", "\\\\")],
            age=1,
            size=11,
            age_size_logical_operator="AND",
            age_size_only=None,
        )
    exp = {
        "name": name,
        "changes": {},
        "result": True,
        "comment": f"Nothing to remove from directory {name}",
    }
    assert ret == exp
    assert remove.call_count == 0


def test_tidied_age_size_args_AND_operator_age_not_size_age_only():
    name = os.sep + "test"
    if salt.utils.platform.is_windows():
        name = "c:" + name
    walker = [
        (os.path.join("test", "test1"), [], ["file1"]),
        (os.path.join("test", "test2", "test3"), [], []),
        (os.path.join("test", "test2"), ["test3"], ["file2"]),
        ("test", ["test1", "test2"], ["file3"]),
    ]
    today_delta = (datetime.today() - timedelta(days=14)) - datetime.utcfromtimestamp(0)

    mystat = MagicMock()
    mystat.st_atime = today_delta.total_seconds()
    # dir = 16877
    # file = 33188
    mock_st_mode = PropertyMock(
        side_effect=[
            33188,
            33188,
            16877,
            33188,
            16877,
            16877,
        ]
    )
    type(mystat).st_mode = mock_st_mode
    mystat.st_size = 10

    remove = MagicMock(name="file.remove")

    with patch("os.walk", return_value=walker), patch(
        "os.path.islink", return_value=False
    ), patch("os.stat", return_value=mystat), patch.dict(
        filestate.__opts__, {"test": False}
    ), patch.dict(
        filestate.__salt__, {"file.remove": remove}
    ), patch(
        "os.path.isdir", return_value=True
    ):
        ret = filestate.tidied(
            name=name,
            exclude=[os.path.join("test", "test2", "file2").replace("\\", "\\\\")],
            age=1,
            size=11,
            age_size_logical_operator="AND",
            age_size_only="age",
        )
    exp = {
        "name": name,
        "changes": {
            "removed": [
                os.path.join("test", "test1", "file1"),
                os.path.join("test", "test2", "file2"),
                os.path.join("test", "file3"),
            ]
        },
        "result": True,
        "comment": f"Removed 3 files or directories from directory {name}",
    }
    assert ret == exp
    assert remove.call_count == 3


def test_tidied_age_size_args_AND_operator_size_not_age():
    name = os.sep + "test"
    if salt.utils.platform.is_windows():
        name = "c:" + name
    walker = [
        (os.path.join("test", "test1"), [], ["file1"]),
        (os.path.join("test", "test2", "test3"), [], []),
        (os.path.join("test", "test2"), ["test3"], ["file2"]),
        ("test", ["test1", "test2"], ["file3"]),
    ]
    today_delta = (datetime.today() - timedelta(days=14)) - datetime.utcfromtimestamp(0)
    remove = MagicMock(name="file.remove")
    with patch("os.walk", return_value=walker), patch(
        "os.path.islink", return_value=False
    ), patch("os.path.getatime", return_value=today_delta.total_seconds()), patch(
        "os.path.getsize", return_value=10
    ), patch.dict(
        filestate.__opts__, {"test": False}
    ), patch.dict(
        filestate.__salt__, {"file.remove": remove}
    ), patch(
        "os.path.isdir", return_value=True
    ):
        ret = filestate.tidied(
            name=name,
            exclude=[os.path.join("test", "test2", "file2").replace("\\", "\\\\")],
            age=(today_delta.days + 1),
            size=9,
            age_size_logical_operator="AND",
            age_size_only=None,
        )
    exp = {
        "name": name,
        "changes": {},
        "result": True,
        "comment": f"Nothing to remove from directory {name}",
    }
    assert ret == exp
    assert remove.call_count == 0


def test_tidied_age_size_args_AND_operator_size_not_age_size_only():
    name = os.sep + "test"
    if salt.utils.platform.is_windows():
        name = "c:" + name
    walker = [
        (os.path.join("test", "test1"), [], ["file1"]),
        (os.path.join("test", "test2", "test3"), [], []),
        (os.path.join("test", "test2"), ["test3"], ["file2"]),
        ("test", ["test1", "test2"], ["file3"]),
    ]
    today_delta = (datetime.today() - timedelta(days=14)) - datetime.utcfromtimestamp(0)

    mystat = MagicMock()
    mystat.st_atime = today_delta.total_seconds()
    # dir = 16877
    # file = 33188
    mock_st_mode = PropertyMock(
        side_effect=[
            33188,
            33188,
            16877,
            33188,
            16877,
            16877,
        ]
    )
    type(mystat).st_mode = mock_st_mode
    mystat.st_size = 10

    remove = MagicMock(name="file.remove")

    with patch("os.walk", return_value=walker), patch(
        "os.path.islink", return_value=False
    ), patch("os.stat", return_value=mystat), patch.dict(
        filestate.__opts__, {"test": False}
    ), patch.dict(
        filestate.__salt__, {"file.remove": remove}
    ), patch(
        "os.path.isdir", return_value=True
    ):
        ret = filestate.tidied(
            name=name,
            exclude=[os.path.join("test", "test2", "file2").replace("\\", "\\\\")],
            age=(today_delta.days + 1),
            size=9,
            age_size_logical_operator="AND",
            age_size_only="size",
        )
    exp = {
        "name": name,
        "changes": {
            "removed": [
                os.path.join("test", "test1", "file1"),
                os.path.join("test", "test2", "file2"),
                os.path.join("test", "file3"),
            ]
        },
        "result": True,
        "comment": f"Removed 3 files or directories from directory {name}",
    }
    assert ret == exp
    assert remove.call_count == 3


def test_tidied_age_size_args_AND_operator_size_and_age():
    name = os.sep + "test"
    if salt.utils.platform.is_windows():
        name = "c:" + name
    walker = [
        (os.path.join("test", "test1"), [], ["file1"]),
        (os.path.join("test", "test2", "test3"), [], []),
        (os.path.join("test", "test2"), ["test3"], ["file2"]),
        ("test", ["test1", "test2"], ["file3"]),
    ]
    today_delta = (datetime.today() - timedelta(days=14)) - datetime.utcfromtimestamp(0)

    mystat = MagicMock()
    mystat.st_atime = today_delta.total_seconds()
    # dir = 16877
    # file = 33188
    mock_st_mode = PropertyMock(
        side_effect=[
            33188,
            33188,
            16877,
            33188,
            16877,
            16877,
        ]
    )
    type(mystat).st_mode = mock_st_mode
    mystat.st_size = 10

    remove = MagicMock(name="file.remove")

    with patch("os.walk", return_value=walker), patch(
        "os.path.islink", return_value=False
    ), patch("os.stat", return_value=mystat), patch.dict(
        filestate.__opts__, {"test": False}
    ), patch.dict(
        filestate.__salt__, {"file.remove": remove}
    ), patch(
        "os.path.isdir", return_value=True
    ):
        ret = filestate.tidied(
            name=name,
            exclude=[os.path.join("test", "test2", "file2").replace("\\", "\\\\")],
            age=1,
            size=9,
            age_size_logical_operator="AND",
            age_size_only=None,
        )
    exp = {
        "name": name,
        "changes": {
            "removed": [
                os.path.join("test", "test1", "file1"),
                os.path.join("test", "test2", "file2"),
                os.path.join("test", "file3"),
            ]
        },
        "result": True,
        "comment": f"Removed 3 files or directories from directory {name}",
    }
    assert ret == exp
    assert remove.call_count == 3


def test_tidied_filenotfound(tmp_path):
    name = tmp_path / "not_found_test"
    name.mkdir(parents=True, exist_ok=True)
    name = str(tmp_path / "not_found_test")
    walker = [
        (os.path.join(name, "test1"), [], ["file1"]),
        (os.path.join(name, "test2", "test3"), [], []),
        (os.path.join(name, "test2"), ["test3"], ["file2"]),
        (name, ["test1", "test2"], ["file3"]),
    ]
    # mock the walk, but files aren't there
    with patch("os.walk", return_value=walker), patch(
        "os.path.islink", return_value=False
    ):
        ret = filestate.tidied(
            name=name,
            age=1,
            size=9,
        )
    exp = {
        "name": name,
        "changes": {},
        "result": True,
        "comment": f"Nothing to remove from directory {name}",
    }
    assert ret == exp


def test_tidied_rmlinks():
    name = os.sep + "test"
    if salt.utils.platform.is_windows():
        name = "c:" + name
    walker = [
        (os.path.join("test", "test1"), [], ["file1"]),
        (os.path.join("test", "test2", "test3"), [], []),
        (os.path.join("test", "test2"), ["test3"], ["link1"]),
        ("test", ["test1", "test2"], ["file3"]),
    ]
    today_delta = (datetime.today() - timedelta(days=14)) - datetime.utcfromtimestamp(0)

    mystat = MagicMock()
    mystat.st_atime = today_delta.total_seconds()
    # dir = 16877
    # file = 33188
    mock_st_mode = PropertyMock(
        side_effect=[
            33188,
            16877,
            33188,
            16877,
            16877,
        ]
    )
    type(mystat).st_mode = mock_st_mode
    mystat.st_size = 10

    mylstat = MagicMock()
    mylstat.st_atime = today_delta.total_seconds()
    mylstat.st_mode = 33188
    mylstat.st_size = 10

    remove = MagicMock(name="file.remove")

    with patch("os.walk", return_value=walker), patch(
        "os.path.islink", side_effect=[False, True, False, False, False, False]
    ), patch("os.lstat", return_value=mylstat), patch(
        "os.stat", return_value=mystat
    ), patch.dict(
        filestate.__opts__, {"test": False}
    ), patch.dict(
        filestate.__salt__, {"file.remove": remove}
    ), patch(
        "os.path.isdir", return_value=True
    ):
        ret = filestate.tidied(
            name=name,
            age=1,
            size=9,
            rmlinks=False,
        )
    exp = {
        "name": name,
        "changes": {
            "removed": [
                os.path.join("test", "test1", "file1"),
                os.path.join("test", "file3"),
            ]
        },
        "result": True,
        "comment": f"Removed 2 files or directories from directory {name}",
    }
    assert ret == exp
    assert remove.call_count == 2
