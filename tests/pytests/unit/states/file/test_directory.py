import contextlib
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
            f'The directory "{name}" will be changed',
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
            comt = f"Specified file {name} is not an absolute path"
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
                    comt = f"Specified location {name} exists and is a file"
                    ret.update({"comment": comt})
                    assert filestate.directory(name, user=user, group=group) == ret

                with patch.object(os.path, "islink", mock_t):
                    comt = f"Specified location {name} exists and is a symlink"
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
                        comt = f"No directory to create {name} in"
                        ret.update({"comment": comt, "result": False})
                        assert filestate.directory(name, user=user, group=group) == ret

                    if salt.utils.platform.is_windows():
                        isdir_side_effect = [False, True, False]
                    else:
                        isdir_side_effect = [True, False, True, False]
                    with patch.object(
                        os.path, "isdir", MagicMock(side_effect=isdir_side_effect)
                    ):
                        comt = f"Failed to create directory {name}"
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

                    comt = f"Directory {name} updated"
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


def test_directory_test_mode_user_group_not_present():
    name = "/etc/testdir"
    user = "salt"
    group = "saltstack"
    if salt.utils.platform.is_windows():
        name = name.replace("/", "\\")

    ret = {
        "name": name,
        "result": None,
        "comment": "",
        "changes": {name: {"directory": "new"}},
    }

    if salt.utils.platform.is_windows():
        comt = 'The directory "{}" will be changed' "".format(name)
    else:
        comt = "The following files will be changed:\n{}:" " directory - new\n".format(
            name
        )
    ret["comment"] = comt

    mock_f = MagicMock(return_value=False)
    mock_uid = MagicMock(
        side_effect=[
            "",
            "U12",
            "",
        ]
    )
    mock_gid = MagicMock(
        side_effect=[
            "G12",
            "",
            "",
        ]
    )
    mock_error = CommandExecutionError
    with patch.dict(
        filestate.__salt__,
        {
            "file.user_to_uid": mock_uid,
            "file.group_to_gid": mock_gid,
            "file.stats": mock_f,
        },
    ), patch("salt.utils.win_dacl.get_sid", mock_error), patch.object(
        os.path, "isdir", mock_f
    ), patch.dict(
        filestate.__opts__, {"test": True}
    ):
        assert filestate.directory(name, user=user, group=group) == ret
        assert filestate.directory(name, user=user, group=group) == ret
        assert filestate.directory(name, user=user, group=group) == ret


def _check_perms_populating(*args, **kwargs):
    """
    Stand-in for file.check_perms that records a per-path change into the
    passed-in ret, mimicking how the real function repopulates ret["changes"]
    for every file/dir visited during a recursive run. Handles both the posix
    positional call (path, ret, ...) and the Windows keyword call
    (path=, ret=, ...).
    """
    if kwargs:
        path = kwargs["path"]
        cur = kwargs["ret"]
    else:
        path = args[0]
        cur = args[1]
    cur["changes"][path] = {"mode": "0755"}
    if salt.utils.platform.is_windows():
        return cur
    return cur, ""


def _directory_recurse_patches(name):
    """
    Common patches to drive file.directory into the recursive check_perms
    loop deterministically: force a pending change so the no-change early
    return is skipped, make the target look like an existing directory, and
    feed the walk a single child file and child dir.
    """
    tchanges = (None, "", {name: {"directory": "new"}})
    return [
        patch.dict(
            filestate.__salt__,
            {"file.check_perms": MagicMock(side_effect=_check_perms_populating)},
        ),
        patch("salt.states.file._check_directory", MagicMock(return_value=tchanges)),
        patch(
            "salt.states.file._check_directory_win", MagicMock(return_value=tchanges)
        ),
        patch(
            "salt.states.file._depth_limited_walk",
            MagicMock(return_value=[(name, ["child_dir"], ["child_file"])]),
        ),
        patch("salt.utils.win_dacl.get_sid", MagicMock()),
        patch(
            "salt.utils.win_functions.get_current_user",
            MagicMock(return_value="username"),
        ),
        patch.object(os.path, "isdir", MagicMock(return_value=True)),
        patch.object(os.path, "isfile", MagicMock(return_value=False)),
        patch.object(os.path, "isabs", MagicMock(return_value=True)),
    ]


def test_directory_recurse_silent_suppresses_changes_60597():
    """
    Regression test for #60597: with ``silent`` in the recurse set, the
    individual per-file/per-dir change notifications produced by the
    check_perms loop must be replaced by the single silence marker.

    Production-exact call shape: recurse=["mode", "silent"] (the ``silent``
    flag lives inside ``recurse``, not at the state top level).
    """
    name = "/etc/testdir"
    if salt.utils.platform.is_windows():
        name = name.replace("/", "\\")

    with contextlib.ExitStack() as stack:
        for ctx in _directory_recurse_patches(name):
            stack.enter_context(ctx)
        # silent is passed inside recurse, alongside mode
        ret = filestate.directory(name, recurse=["mode", "silent"])

    assert ret["changes"] == {"recursion": "Changes silenced"}


def test_directory_recurse_without_silent_still_reports_changes_60597():
    """
    Must-not-regress sibling for #60597: without ``silent`` in the recurse
    set, the per-file/per-dir changes gathered by the check_perms loop must
    still be reported. This passes both with and without the fix; it guards
    against the silence marker leaking into the ordinary recurse path.
    """
    name = "/etc/testdir"
    if salt.utils.platform.is_windows():
        name = name.replace("/", "\\")

    with contextlib.ExitStack() as stack:
        for ctx in _directory_recurse_patches(name):
            stack.enter_context(ctx)
        # no silent this time, only mode
        ret = filestate.directory(name, recurse=["mode"])

    assert os.path.join(name, "child_file") in ret["changes"]
    assert os.path.join(name, "child_dir") in ret["changes"]
    assert "recursion" not in ret["changes"]


def test_directory_recurse_silent_preserves_clean_removed_60597():
    """
    Peripheral coverage for #60597: the silence reset runs after the
    check_perms loop but before the ``clean`` block, so entries recorded by
    clean (``removed``) must still survive alongside the silence marker.
    """
    name = "/etc/testdir"
    if salt.utils.platform.is_windows():
        name = name.replace("/", "\\")
    removed = [os.path.join(name, "stale")]

    with contextlib.ExitStack() as stack:
        for ctx in _directory_recurse_patches(name):
            stack.enter_context(ctx)
        stack.enter_context(
            patch("salt.states.file._gen_keep_files", MagicMock(return_value=set()))
        )
        stack.enter_context(
            patch("salt.states.file._clean_dir", MagicMock(return_value=removed))
        )
        # silent inside recurse, together with clean=True
        ret = filestate.directory(name, recurse=["mode", "silent"], clean=True)

    assert ret["changes"] == {"recursion": "Changes silenced", "removed": removed}
