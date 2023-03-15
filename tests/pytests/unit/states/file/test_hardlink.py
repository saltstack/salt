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


@pytest.mark.skip_on_windows(reason="Do not run on Windows")
def test_hardlink(tmp_path):
    """
    Test to create a hardlink.
    """

    name = str(tmp_path / "testfile.txt")
    target = str(tmp_path / "target.txt")
    with salt.utils.files.fopen(target, "w") as fp:
        fp.write("")

    test_dir = str(tmp_path)
    user, group = "salt", "saltstack"

    def return_val(**kwargs):
        res = {
            "name": name,
            "result": False,
            "comment": "",
            "changes": {},
        }
        res.update(kwargs)
        return res

    mock_t = MagicMock(return_value=True)
    mock_f = MagicMock(return_value=False)
    mock_empty = MagicMock(return_value="")
    mock_uid = MagicMock(return_value="U1001")
    mock_gid = MagicMock(return_value="g1001")
    mock_nothing = MagicMock(return_value={})
    mock_stats = MagicMock(return_value={"inode": 1})
    mock_execerror = MagicMock(side_effect=CommandExecutionError)

    patches = {}
    patches["file.user_to_uid"] = mock_empty
    patches["file.group_to_gid"] = mock_empty
    patches["user.info"] = mock_empty
    patches["file.is_hardlink"] = mock_t
    patches["file.stats"] = mock_empty

    # Argument validation
    with patch.dict(filestate.__salt__, patches):
        expected = "Must provide name to file.hardlink"
        ret = return_val(comment=expected, name="")
        assert filestate.hardlink("", target) == ret

    # User validation for dir_mode
    with patch.dict(filestate.__salt__, patches), patch.dict(
        filestate.__salt__, {"file.user_to_uid": mock_empty}
    ), patch.dict(filestate.__salt__, {"file.group_to_gid": mock_gid}), patch.object(
        os.path, "isabs", mock_t
    ):
        expected = "User {} does not exist".format(user)
        ret = return_val(comment=expected, name=name)
        assert filestate.hardlink(name, target, user=user, group=group) == ret

    # Group validation for dir_mode
    with patch.dict(filestate.__salt__, patches), patch.dict(
        filestate.__salt__, {"file.user_to_uid": mock_uid}
    ), patch.dict(filestate.__salt__, {"file.group_to_gid": mock_empty}), patch.object(
        os.path, "isabs", mock_t
    ):
        expected = "Group {} does not exist".format(group)
        ret = return_val(comment=expected, name=name)
        assert filestate.hardlink(name, target, user=user, group=group) == ret

    # Absolute path for name
    nonabs = "./non-existent-path/to/non-existent-file"
    with patch.dict(filestate.__salt__, patches), patch.dict(
        filestate.__salt__, {"file.user_to_uid": mock_uid}
    ), patch.dict(filestate.__salt__, {"file.group_to_gid": mock_gid}):
        expected = "Specified file {} is not an absolute path".format(nonabs)
        ret = return_val(comment=expected, name=nonabs)
        assert filestate.hardlink(nonabs, target, user=user, group=group) == ret

    # Absolute path for target
    with patch.dict(filestate.__salt__, patches), patch.dict(
        filestate.__salt__, {"file.user_to_uid": mock_uid}
    ), patch.dict(filestate.__salt__, {"file.group_to_gid": mock_gid}):
        expected = "Specified target {} is not an absolute path".format(nonabs)
        ret = return_val(comment=expected, name=name)
        assert filestate.hardlink(name, nonabs, user=user, group=group) == ret
    # Test option -- nonexistent target
    with patch.dict(filestate.__salt__, patches), patch.dict(
        filestate.__salt__, {"file.user_to_uid": mock_uid}
    ), patch.dict(filestate.__salt__, {"file.group_to_gid": mock_gid}), patch.object(
        os.path, "exists", mock_f
    ), patch.dict(
        filestate.__opts__, {"test": True}
    ):
        expected = "Target {} for hard link does not exist".format(target)
        ret = return_val(comment=expected, name=name)
        assert filestate.hardlink(name, target, user=user, group=group) == ret

    # Test option -- target is a directory
    with patch.dict(filestate.__salt__, patches), patch.dict(
        filestate.__salt__, {"file.user_to_uid": mock_uid}
    ), patch.dict(filestate.__salt__, {"file.group_to_gid": mock_gid}), patch.object(
        os.path, "exists", mock_t
    ), patch.dict(
        filestate.__opts__, {"test": True}
    ):
        expected = "Unable to hard link from directory {}".format(test_dir)
        ret = return_val(comment=expected, name=name)
        assert filestate.hardlink(name, test_dir, user=user, group=group) == ret

    # Test option -- name is a directory
    with patch.dict(filestate.__salt__, patches), patch.dict(
        filestate.__salt__, {"file.user_to_uid": mock_uid}
    ), patch.dict(filestate.__salt__, {"file.group_to_gid": mock_gid}), patch.dict(
        filestate.__opts__, {"test": True}
    ):
        expected = "Unable to hard link to directory {}".format(test_dir)
        ret = return_val(comment=expected, name=test_dir)
        assert filestate.hardlink(test_dir, target, user=user, group=group) == ret

    # Test option -- name does not exist
    with patch.dict(filestate.__salt__, patches), patch.dict(
        filestate.__salt__, {"file.user_to_uid": mock_uid}
    ), patch.dict(filestate.__salt__, {"file.group_to_gid": mock_gid}), patch.dict(
        filestate.__opts__, {"test": True}
    ):
        expected = "Hard link {} to {} is set for creation".format(name, target)
        changes = dict(new=name)
        ret = return_val(result=None, comment=expected, name=name, changes=changes)
        assert filestate.hardlink(name, target, user=user, group=group) == ret

    # Test option -- hardlink matches
    with patch.dict(filestate.__salt__, patches), patch.dict(
        filestate.__salt__, {"file.user_to_uid": mock_uid}
    ), patch.dict(filestate.__salt__, {"file.group_to_gid": mock_gid}), patch.dict(
        filestate.__salt__, {"file.is_hardlink": mock_t}
    ), patch.dict(
        filestate.__salt__, {"file.stats": mock_stats}
    ), patch.object(
        os.path, "exists", mock_t
    ), patch.dict(
        filestate.__opts__, {"test": True}
    ):
        expected = "The hard link {} is presently targetting {}".format(name, target)
        ret = return_val(result=True, comment=expected, name=name)
        assert filestate.hardlink(name, target, user=user, group=group) == ret

    # Test option -- hardlink does not match
    with patch.dict(filestate.__salt__, patches), patch.dict(
        filestate.__salt__, {"file.user_to_uid": mock_uid}
    ), patch.dict(filestate.__salt__, {"file.group_to_gid": mock_gid}), patch.dict(
        filestate.__salt__, {"file.is_hardlink": mock_t}
    ), patch.dict(
        filestate.__salt__, {"file.stats": mock_nothing}
    ), patch.object(
        os.path, "exists", mock_t
    ), patch.dict(
        filestate.__opts__, {"test": True}
    ):
        expected = "Link {} target is set to be changed to {}".format(name, target)
        changes = dict(change=name)
        ret = return_val(result=None, comment=expected, name=name, changes=changes)
        assert filestate.hardlink(name, target, user=user, group=group) == ret

    # Test option -- force removal
    with patch.dict(filestate.__salt__, patches), patch.dict(
        filestate.__salt__, {"file.user_to_uid": mock_uid}
    ), patch.dict(filestate.__salt__, {"file.group_to_gid": mock_gid}), patch.dict(
        filestate.__salt__, {"file.is_hardlink": mock_f}
    ), patch.object(
        os.path, "exists", mock_t
    ), patch.dict(
        filestate.__opts__, {"test": True}
    ):
        expected = (
            "The file or directory {} is set for removal to "
            "make way for a new hard link targeting {}".format(name, target)
        )
        ret = return_val(result=None, comment=expected, name=name)
        assert (
            filestate.hardlink(name, target, force=True, user=user, group=group) == ret
        )

    # Test option -- without force removal
    with patch.dict(filestate.__salt__, patches), patch.dict(
        filestate.__salt__, {"file.user_to_uid": mock_uid}
    ), patch.dict(filestate.__salt__, {"file.group_to_gid": mock_gid}), patch.dict(
        filestate.__salt__, {"file.is_hardlink": mock_f}
    ), patch.object(
        os.path, "exists", mock_t
    ), patch.dict(
        filestate.__opts__, {"test": True}
    ):
        expected = (
            "File or directory exists where the hard link {} "
            "should be. Did you mean to use force?".format(name)
        )
        ret = return_val(result=False, comment=expected, name=name)
        assert (
            filestate.hardlink(name, target, force=False, user=user, group=group) == ret
        )

    # Target is a directory
    with patch.dict(filestate.__salt__, patches), patch.dict(
        filestate.__salt__, {"file.user_to_uid": mock_uid}
    ), patch.dict(filestate.__salt__, {"file.group_to_gid": mock_gid}):
        expected = "Unable to hard link from directory {}".format(test_dir)
        ret = return_val(comment=expected, name=name)
        assert filestate.hardlink(name, test_dir, user=user, group=group) == ret

    # Name is a directory
    with patch.dict(filestate.__salt__, patches), patch.dict(
        filestate.__salt__, {"file.user_to_uid": mock_uid}
    ), patch.dict(filestate.__salt__, {"file.group_to_gid": mock_gid}):
        expected = "Unable to hard link to directory {}".format(test_dir)
        ret = return_val(comment=expected, name=test_dir)
        assert filestate.hardlink(test_dir, target, user=user, group=group) == ret

    # Try overwrite file with link
    with patch.dict(filestate.__salt__, patches), patch.dict(
        filestate.__salt__, {"file.user_to_uid": mock_uid}
    ), patch.dict(filestate.__salt__, {"file.group_to_gid": mock_gid}), patch.dict(
        filestate.__salt__, {"file.is_hardlink": mock_f}
    ), patch.object(
        os.path, "isfile", mock_t
    ):

        expected = "File exists where the hard link {} should be".format(name)
        ret = return_val(comment=expected, name=name)
        assert filestate.hardlink(name, target, user=user, group=group) == ret

    # Try overwrite link with same
    with patch.dict(filestate.__salt__, patches), patch.dict(
        filestate.__salt__, {"file.user_to_uid": mock_uid}
    ), patch.dict(filestate.__salt__, {"file.group_to_gid": mock_gid}), patch.dict(
        filestate.__salt__, {"file.is_hardlink": mock_t}
    ), patch.dict(
        filestate.__salt__, {"file.stats": mock_stats}
    ), patch.object(
        os.path, "isfile", mock_f
    ):

        expected = "Target of hard link {} is already pointing to {}".format(
            name, target
        )
        ret = return_val(result=True, comment=expected, name=name)
        assert filestate.hardlink(name, target, user=user, group=group) == ret

    # Really overwrite link with same
    with patch.dict(filestate.__salt__, patches), patch.dict(
        filestate.__salt__, {"file.user_to_uid": mock_uid}
    ), patch.dict(filestate.__salt__, {"file.group_to_gid": mock_gid}), patch.dict(
        filestate.__salt__, {"file.is_hardlink": mock_t}
    ), patch.dict(
        filestate.__salt__, {"file.link": mock_t}
    ), patch.dict(
        filestate.__salt__, {"file.stats": mock_nothing}
    ), patch.object(
        os, "remove", mock_t
    ), patch.object(
        os.path, "isfile", mock_f
    ):

        expected = "Set target of hard link {} -> {}".format(name, target)
        changes = dict(new=name)
        ret = return_val(result=True, comment=expected, name=name, changes=changes)
        assert filestate.hardlink(name, target, user=user, group=group) == ret

    # Fail at overwriting link with same
    with patch.dict(filestate.__salt__, patches), patch.dict(
        filestate.__salt__, {"file.user_to_uid": mock_uid}
    ), patch.dict(filestate.__salt__, {"file.group_to_gid": mock_gid}), patch.dict(
        filestate.__salt__, {"file.is_hardlink": mock_t}
    ), patch.dict(
        filestate.__salt__, {"file.link": mock_execerror}
    ), patch.dict(
        filestate.__salt__, {"file.stats": mock_nothing}
    ), patch.object(
        os, "remove", mock_t
    ), patch.object(
        os.path, "isfile", mock_f
    ):

        expected = "Unable to set target of hard link {} -> {}: {}".format(
            name, target, ""
        )
        ret = return_val(result=False, comment=expected, name=name)
        assert filestate.hardlink(name, target, user=user, group=group) == ret

    # Make new link
    with patch.dict(filestate.__salt__, patches), patch.dict(
        filestate.__salt__, {"file.user_to_uid": mock_uid}
    ), patch.dict(filestate.__salt__, {"file.group_to_gid": mock_gid}), patch.dict(
        filestate.__salt__, {"file.is_hardlink": mock_f}
    ), patch.dict(
        filestate.__salt__, {"file.link": mock_f}
    ), patch.dict(
        filestate.__salt__, {"file.stats": mock_nothing}
    ), patch.object(
        os, "remove", mock_t
    ), patch.object(
        os.path, "isfile", mock_f
    ):

        expected = "Created new hard link {} -> {}".format(name, target)
        changes = dict(new=name)
        ret = return_val(result=True, comment=expected, name=name, changes=changes)
        assert filestate.hardlink(name, target, user=user, group=group) == ret

    # Fail while making new link
    with patch.dict(filestate.__salt__, patches), patch.dict(
        filestate.__salt__, {"file.user_to_uid": mock_uid}
    ), patch.dict(filestate.__salt__, {"file.group_to_gid": mock_gid}), patch.dict(
        filestate.__salt__, {"file.is_hardlink": mock_f}
    ), patch.dict(
        filestate.__salt__, {"file.link": mock_execerror}
    ), patch.dict(
        filestate.__salt__, {"file.stats": mock_nothing}
    ), patch.object(
        os, "remove", mock_t
    ), patch.object(
        os.path, "isfile", mock_f
    ):

        expected = "Unable to create new hard link {} -> {}: {}".format(
            name, target, ""
        )
        ret = return_val(result=False, comment=expected, name=name)
        assert filestate.hardlink(name, target, user=user, group=group) == ret

    # Force making new link over file
    with patch.dict(filestate.__salt__, patches), patch.dict(
        filestate.__salt__, {"file.user_to_uid": mock_uid}
    ), patch.dict(filestate.__salt__, {"file.group_to_gid": mock_gid}), patch.dict(
        filestate.__salt__, {"file.is_hardlink": mock_f}
    ), patch.dict(
        filestate.__salt__, {"file.link": mock_t}
    ), patch.dict(
        filestate.__salt__, {"file.stats": mock_nothing}
    ), patch.object(
        os, "remove", mock_t
    ), patch.object(
        os.path, "isfile", mock_t
    ):

        expected = "Created new hard link {} -> {}".format(name, target)
        changes = dict(new=name)
        changes["forced"] = "File for hard link was forcibly replaced"
        ret = return_val(result=True, comment=expected, name=name, changes=changes)
        assert (
            filestate.hardlink(name, target, user=user, force=True, group=group) == ret
        )

    # Force making new link over file but error out
    with patch.dict(filestate.__salt__, patches), patch.dict(
        filestate.__salt__, {"file.user_to_uid": mock_uid}
    ), patch.dict(filestate.__salt__, {"file.group_to_gid": mock_gid}), patch.dict(
        filestate.__salt__, {"file.is_hardlink": mock_f}
    ), patch.dict(
        filestate.__salt__, {"file.link": mock_execerror}
    ), patch.dict(
        filestate.__salt__, {"file.stats": mock_nothing}
    ), patch.object(
        os, "remove", mock_t
    ), patch.object(
        os.path, "isfile", mock_t
    ):

        expected = "Unable to create new hard link {} -> {}: {}".format(
            name, target, ""
        )
        changes = dict(forced="File for hard link was forcibly replaced")
        ret = return_val(result=False, comment=expected, name=name, changes=changes)
        assert (
            filestate.hardlink(name, target, user=user, force=True, group=group) == ret
        )

    patches = {}
    patches["file.user_to_uid"] = mock_empty
    patches["file.group_to_gid"] = mock_empty
    patches["file.is_hardlink"] = mock_t
    patches["file.stats"] = mock_empty

    # Make new link when group is None and file.gid_to_group is unavailable
    with patch.dict(filestate.__salt__, patches), patch.dict(
        filestate.__salt__, {"file.user_to_uid": mock_uid}
    ), patch.dict(filestate.__salt__, {"file.group_to_gid": mock_gid}), patch.dict(
        filestate.__salt__, {"file.is_hardlink": mock_f}
    ), patch.dict(
        filestate.__salt__, {"file.link": mock_f}
    ), patch.dict(
        filestate.__salt__, {"file.stats": mock_nothing}
    ), patch.object(
        os, "remove", mock_t
    ), patch.object(
        os.path, "isfile", mock_f
    ):

        group = None
        expected = "Created new hard link {} -> {}".format(name, target)
        changes = dict(new=name)
        ret = return_val(result=True, comment=expected, name=name, changes=changes)
        assert filestate.hardlink(name, target, user=user, group=group) == ret
