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


# 'managed' function tests: 1
def test_file_managed_should_fall_back_to_binary():
    expected_contents = b"\x8b"
    filename = "/tmp/blarg"
    mock_manage = MagicMock(return_value={"fnord": "fnords"})
    with patch("salt.states.file._load_accumulators", MagicMock(return_value=([], []))):
        with patch.dict(
            filestate.__salt__,
            {
                "file.get_managed": MagicMock(return_value=["", "", ""]),
                "file.source_list": MagicMock(return_value=["", ""]),
                "file.manage_file": mock_manage,
                "pillar.get": MagicMock(return_value=expected_contents),
            },
        ):
            ret = filestate.managed(filename, contents_pillar="fnord", encoding="utf-8")
            actual_contents = mock_manage.call_args[0][14]
            assert actual_contents == expected_contents


def test_managed():
    """
    Test to manage a given file, this function allows for a file to be
    downloaded from the salt master and potentially run through a templating
    system.
    """
    with patch("salt.states.file._load_accumulators", MagicMock(return_value=([], []))):
        name = "/etc/grub.conf"
        user = "salt"
        group = "saltstack"

        ret = {"name": name, "result": False, "comment": "", "changes": {}}

        mock_t = MagicMock(return_value=True)
        mock_f = MagicMock(return_value=False)
        mock_cmd_fail = MagicMock(return_value={"retcode": 1})
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
                "G12",
                "G12",
                "G12",
                "G12",
                "G12",
                "G12",
            ]
        )
        mock_if = MagicMock(
            side_effect=[True, False, False, False, False, False, False, False, False]
        )
        if salt.utils.platform.is_windows():
            mock_ret = MagicMock(return_value=ret)
        else:
            mock_ret = MagicMock(return_value=(ret, None))
        mock_dict = MagicMock(return_value={})
        mock_cp = MagicMock(side_effect=[Exception, True])
        mock_ex = MagicMock(
            side_effect=[Exception, {"changes": {name: name}}, True, Exception]
        )
        mock_mng = MagicMock(
            side_effect=[
                Exception,
                ("", "", ""),
                ("", "", ""),
                ("", "", True),
                ("", "", True),
                ("", "", ""),
                ("", "", ""),
                ("", "", ""),
            ]
        )
        mock_file = MagicMock(
            side_effect=[
                CommandExecutionError,
                ("", ""),
                ("", ""),
                ("", ""),
                ("", ""),
                ("", ""),
                ("", ""),
                ("", ""),
                ("", ""),
                ("", ""),
            ]
        )
        with patch.dict(
            filestate.__salt__,
            {
                "config.manage_mode": mock_t,
                "file.user_to_uid": mock_uid,
                "file.group_to_gid": mock_gid,
                "file.file_exists": mock_if,
                "file.check_perms": mock_ret,
                "file.check_managed_changes": mock_dict,
                "file.get_managed": mock_mng,
                "file.source_list": mock_file,
                "file.copy": mock_cp,
                "file.manage_file": mock_ex,
                "cmd.run_all": mock_cmd_fail,
            },
        ):
            comt = "Destination file name is required"
            ret.update({"comment": comt, "name": "", "changes": {}})
            assert filestate.managed("") == ret

            with patch.object(os.path, "isfile", mock_f):
                comt = "File {} is not present and is not set for creation".format(name)
                ret.update({"comment": comt, "name": name, "result": True})
                assert filestate.managed(name, create=False) == ret

            # Group argument is ignored on Windows systems. Group is set to
            # user
            if salt.utils.platform.is_windows():
                comt = "User salt is not available Group salt is not available"
            else:
                comt = "User salt is not available Group saltstack is not available"
            ret.update({"comment": comt, "result": False})
            assert filestate.managed(name, user=user, group=group) == ret

            with patch.object(os.path, "isabs", mock_f):
                comt = "Specified file {} is not an absolute path".format(name)
                ret.update({"comment": comt, "result": False})
                assert filestate.managed(name, user=user, group=group) == ret

            with patch.object(os.path, "isabs", mock_t):
                with patch.object(os.path, "isdir", mock_t):
                    comt = "Specified target {} is a directory".format(name)
                    ret.update({"comment": comt})
                    assert filestate.managed(name, user=user, group=group) == ret

                with patch.object(os.path, "isdir", mock_f):
                    comt = "Context must be formed as a dict"
                    ret.update({"comment": comt})
                    assert (
                        filestate.managed(name, user=user, group=group, context=True)
                        == ret
                    )

                    comt = "Defaults must be formed as a dict"
                    ret.update({"comment": comt})
                    assert (
                        filestate.managed(name, user=user, group=group, defaults=True)
                        == ret
                    )

                    comt = (
                        "Only one of 'contents', 'contents_pillar', "
                        "and 'contents_grains' is permitted"
                    )
                    ret.update({"comment": comt})
                    assert (
                        filestate.managed(
                            name,
                            user=user,
                            group=group,
                            contents="A",
                            contents_grains="B",
                            contents_pillar="C",
                        )
                        == ret
                    )

                    with patch.object(os.path, "exists", mock_t):
                        with patch.dict(filestate.__opts__, {"test": True}):
                            comt = "File {} not updated".format(name)
                            ret.update({"comment": comt})
                            assert (
                                filestate.managed(
                                    name, user=user, group=group, replace=False
                                )
                                == ret
                            )

                            comt = "The file {} is in the correct state".format(name)
                            ret.update({"comment": comt, "result": True})
                            assert (
                                filestate.managed(
                                    name, user=user, contents="A", group=group
                                )
                                == ret
                            )

                    with patch.object(os.path, "exists", mock_f):
                        with patch.dict(filestate.__opts__, {"test": False}):
                            comt = "Unable to manage file: "
                            ret.update({"comment": comt, "result": False})
                            assert (
                                filestate.managed(
                                    name, user=user, group=group, contents="A"
                                )
                                == ret
                            )

                            comt = "Unable to manage file: "
                            ret.update({"comment": comt, "result": False})
                            assert (
                                filestate.managed(
                                    name, user=user, group=group, contents="A"
                                )
                                == ret
                            )

                            with patch.object(
                                salt.utils.files, "mkstemp", return_value=name
                            ):
                                comt = "Unable to copy file {0} to {0}: ".format(name)
                                ret.update({"comment": comt, "result": False})
                                assert (
                                    filestate.managed(
                                        name, user=user, group=group, check_cmd="A"
                                    )
                                    == ret
                                )

                            comt = "Unable to check_cmd file: "
                            ret.update({"comment": comt, "result": False})
                            assert (
                                filestate.managed(
                                    name, user=user, group=group, check_cmd="A"
                                )
                                == ret
                            )

                            comt = "check_cmd execution failed"
                            ret.update(
                                {"comment": comt, "result": False, "skip_watch": True}
                            )
                            assert (
                                filestate.managed(
                                    name, user=user, group=group, check_cmd="A"
                                )
                                == ret
                            )

                            comt = "check_cmd execution failed"
                            ret.update({"comment": True, "changes": {}})
                            ret.pop("skip_watch", None)
                            assert (
                                filestate.managed(name, user=user, group=group) == ret
                            )

                            assert filestate.managed(name, user=user, group=group)

                            comt = "Unable to manage file: "
                            ret.update({"comment": comt})
                            assert (
                                filestate.managed(name, user=user, group=group) == ret
                            )

                    if salt.utils.platform.is_windows():
                        mock_ret = MagicMock(return_value=ret)
                        comt = "File {} not updated".format(name)
                    else:
                        perms = {"luser": user, "lmode": "0644", "lgroup": group}
                        mock_ret = MagicMock(return_value=(ret, perms))
                        comt = (
                            "File {} will be updated with "
                            "permissions 0400 from its current "
                            "state of 0644".format(name)
                        )

                    with patch.dict(filestate.__salt__, {"file.check_perms": mock_ret}):
                        with patch.object(os.path, "exists", mock_t):
                            with patch.dict(filestate.__opts__, {"test": True}):
                                ret.update({"comment": comt})
                                if salt.utils.platform.is_windows():
                                    assert (
                                        filestate.managed(name, user=user, group=group)
                                        == ret
                                    )
                                else:
                                    assert (
                                        filestate.managed(
                                            name, user=user, group=group, mode=400
                                        )
                                        == ret
                                    )

                    # Replace is False, test is True, mode is empty
                    # should return "File not updated"
                    #  https://github.com/saltstack/salt/issues/59276
                    if salt.utils.platform.is_windows():
                        mock_ret = MagicMock(return_value=ret)
                    else:
                        perms = {"luser": user, "lmode": "0644", "lgroup": group}
                        mock_ret = MagicMock(return_value=(ret, perms))
                    comt = "File {} not updated".format(name)
                    with patch.dict(filestate.__salt__, {"file.check_perms": mock_ret}):
                        with patch.object(os.path, "exists", mock_t):
                            with patch.dict(filestate.__opts__, {"test": True}):
                                ret.update({"comment": comt})
                                if salt.utils.platform.is_windows():
                                    assert (
                                        filestate.managed(name, user=user, group=group)
                                        == ret
                                    )
                                else:
                                    assert (
                                        filestate.managed(name, user=user, group=group)
                                        == ret
                                    )


def test_managed_test_mode_user_group_not_present():
    """
    Test file managed in test mode with no user or group existing
    """
    filename = "/tmp/managed_no_user_group_test_mode"
    with patch.dict(
        filestate.__salt__,
        {
            "file.group_to_gid": MagicMock(side_effect=["1234", "", ""]),
            "file.user_to_uid": MagicMock(side_effect=["", "4321", ""]),
        },
    ), patch.dict(filestate.__opts__, {"test": True}):
        ret = filestate.managed(
            filename, group="nonexistinggroup", user="nonexistinguser"
        )
        assert ret["result"] is not False
        assert "is not available" not in ret["comment"]

        ret = filestate.managed(
            filename, group="nonexistinggroup", user="nonexistinguser"
        )
        assert ret["result"] is not False
        assert "is not available" not in ret["comment"]

        ret = filestate.managed(
            filename, group="nonexistinggroup", user="nonexistinguser"
        )
        assert ret["result"] is not False
        assert "is not available" not in ret["comment"]
