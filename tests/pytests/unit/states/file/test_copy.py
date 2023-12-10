import logging
import os
import shutil

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


# 'copy' function tests: 1
def test_copy(tmp_path):
    """
    Test if the source file exists on the system, copy it to the named file.
    """
    name = str(tmp_path / "salt")
    source = str(tmp_path / "salt" / "salt")
    user = "salt"
    group = "saltstack"

    ret = {"name": name, "result": False, "comment": "", "changes": {}}

    comt = "Must provide name to file.copy"
    ret.update({"comment": comt, "name": ""})
    assert filestate.copy_("", source) == ret

    mock_t = MagicMock(return_value=True)
    mock_f = MagicMock(return_value=False)
    mock_uid = MagicMock(side_effect=["", "1000", "1000"])
    mock_gid = MagicMock(side_effect=["", "1000", "1000"])
    mock_user = MagicMock(return_value=user)
    mock_grp = MagicMock(return_value=group)
    mock_io = MagicMock(side_effect=IOError)
    with patch.object(os.path, "isabs", mock_f):
        comt = "Specified file {} is not an absolute path".format(name)
        ret.update({"comment": comt, "name": name})
        assert filestate.copy_(name, source) == ret

    with patch.object(os.path, "isabs", mock_t):
        with patch.object(os.path, "exists", mock_f):
            comt = 'Source file "{}" is not present'.format(source)
            ret.update({"comment": comt, "result": False})
            assert filestate.copy_(name, source) == ret

        with patch.object(os.path, "exists", mock_t):
            with patch.dict(
                filestate.__salt__,
                {
                    "file.user_to_uid": mock_uid,
                    "file.group_to_gid": mock_gid,
                    "file.get_user": mock_user,
                    "file.get_group": mock_grp,
                    "file.get_mode": mock_grp,
                    "file.check_perms": mock_t,
                },
            ):

                # Group argument is ignored on Windows systems. Group is set
                # to user
                if salt.utils.platform.is_windows():
                    comt = "User salt is not available Group salt is not available"
                else:
                    comt = "User salt is not available Group saltstack is not available"
                ret.update({"comment": comt, "result": False})
                assert filestate.copy_(name, source, user=user, group=group) == ret

                comt1 = (
                    'Failed to delete "{}" in preparation for'
                    " forced move".format(name)
                )
                comt2 = (
                    'The target file "{}" exists and will not be '
                    "overwritten".format(name)
                )
                comt3 = 'File "{}" is set to be copied to "{}"'.format(source, name)
                with patch.object(os.path, "isdir", mock_f):
                    with patch.object(os.path, "lexists", mock_t):
                        with patch.dict(filestate.__opts__, {"test": False}):
                            with patch.dict(
                                filestate.__salt__, {"file.remove": mock_io}
                            ):
                                ret.update({"comment": comt1, "result": False})
                                assert (
                                    filestate.copy_(
                                        name, source, preserve=True, force=True
                                    )
                                    == ret
                                )

                            with patch.object(os.path, "isfile", mock_t):
                                ret.update({"comment": comt2, "result": True})
                                assert (
                                    filestate.copy_(name, source, preserve=True) == ret
                                )

                    with patch.object(os.path, "lexists", mock_f):
                        with patch.dict(filestate.__opts__, {"test": True}):
                            ret.update({"comment": comt3, "result": None})
                            assert filestate.copy_(name, source, preserve=True) == ret

                        with patch.dict(filestate.__opts__, {"test": False}):
                            comt = "The target directory {} is not present".format(
                                tmp_path
                            )
                            ret.update({"comment": comt, "result": False})
                            assert filestate.copy_(name, source, preserve=True) == ret

            check_perms_ret = {
                "name": name,
                "changes": {},
                "comment": [],
                "result": True,
            }
            check_perms_perms = {}

            if salt.utils.platform.is_windows():
                mock_check_perms = MagicMock(return_value=check_perms_ret)
            else:
                mock_check_perms = MagicMock(
                    return_value=(check_perms_ret, check_perms_perms)
                )
            with patch.dict(
                filestate.__salt__,
                {
                    "file.user_to_uid": mock_uid,
                    "file.group_to_gid": mock_gid,
                    "file.get_user": mock_user,
                    "file.get_group": mock_grp,
                    "file.get_mode": mock_grp,
                    "file.check_perms": mock_check_perms,
                },
            ):

                comt = 'Copied "{}" to "{}"'.format(source, name)
                with patch.dict(filestate.__opts__, {"user": "salt"}), patch.object(
                    os.path, "isdir", mock_t
                ), patch.object(os.path, "lexists", mock_f), patch.dict(
                    filestate.__opts__, {"test": False}
                ), patch.dict(
                    filestate.__salt__, {"file.remove": mock_io}
                ), patch.object(
                    shutil, "copytree", MagicMock()
                ):
                    group = None
                    ret.update(
                        {
                            "comment": comt,
                            "result": True,
                            "changes": {name: source},
                        }
                    )
                    res = filestate.copy_(name, source, group=group, preserve=False)
                    assert res == ret

                comt = 'Copied "{}" to "{}"'.format(source, name)
                with patch.dict(filestate.__opts__, {"user": "salt"}), patch.object(
                    os.path, "isdir", MagicMock(side_effect=[False, True, False])
                ), patch.object(os.path, "lexists", mock_f), patch.dict(
                    filestate.__opts__, {"test": False}
                ), patch.dict(
                    filestate.__salt__, {"file.remove": mock_io}
                ), patch.object(
                    shutil, "copy", MagicMock()
                ):
                    group = None
                    ret.update(
                        {
                            "comment": comt,
                            "result": True,
                            "changes": {name: source},
                        }
                    )
                    res = filestate.copy_(name, source, group=group, preserve=False)
                    assert res == ret


def test_copy_test_mode_user_group_not_present():
    """
    Test file copy in test mode with no user or group existing
    """
    source = "/tmp/src_copy_no_user_group_test_mode"
    filename = "/tmp/copy_no_user_group_test_mode"
    with patch.dict(
        filestate.__salt__,
        {
            "file.group_to_gid": MagicMock(side_effect=["1234", "", ""]),
            "file.user_to_uid": MagicMock(side_effect=["", "4321", ""]),
            "file.get_mode": MagicMock(return_value="0644"),
        },
    ), patch.dict(filestate.__opts__, {"test": True}), patch.object(
        os.path, "exists", return_value=True
    ):
        ret = filestate.copy_(
            source, filename, group="nonexistinggroup", user="nonexistinguser"
        )
        assert ret["result"] is not False
        assert "is not available" not in ret["comment"]

        ret = filestate.copy_(
            source, filename, group="nonexistinggroup", user="nonexistinguser"
        )
        assert ret["result"] is not False
        assert "is not available" not in ret["comment"]

        ret = filestate.copy_(
            source, filename, group="nonexistinggroup", user="nonexistinguser"
        )
        assert ret["result"] is not False
        assert "is not available" not in ret["comment"]
