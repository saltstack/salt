import logging
import os
from datetime import datetime

import pytest
import salt.states.file as filestate
import salt.utils.files
import salt.utils.json
import salt.utils.platform
import salt.utils.win_functions
import salt.utils.yaml
from tests.support.mock import MagicMock, patch

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
        "comment": "Removed 3 files or directories from directory {}".format(name),
    }
    assert exp == ret
    assert remove.call_count == 3

    remove.reset_mock()
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
        "comment": "Removed 6 files or directories from directory {}".format(name),
    }
    assert exp == ret
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
