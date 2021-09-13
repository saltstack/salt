import logging
import os

import pytest
import salt.serializers.json as jsonserializer
import salt.serializers.msgpack as msgpackserializer
import salt.serializers.plist as plistserializer
import salt.serializers.python as pythonserializer
import salt.serializers.yaml as yamlserializer
import salt.states.file as filestate
import salt.utils.files
import salt.utils.json
import salt.utils.platform
import salt.utils.win_functions
import salt.utils.yaml
from salt.exceptions import CommandExecutionError
from tests.support.mock import MagicMock, patch

log = logging.getLogger(__name__)


@pytest.fixture
def configure_loader_modules():
    return {
        filestate: {
            "__env__": "base",
            "__salt__": {"file.manage_file": False},
            "__serializers__": {
                "yaml.serialize": yamlserializer.serialize,
                "yaml.seserialize": yamlserializer.serialize,
                "python.serialize": pythonserializer.serialize,
                "json.serialize": jsonserializer.serialize,
                "plist.serialize": plistserializer.serialize,
                "msgpack.serialize": msgpackserializer.serialize,
            },
            "__opts__": {"test": False, "cachedir": ""},
            "__instance_id__": "",
            "__low__": {},
            "__utils__": {},
        }
    }


# 'directory' function tests: 1
def test_directory():
    """
    Test to ensure that a named directory is present and has the right perms
    """
    name = "/etc/testdir"
    user = "salt"
    group = "saltstack"
    if salt.utils.platform.is_windows():
        name = name.replace("/", "\\")

    ret = {"name": name, "result": False, "comment": "", "changes": {}}

    check_perms_ret = {"name": name, "result": False, "comment": "", "changes": {}}

    comt = "Must provide name to file.directory"
    ret.update({"comment": comt, "name": ""})
    assert filestate.directory("") == ret

    comt = "Cannot specify both max_depth and clean"
    ret.update({"comment": comt, "name": name})
    assert filestate.directory(name, clean=True, max_depth=2) == ret

    mock_t = MagicMock(return_value=True)
    mock_f = MagicMock(return_value=False)
    if salt.utils.platform.is_windows():
        mock_perms = MagicMock(return_value=check_perms_ret)
    else:
        mock_perms = MagicMock(return_value=(check_perms_ret, ""))
    mock_uid = MagicMock(
        side_effect=[
            "",
            "U12",
            "U12",
            "U12",
            "U12",
            "U12",
            "U12",
            "U12",
            "U12",
            "U12",
            "U12",
        ]
    )
    mock_gid = MagicMock(
        side_effect=[
            "",
            "G12",
            "G12",
            "G12",
            "G12",
            "G12",
            "G12",
            "G12",
            "G12",
            "G12",
            "G12",
        ]
    )
    mock_check = MagicMock(
        return_value=(
            None,
            'The directory "{}" will be changed'.format(name),
            {name: {"directory": "new"}},
        )
    )
    mock_error = CommandExecutionError
    with patch.dict(
        filestate.__salt__,
        {
            "config.manage_mode": mock_t,
            "file.user_to_uid": mock_uid,
            "file.group_to_gid": mock_gid,
            "file.stats": mock_f,
            "file.check_perms": mock_perms,
            "file.mkdir": mock_t,
        },
    ), patch("salt.utils.win_dacl.get_sid", mock_error), patch(
        "os.path.isdir", mock_t
    ), patch(
        "salt.states.file._check_directory_win", mock_check
    ):
        if salt.utils.platform.is_windows():
            comt = ""
        else:
            comt = "User salt is not available Group saltstack is not available"
        ret.update({"comment": comt, "name": name})
        assert filestate.directory(name, user=user, group=group) == ret

        with patch.object(os.path, "isabs", mock_f):
            comt = "Specified file {} is not an absolute path".format(name)
            ret.update({"comment": comt})
            assert filestate.directory(name, user=user, group=group) == ret

        with patch.object(os.path, "isabs", mock_t):
            with patch.object(
                os.path,
                "isfile",
                MagicMock(side_effect=[True, True, False, True, True, True, False]),
            ):
                with patch.object(os.path, "lexists", mock_t):
                    comt = "File exists where the backup target A should go"
                    ret.update({"comment": comt})
                    assert (
                        filestate.directory(
                            name, user=user, group=group, backupname="A"
                        )
                        == ret
                    )

                with patch.object(os.path, "isfile", mock_t):
                    comt = "Specified location {} exists and is a file".format(name)
                    ret.update({"comment": comt})
                    assert filestate.directory(name, user=user, group=group) == ret

                with patch.object(os.path, "islink", mock_t):
                    comt = "Specified location {} exists and is a symlink".format(name)
                    ret.update({"comment": comt})
                    assert filestate.directory(name, user=user, group=group) == ret

            with patch.object(os.path, "isdir", mock_f):
                with patch.dict(filestate.__opts__, {"test": True}):
                    if salt.utils.platform.is_windows():
                        comt = 'The directory "{}" will be changed' "".format(name)
                    else:
                        comt = (
                            "The following files will be changed:\n{}:"
                            " directory - new\n".format(name)
                        )
                    ret.update(
                        {
                            "comment": comt,
                            "result": None,
                            "changes": {name: {"directory": "new"}},
                        }
                    )
                    assert filestate.directory(name, user=user, group=group) == ret

                with patch.dict(filestate.__opts__, {"test": False}):
                    with patch.object(os.path, "isdir", mock_f):
                        comt = "No directory to create {} in".format(name)
                        ret.update({"comment": comt, "result": False})
                        assert filestate.directory(name, user=user, group=group) == ret

                    if salt.utils.platform.is_windows():
                        isdir_side_effect = [False, True, False]
                    else:
                        isdir_side_effect = [True, False, True, False]
                    with patch.object(
                        os.path, "isdir", MagicMock(side_effect=isdir_side_effect)
                    ):
                        comt = "Failed to create directory {}".format(name)
                        ret.update(
                            {
                                "comment": comt,
                                "result": False,
                                "changes": {name: {"directory": "new"}},
                            }
                        )
                        assert filestate.directory(name, user=user, group=group) == ret

                    check_perms_ret = {
                        "name": name,
                        "result": False,
                        "comment": "",
                        "changes": {},
                    }
                    if salt.utils.platform.is_windows():
                        mock_perms = MagicMock(return_value=check_perms_ret)
                    else:
                        mock_perms = MagicMock(return_value=(check_perms_ret, ""))

                    recurse = ["silent"]
                    ret = {
                        "name": name,
                        "result": False,
                        "comment": "Directory /etc/testdir updated",
                        "changes": {"recursion": "Changes silenced"},
                    }
                    if salt.utils.platform.is_windows():
                        ret["comment"] = ret["comment"].replace("/", "\\")
                    with patch.dict(
                        filestate.__salt__, {"file.check_perms": mock_perms}
                    ):
                        with patch.object(os.path, "isdir", mock_t):
                            assert (
                                filestate.directory(
                                    name, user=user, recurse=recurse, group=group
                                )
                                == ret
                            )

                    check_perms_ret = {
                        "name": name,
                        "result": False,
                        "comment": "",
                        "changes": {},
                    }
                    if salt.utils.platform.is_windows():
                        mock_perms = MagicMock(return_value=check_perms_ret)
                    else:
                        mock_perms = MagicMock(return_value=(check_perms_ret, ""))

                    recurse = ["ignore_files", "ignore_dirs"]
                    ret = {
                        "name": name,
                        "result": False,
                        "comment": 'Must not specify "recurse" '
                        'options "ignore_files" and '
                        '"ignore_dirs" at the same '
                        "time.",
                        "changes": {},
                    }
                    with patch.dict(
                        filestate.__salt__, {"file.check_perms": mock_perms}
                    ):
                        with patch.object(os.path, "isdir", mock_t):
                            assert (
                                filestate.directory(
                                    name, user=user, recurse=recurse, group=group
                                )
                                == ret
                            )

                    comt = "Directory {} updated".format(name)
                    ret = {
                        "name": name,
                        "result": True,
                        "comment": comt,
                        "changes": {"group": "group", "mode": "0777", "user": "user"},
                    }

                    check_perms_ret = {
                        "name": name,
                        "result": True,
                        "comment": "",
                        "changes": {"group": "group", "mode": "0777", "user": "user"},
                    }

                    if salt.utils.platform.is_windows():
                        _mock_perms = MagicMock(return_value=check_perms_ret)
                    else:
                        _mock_perms = MagicMock(return_value=(check_perms_ret, ""))
                    with patch.object(os.path, "isdir", mock_t):
                        with patch.dict(
                            filestate.__salt__, {"file.check_perms": _mock_perms}
                        ):
                            assert (
                                filestate.directory(name, user=user, group=group) == ret
                            )
