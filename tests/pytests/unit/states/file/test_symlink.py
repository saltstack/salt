import logging
import os

import pytest

import salt.serializers.json as jsonserializer
import salt.serializers.msgpack as msgpackserializer
import salt.serializers.yaml as yamlserializer
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
    return {
        filestate: {
            "__env__": "base",
            "__salt__": {"file.manage_file": False},
            "__serializers__": {
                "yaml.serialize": yamlserializer.serialize,
                "yaml.seserialize": yamlserializer.serialize,
                "json.serialize": jsonserializer.serialize,
                "msgpack.serialize": msgpackserializer.serialize,
            },
            "__opts__": {"test": False, "cachedir": ""},
            "__instance_id__": "",
            "__low__": {},
            "__utils__": {},
        }
    }


def test_symlink():
    """
    Test to create a symlink.
    """
    name = os.sep + os.path.join("tmp", "testfile.txt")
    target = salt.utils.files.mkstemp()
    test_dir = os.sep + "tmp"
    user = "salt"

    if salt.utils.platform.is_windows():
        group = "salt"
    else:
        group = "saltstack"

    def return_val(kwargs):
        val = {
            "name": name,
            "result": False,
            "comment": "",
            "changes": {},
        }
        val.update(kwargs)
        return val

    mock_t = MagicMock(return_value=True)
    mock_f = MagicMock(return_value=False)
    mock_empty = MagicMock(return_value="")
    mock_uid = MagicMock(return_value="U1001")
    mock_gid = MagicMock(return_value="g1001")
    mock_target = MagicMock(return_value=target)
    mock_user = MagicMock(return_value=user)
    mock_grp = MagicMock(return_value=group)
    mock_os_error = MagicMock(side_effect=OSError)

    with patch.dict(filestate.__salt__, {"config.manage_mode": mock_t}):
        comt = "Must provide name to file.symlink"
        ret = return_val({"comment": comt, "name": ""})
        assert filestate.symlink("", target) == ret

    with patch.dict(
        filestate.__salt__,
        {
            "config.manage_mode": mock_t,
            "file.user_to_uid": mock_empty,
            "file.group_to_gid": mock_empty,
            "user.info": mock_empty,
            "user.current": mock_user,
        },
    ):
        if salt.utils.platform.is_windows():
            comt = f"User {user} does not exist"
            ret = return_val({"comment": comt, "name": name})
        else:
            comt = "User {} does not exist. Group {} does not exist.".format(
                user, group
            )
            ret = return_val({"comment": comt, "name": name})
        assert filestate.symlink(name, target, user=user, group=group) == ret

    with patch.dict(
        filestate.__salt__,
        {
            "config.manage_mode": mock_t,
            "file.user_to_uid": mock_uid,
            "file.group_to_gid": mock_gid,
            "file.is_link": mock_f,
            "user.info": mock_empty,
            "user.current": mock_user,
        },
    ), patch.dict(filestate.__opts__, {"test": True}), patch.object(
        os.path, "exists", mock_f
    ):
        if salt.utils.platform.is_windows():
            comt = f"User {user} does not exist"
            ret = return_val(
                {"comment": comt, "result": False, "name": name, "changes": {}}
            )
        else:
            comt = f"Symlink {name} to {target} is set for creation"
            ret = return_val(
                {"comment": comt, "result": None, "changes": {"new": name}}
            )
        assert filestate.symlink(name, target, user=user, group=group) == ret

    with patch.dict(
        filestate.__salt__,
        {
            "config.manage_mode": mock_t,
            "file.user_to_uid": mock_uid,
            "file.group_to_gid": mock_gid,
            "file.is_link": mock_f,
            "user.info": mock_empty,
            "user.current": mock_user,
        },
    ), patch.dict(filestate.__opts__, {"test": False}), patch.object(
        os.path, "isdir", mock_f
    ), patch.object(
        os.path, "exists", mock_f
    ):
        if salt.utils.platform.is_windows():
            comt = f"User {user} does not exist"
            ret = return_val(
                {"comment": comt, "result": False, "name": name, "changes": {}}
            )
        else:
            comt = f"Directory {test_dir} for symlink is not present"
            ret = return_val({"comment": comt, "result": False, "changes": {}})
        assert filestate.symlink(name, target, user=user, group=group) == ret

    with patch.dict(
        filestate.__salt__,
        {
            "config.manage_mode": mock_t,
            "file.user_to_uid": mock_uid,
            "file.group_to_gid": mock_gid,
            "file.is_link": mock_t,
            "file.readlink": mock_target,
            "user.info": mock_empty,
            "user.current": mock_user,
        },
    ), patch.dict(filestate.__opts__, {"test": False}), patch.object(
        os.path, "isdir", mock_t
    ), patch.object(
        salt.states.file, "_check_symlink_ownership", mock_t
    ), patch(
        "salt.utils.win_functions.get_sid_from_name", return_value="test-sid"
    ):
        if salt.utils.platform.is_windows():
            comt = f"Symlink {name} is present and owned by {user}"
        else:
            comt = f"Symlink {name} is present and owned by {user}:{group}"
        ret = return_val({"comment": comt, "result": True, "changes": {}})
        assert filestate.symlink(name, target, user=user, group=group) == ret

    with patch.dict(
        filestate.__salt__,
        {
            "config.manage_mode": mock_t,
            "file.user_to_uid": mock_uid,
            "file.group_to_gid": mock_gid,
            "file.is_link": mock_f,
            "file.readlink": mock_target,
            "user.info": mock_empty,
            "user.current": mock_user,
        },
    ), patch.dict(filestate.__opts__, {"test": False}), patch.object(
        os.path, "isdir", mock_t
    ), patch.object(
        os.path, "exists", mock_t
    ), patch.object(
        os.path, "lexists", mock_t
    ), patch(
        "salt.utils.win_functions.get_sid_from_name", return_value="test-sid"
    ):
        comt = (
            "Symlink & backup dest exists and Force not set. {} -> "
            "{} - backup: {}".format(name, target, os.path.join(test_dir, "SALT"))
        )
        ret.update({"comment": comt, "result": False, "changes": {}})
        assert (
            filestate.symlink(name, target, user=user, group=group, backupname="SALT")
            == ret
        )

    with patch.dict(
        filestate.__salt__,
        {
            "config.manage_mode": mock_t,
            "file.user_to_uid": mock_uid,
            "file.group_to_gid": mock_gid,
            "file.is_link": mock_f,
            "file.readlink": mock_target,
            "user.info": mock_empty,
            "user.current": mock_user,
        },
    ), patch.dict(filestate.__opts__, {"test": False}), patch.object(
        os.path, "exists", mock_t
    ), patch.object(
        os.path, "isfile", mock_t
    ), patch.object(
        os.path, "isdir", mock_t
    ), patch(
        "salt.utils.win_functions.get_sid_from_name", return_value="test-sid"
    ):
        comt = "Backupname must be an absolute path or a file name: {}".format(
            "tmp/SALT"
        )
        ret.update({"comment": comt, "result": False, "changes": {}})
        assert (
            filestate.symlink(
                name, target, user=user, group=group, backupname="tmp/SALT"
            )
            == ret
        )

    with patch.dict(
        filestate.__salt__,
        {
            "config.manage_mode": mock_t,
            "file.user_to_uid": mock_uid,
            "file.group_to_gid": mock_gid,
            "file.is_link": mock_f,
            "file.readlink": mock_target,
            "user.info": mock_empty,
            "user.current": mock_user,
        },
    ), patch.dict(filestate.__opts__, {"test": False}), patch.object(
        os.path, "isdir", mock_t
    ), patch.object(
        os.path, "exists", mock_t
    ), patch.object(
        os.path, "isfile", mock_t
    ), patch(
        "salt.utils.win_functions.get_sid_from_name", return_value="test-sid"
    ):
        comt = f"File exists where the symlink {name} should be"
        ret = return_val({"comment": comt, "changes": {}, "result": False})
        assert filestate.symlink(name, target, user=user, group=group) == ret

    with patch.dict(
        filestate.__salt__,
        {
            "config.manage_mode": mock_t,
            "file.user_to_uid": mock_uid,
            "file.group_to_gid": mock_gid,
            "file.is_link": mock_f,
            "file.readlink": mock_target,
            "file.symlink": mock_t,
            "user.info": mock_t,
            "file.lchown": mock_f,
        },
    ), patch.dict(filestate.__opts__, {"test": False}), patch.object(
        os.path, "isdir", MagicMock(side_effect=[True, False])
    ), patch.object(
        os.path, "isdir", mock_t
    ), patch.object(
        os.path, "exists", mock_t
    ), patch(
        "salt.utils.win_functions.get_sid_from_name", return_value="test-sid"
    ):
        comt = f"Directory exists where the symlink {name} should be"
        ret = return_val({"comment": comt, "result": False, "changes": {}})
        assert filestate.symlink(name, target, user=user, group=group) == ret

    with patch.dict(
        filestate.__salt__,
        {
            "config.manage_mode": mock_t,
            "file.user_to_uid": mock_uid,
            "file.group_to_gid": mock_gid,
            "file.is_link": mock_f,
            "file.readlink": mock_target,
            "file.symlink": mock_os_error,
            "user.info": mock_t,
            "file.lchown": mock_f,
        },
    ), patch.dict(filestate.__opts__, {"test": False}), patch.object(
        os.path, "isdir", MagicMock(side_effect=[True, False])
    ), patch.object(
        os.path, "isfile", mock_f
    ), patch(
        "salt.utils.win_functions.get_sid_from_name", return_value="test-sid"
    ):
        comt = f"Unable to create new symlink {name} -> {target}: "
        ret = return_val({"comment": comt, "result": False, "changes": {}})
        assert filestate.symlink(name, target, user=user, group=group) == ret

    with patch.dict(
        filestate.__salt__,
        {
            "config.manage_mode": mock_t,
            "file.user_to_uid": mock_uid,
            "file.group_to_gid": mock_gid,
            "file.is_link": mock_f,
            "file.readlink": mock_target,
            "file.symlink": mock_t,
            "user.info": mock_t,
            "file.lchown": mock_f,
            "file.get_user": mock_user,
            "file.get_group": mock_grp,
        },
    ), patch.dict(filestate.__opts__, {"test": False}), patch.object(
        os.path, "isdir", MagicMock(side_effect=[True, False])
    ), patch.object(
        os.path, "isfile", mock_f
    ), patch(
        "salt.states.file._check_symlink_ownership", return_value=True
    ), patch(
        "salt.utils.win_functions.get_sid_from_name", return_value="test-sid"
    ):
        comt = f"Created new symlink {name} -> {target}"
        ret = return_val({"comment": comt, "result": True, "changes": {"new": name}})
        assert filestate.symlink(name, target, user=user, group=group) == ret

    with patch.dict(
        filestate.__salt__,
        {
            "config.manage_mode": mock_t,
            "file.user_to_uid": mock_uid,
            "file.group_to_gid": mock_gid,
            "file.is_link": mock_f,
            "file.readlink": mock_target,
            "file.symlink": mock_t,
            "user.info": mock_t,
            "file.lchown": mock_f,
            "file.get_user": mock_empty,
            "file.get_group": mock_empty,
        },
    ), patch.dict(filestate.__opts__, {"test": False}), patch.object(
        os.path, "isdir", MagicMock(side_effect=[True, False])
    ), patch.object(
        os.path, "isfile", mock_f
    ), patch(
        "salt.utils.win_functions.get_sid_from_name", return_value="test-sid"
    ), patch(
        "salt.states.file._set_symlink_ownership", return_value=False
    ), patch(
        "salt.states.file._check_symlink_ownership", return_value=False
    ):
        comt = (
            "Created new symlink {} -> {}, but was unable to set "
            "ownership to {}:{}".format(name, target, user, group)
        )
        ret = return_val({"comment": comt, "result": False, "changes": {"new": name}})
        assert filestate.symlink(name, target, user=user, group=group) == ret

    with patch.dict(
        filestate.__salt__,
        {
            "config.manage_mode": mock_t,
            "file.user_to_uid": mock_uid,
            "file.group_to_gid": mock_gid,
            "file.is_link": mock_f,
            "file.readlink": mock_target,
            "file.symlink": mock_t,
            "user.info": mock_t,
            "file.lchown": mock_f,
            "file.get_user": mock_empty,
            "file.get_group": mock_empty,
        },
    ), patch.dict(filestate.__opts__, {"test": False}), patch.object(
        os.path, "isdir", MagicMock(side_effect=[True, False])
    ), patch.object(
        os.path, "isfile", mock_f
    ), patch(
        "salt.utils.win_functions.get_sid_from_name", return_value="test-sid"
    ), patch(
        "salt.states.file._set_symlink_ownership", return_value=True
    ), patch(
        "salt.states.file._check_symlink_ownership", return_value=True
    ):
        comt = f"Created new symlink {name} -> {target}"
        ret = return_val({"comment": comt, "result": True, "changes": {"new": name}})
        res = filestate.symlink(name, target, user=user, group=user)
        assert res == ret

    with patch.dict(
        filestate.__salt__,
        {
            "file.is_link": mock_t,
            "file.get_user": mock_user,
            "file.get_group": mock_grp,
            "file.user_to_uid": mock_uid,
            "file.group_to_gid": mock_gid,
            "file.gid_to_group": MagicMock(return_value=group),
            "file.readlink": mock_target,
            "user.info": mock_t,
        },
    ), patch.dict(filestate.__opts__, {"test": False}), patch.object(
        os.path, "isdir", MagicMock(side_effect=[True, False])
    ), patch.object(
        os.path, "isfile", mock_f
    ), patch(
        "salt.utils.win_functions.get_sid_from_name", return_value="test-sid"
    ), patch(
        "salt.states.file._set_symlink_ownership", return_value=True
    ), patch(
        "salt.states.file._check_symlink_ownership", return_value=True
    ), patch(
        "salt.states.file._get_symlink_ownership", return_value=(user, group)
    ):
        if salt.utils.platform.is_windows():
            comt = f"Symlink {name} is present and owned by {user}"
        else:
            comt = f"Symlink {name} is present and owned by {user}:{group}"
        ret = return_val({"comment": comt, "result": True, "changes": {}})
        res = filestate.symlink(name, target, inherit_user_and_group=True)
        assert res == ret
