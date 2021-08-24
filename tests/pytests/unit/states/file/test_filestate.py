import logging
import os
import plistlib
import pprint

import msgpack
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
from tests.support.mock import MagicMock, Mock, patch

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


def test_serialize():
    def returner(contents, *args, **kwargs):
        returner.returned = contents

    returner.returned = None

    with patch.dict(filestate.__salt__, {"file.manage_file": returner}):

        dataset = {"foo": True, "bar": 42, "baz": [1, 2, 3], "qux": 2.0}

        # If no serializer passed, result should be serialized as YAML
        filestate.serialize("/tmp", dataset)
        assert salt.utils.yaml.safe_load(returner.returned) == dataset

        # If serializer and formatter passed, state should not proceed.
        ret = filestate.serialize("/tmp", dataset, serializer="yaml", formatter="json")
        assert ret["result"] is False
        assert ret["comment"] == "Only one of serializer and formatter are allowed", ret

        # YAML
        filestate.serialize("/tmp", dataset, serializer="yaml")
        assert salt.utils.yaml.safe_load(returner.returned) == dataset
        filestate.serialize("/tmp", dataset, formatter="yaml")
        assert salt.utils.yaml.safe_load(returner.returned) == dataset

        # JSON
        filestate.serialize("/tmp", dataset, serializer="json")
        assert salt.utils.json.loads(returner.returned) == dataset
        filestate.serialize("/tmp", dataset, formatter="json")
        assert salt.utils.json.loads(returner.returned) == dataset

        # plist
        filestate.serialize("/tmp", dataset, serializer="plist")
        assert plistlib.loads(returner.returned) == dataset
        filestate.serialize("/tmp", dataset, formatter="plist")
        assert plistlib.loads(returner.returned) == dataset

        # Python
        filestate.serialize("/tmp", dataset, serializer="python")
        assert returner.returned == pprint.pformat(dataset) + "\n"
        filestate.serialize("/tmp", dataset, formatter="python")
        assert returner.returned == pprint.pformat(dataset) + "\n"

        # msgpack
        filestate.serialize("/tmp", dataset, serializer="msgpack")
        assert returner.returned == msgpack.packb(dataset)
        filestate.serialize("/tmp", dataset, formatter="msgpack")
        assert returner.returned == msgpack.packb(dataset)

        mock_serializer = Mock(return_value="")
        with patch.dict(filestate.__serializers__, {"json.serialize": mock_serializer}):
            # Test with "serializer" arg
            filestate.serialize(
                "/tmp", dataset, formatter="json", serializer_opts=[{"indent": 8}]
            )
            mock_serializer.assert_called_with(
                dataset, indent=8, separators=(",", ": "), sort_keys=True
            )
            # Test with "formatter" arg
            mock_serializer.reset_mock()
            filestate.serialize(
                "/tmp", dataset, formatter="json", serializer_opts=[{"indent": 8}]
            )
            mock_serializer.assert_called_with(
                dataset, indent=8, separators=(",", ": "), sort_keys=True
            )


def test_contents_and_contents_pillar():
    def returner(contents, *args, **kwargs):
        returner.returned = contents

    returner.returned = None

    manage_mode_mock = MagicMock()
    with patch.dict(
        filestate.__salt__,
        {"file.manage_file": returner, "config.manage_mode": manage_mode_mock},
    ):

        ret = filestate.managed("/tmp/foo", contents="hi", contents_pillar="foo:bar")
        assert not ret["result"]


def test_contents_pillar_doesnt_add_more_newlines():
    # make sure the newline
    pillar_value = "i am the pillar value{}".format(os.linesep)

    returner = MagicMock(return_value=None)
    path = "/tmp/foo"
    pillar_path = "foo:bar"

    # the values don't matter here
    pillar_mock = MagicMock(return_value=pillar_value)
    with patch.dict(
        filestate.__salt__,
        {
            "file.manage_file": returner,
            "config.manage_mode": MagicMock(),
            "file.source_list": MagicMock(return_value=[None, None]),
            "file.get_managed": MagicMock(return_value=[None, None, None]),
            "pillar.get": pillar_mock,
        },
    ):

        ret = filestate.managed(path, contents_pillar=pillar_path)

        # make sure no errors are returned
        assert ret is None

        # Make sure the contents value matches the expected value.
        # returner.call_args[0] will be an args tuple containing all the args
        # passed to the mocked returner for file.manage_file. Any changes to
        # the arguments for file.manage_file may make this assertion fail.
        # If the test is failing, check the position of the "contents" param
        # in the manage_file() function in salt/modules/file.py, the fix is
        # likely as simple as updating the 2nd index below.
        assert returner.call_args[0][-5] == pillar_value


# 'exists' function tests: 1
def test_exists():
    """
    Test to verify that the named file or directory is present or exists.
    """
    name = "/etc/grub.conf"

    ret = {"name": name, "result": False, "comment": "", "changes": {}}

    mock_t = MagicMock(return_value=True)
    mock_f = MagicMock(return_value=False)

    comt = "Must provide name to file.exists"
    ret.update({"comment": comt, "name": ""})
    assert filestate.exists("") == ret

    with patch.object(os.path, "exists", mock_f):
        comt = "Specified path {} does not exist".format(name)
        ret.update({"comment": comt, "name": name})
        assert filestate.exists(name) == ret

    with patch.object(os.path, "exists", mock_t):
        comt = "Path {} exists".format(name)
        ret.update({"comment": comt, "result": True})
        assert filestate.exists(name) == ret


# 'missing' function tests: 1
def test_missing():
    """
    Test to verify that the named file or directory is missing.
    """
    name = "/etc/grub.conf"

    ret = {"name": name, "result": False, "comment": "", "changes": {}}

    mock_t = MagicMock(return_value=True)
    mock_f = MagicMock(return_value=False)

    comt = "Must provide name to file.missing"
    ret.update({"comment": comt, "name": "", "changes": {}})
    assert filestate.missing("") == ret

    with patch.object(os.path, "exists", mock_t):
        comt = "Specified path {} exists".format(name)
        ret.update({"comment": comt, "name": name})
        assert filestate.missing(name) == ret

    with patch.object(os.path, "exists", mock_f):
        comt = "Path {} is missing".format(name)
        ret.update({"comment": comt, "result": True})
        assert filestate.missing(name) == ret


# 'recurse' function tests: 1
def test_recurse():
    """
    Test to recurse through a subdirectory on the master
    and copy said subdirectory over to the specified path.
    """
    name = "/opt/code/flask"
    source = "salt://code/flask"
    user = "salt"
    group = "saltstack"
    if salt.utils.platform.is_windows():
        name = name.replace("/", "\\")

    ret = {"name": name, "result": False, "comment": "", "changes": {}}

    comt = (
        "'mode' is not allowed in 'file.recurse'."
        " Please use 'file_mode' and 'dir_mode'."
    )
    ret.update({"comment": comt})
    assert filestate.recurse(name, source, mode="W") == ret

    mock_t = MagicMock(return_value=True)
    mock_f = MagicMock(return_value=False)
    mock_uid = MagicMock(return_value="")
    mock_gid = MagicMock(return_value="")
    mock_l = MagicMock(return_value=[])
    mock_emt = MagicMock(side_effect=[[], ["code/flask"], ["code/flask"]])
    mock_lst = MagicMock(
        side_effect=[CommandExecutionError, (source, ""), (source, ""), (source, "")]
    )
    with patch.dict(
        filestate.__salt__,
        {
            "config.manage_mode": mock_t,
            "file.user_to_uid": mock_uid,
            "file.group_to_gid": mock_gid,
            "file.source_list": mock_lst,
            "cp.list_master_dirs": mock_emt,
            "cp.list_master": mock_l,
        },
    ):

        # Group argument is ignored on Windows systems. Group is set to user
        if salt.utils.platform.is_windows():
            comt = "User salt is not available Group salt is not available"
        else:
            comt = "User salt is not available Group saltstack is not available"
        ret.update({"comment": comt})
        assert filestate.recurse(name, source, user=user, group=group) == ret

        with patch.object(os.path, "isabs", mock_f):
            comt = "Specified file {} is not an absolute path".format(name)
            ret.update({"comment": comt})
            assert filestate.recurse(name, source) == ret

        with patch.object(os.path, "isabs", mock_t):
            comt = "Invalid source '1' (must be a salt:// URI)"
            ret.update({"comment": comt})
            assert filestate.recurse(name, 1) == ret

            comt = "Invalid source '//code/flask' (must be a salt:// URI)"
            ret.update({"comment": comt})
            assert filestate.recurse(name, "//code/flask") == ret

            comt = "Recurse failed: "
            ret.update({"comment": comt})
            assert filestate.recurse(name, source) == ret

            comt = (
                "The directory 'code/flask' does not exist"
                " on the salt fileserver in saltenv 'base'"
            )
            ret.update({"comment": comt})
            assert filestate.recurse(name, source) == ret

            with patch.object(os.path, "isdir", mock_f):
                with patch.object(os.path, "exists", mock_t):
                    comt = "The path {} exists and is not a directory".format(name)
                    ret.update({"comment": comt})
                    assert filestate.recurse(name, source) == ret

            with patch.object(os.path, "isdir", mock_t):
                comt = "The directory {} is in the correct state".format(name)
                ret.update({"comment": comt, "result": True})
                assert filestate.recurse(name, source) == ret


# 'replace' function tests: 1
def test_replace():
    """
    Test to maintain an edit in a file.
    """
    name = "/etc/grub.conf"
    pattern = "CentOS +"
    repl = "salt"

    ret = {"name": name, "result": False, "comment": "", "changes": {}}

    comt = "Must provide name to file.replace"
    ret.update({"comment": comt, "name": "", "changes": {}})
    assert filestate.replace("", pattern, repl) == ret

    mock_t = MagicMock(return_value=True)
    mock_f = MagicMock(return_value=False)
    with patch.object(os.path, "isabs", mock_f):
        comt = "Specified file {} is not an absolute path".format(name)
        ret.update({"comment": comt, "name": name})
        assert filestate.replace(name, pattern, repl) == ret

    with patch.object(os.path, "isabs", mock_t):
        with patch.object(os.path, "exists", mock_t):
            with patch.dict(filestate.__salt__, {"file.replace": mock_f}):
                with patch.dict(filestate.__opts__, {"test": False}):
                    comt = "No changes needed to be made"
                    ret.update({"comment": comt, "name": name, "result": True})
                    assert filestate.replace(name, pattern, repl) == ret


# 'blockreplace' function tests: 1
def test_blockreplace():
    """
    Test to maintain an edit in a file in a zone
    delimited by two line markers.
    """
    with patch("salt.states.file._load_accumulators", MagicMock(return_value=([], []))):
        name = "/etc/hosts"

        ret = {"name": name, "result": False, "comment": "", "changes": {}}

        comt = "Must provide name to file.blockreplace"
        ret.update({"comment": comt, "name": ""})
        assert filestate.blockreplace("") == ret

        mock_t = MagicMock(return_value=True)
        mock_f = MagicMock(return_value=False)
        with patch.object(os.path, "isabs", mock_f):
            comt = "Specified file {} is not an absolute path".format(name)
            ret.update({"comment": comt, "name": name})
            assert filestate.blockreplace(name) == ret

        with patch.object(os.path, "isabs", mock_t), patch.object(
            os.path, "exists", mock_t
        ):
            with patch.dict(filestate.__salt__, {"file.blockreplace": mock_t}):
                with patch.dict(filestate.__opts__, {"test": True}):
                    comt = "Changes would be made"
                    ret.update(
                        {"comment": comt, "result": None, "changes": {"diff": True}}
                    )
                    assert filestate.blockreplace(name) == ret


# 'touch' function tests: 1
def test_touch():
    """
    Test to replicate the 'nix "touch" command to create a new empty
    file or update the atime and mtime of an existing file.
    """
    name = "/var/log/httpd/logrotate.empty"

    ret = {"name": name, "result": False, "comment": "", "changes": {}}

    comt = "Must provide name to file.touch"
    ret.update({"comment": comt, "name": ""})
    assert filestate.touch("") == ret

    mock_t = MagicMock(return_value=True)
    mock_f = MagicMock(return_value=False)
    with patch.object(os.path, "isabs", mock_f):
        comt = "Specified file {} is not an absolute path".format(name)
        ret.update({"comment": comt, "name": name})
        assert filestate.touch(name) == ret

    with patch.object(os.path, "isabs", mock_t):
        with patch.object(os.path, "exists", mock_f):
            with patch.dict(filestate.__opts__, {"test": True}):
                comt = "File {} is set to be created".format(name)
                ret.update({"comment": comt, "result": None, "changes": {"new": name}})
                assert filestate.touch(name) == ret

        with patch.dict(filestate.__opts__, {"test": False}):
            with patch.object(os.path, "isdir", mock_f):
                comt = "Directory not present to touch file {}".format(name)
                ret.update({"comment": comt, "result": False, "changes": {}})
                assert filestate.touch(name) == ret

            with patch.object(os.path, "isdir", mock_t):
                with patch.dict(filestate.__salt__, {"file.touch": mock_t}):
                    comt = "Created empty file {}".format(name)
                    ret.update(
                        {"comment": comt, "result": True, "changes": {"new": name}}
                    )
                    assert filestate.touch(name) == ret


# 'accumulated' function tests: 1
def test_accumulated():
    """
    Test to prepare accumulator which can be used in template in file.
    """
    with patch(
        "salt.states.file._load_accumulators", MagicMock(return_value=({}, {}))
    ), patch("salt.states.file._persist_accummulators", MagicMock(return_value=True)):
        name = "animals_doing_things"
        filename = "/tmp/animal_file.txt"
        text = " jumps over the lazy dog."

        ret = {"name": name, "result": False, "comment": "", "changes": {}}

        comt = "Must provide name to file.accumulated"
        ret.update({"comment": comt, "name": ""})
        assert filestate.accumulated("", filename, text) == ret

        comt = "No text supplied for accumulator"
        ret.update({"comment": comt, "name": name})
        assert filestate.accumulated(name, filename, None) == ret

        with patch.dict(
            filestate.__low__,
            {
                "require_in": "file",
                "watch_in": "salt",
                "__sls__": "SLS",
                "__id__": "ID",
            },
        ):
            comt = "Orphaned accumulator animals_doing_things in SLS:ID"
            ret.update({"comment": comt, "name": name})
            assert filestate.accumulated(name, filename, text) == ret

        with patch.dict(
            filestate.__low__,
            {
                "require_in": [{"file": "A"}],
                "watch_in": [{"B": "C"}],
                "__sls__": "SLS",
                "__id__": "ID",
            },
        ):
            comt = "Accumulator {} for file {} was charged by text".format(
                name, filename
            )
            ret.update({"comment": comt, "name": name, "result": True})
            assert filestate.accumulated(name, filename, text) == ret


# 'serialize' function tests: 1
def test_serialize_into_managed_file():
    """
    Test to serializes dataset and store it into managed file.
    """
    name = "/etc/dummy/package.json"

    ret = {"name": name, "result": False, "comment": "", "changes": {}}

    comt = "Must provide name to file.serialize"
    ret.update({"comment": comt, "name": ""})
    assert filestate.serialize("") == ret

    mock_t = MagicMock(return_value=True)
    mock_f = MagicMock(return_value=False)
    with patch.object(os.path, "isfile", mock_f):
        comt = "File {} is not present and is not set for creation".format(name)
        ret.update({"comment": comt, "name": name, "result": True})
        assert filestate.serialize(name, create=False) == ret

    comt = "Only one of 'dataset' and 'dataset_pillar' is permitted"
    ret.update({"comment": comt, "result": False})
    assert filestate.serialize(name, dataset=True, dataset_pillar=True) == ret

    comt = "Neither 'dataset' nor 'dataset_pillar' was defined"
    ret.update({"comment": comt, "result": False})
    assert filestate.serialize(name) == ret

    with patch.object(os.path, "isfile", mock_t):
        comt = "merge_if_exists is not supported for the python serializer"
        ret.update({"comment": comt, "result": False})
        assert (
            filestate.serialize(
                name, dataset=True, merge_if_exists=True, formatter="python"
            )
            == ret
        )

    comt = (
        "The a serializer could not be found. "
        "It either does not exist or its prerequisites are not installed."
    )
    ret.update({"comment": comt, "result": False})
    assert filestate.serialize(name, dataset=True, formatter="A") == ret
    mock_changes = MagicMock(return_value=True)
    mock_no_changes = MagicMock(return_value=False)

    # __opts__['test']=True with changes
    with patch.dict(filestate.__salt__, {"file.check_managed_changes": mock_changes}):
        with patch.dict(filestate.__opts__, {"test": True}):
            comt = "Dataset will be serialized and stored into {}".format(name)
            ret.update({"comment": comt, "result": None, "changes": True})
            assert filestate.serialize(name, dataset=True, formatter="python") == ret

    # __opts__['test']=True without changes
    with patch.dict(
        filestate.__salt__, {"file.check_managed_changes": mock_no_changes}
    ):
        with patch.dict(filestate.__opts__, {"test": True}):
            comt = "The file {} is in the correct state".format(name)
            ret.update({"comment": comt, "result": True, "changes": False})
            assert filestate.serialize(name, dataset=True, formatter="python") == ret

    mock = MagicMock(return_value=ret)
    with patch.dict(filestate.__opts__, {"test": False}):
        with patch.dict(filestate.__salt__, {"file.manage_file": mock}):
            comt = "Dataset will be serialized and stored into {}".format(name)
            ret.update({"comment": comt, "result": None})
            assert filestate.serialize(name, dataset=True, formatter="python") == ret


# 'mknod' function tests: 1
def test_mknod():
    """
    Test to create a special file similar to the 'nix mknod command.
    """
    name = "/dev/AA"
    ntype = "a"

    ret = {"name": name, "result": False, "comment": "", "changes": {}}

    comt = "Must provide name to file.mknod"
    ret.update({"comment": comt, "name": ""})
    assert filestate.mknod("", ntype) == ret

    comt = (
        "Node type unavailable: 'a'. Available node types are "
        "character ('c'), block ('b'), and pipe ('p')"
    )
    ret.update({"comment": comt, "name": name})
    assert filestate.mknod(name, ntype) == ret


# 'mod_run_check_cmd' function tests: 1
def test_mod_run_check_cmd():
    """
    Test to execute the check_cmd logic.
    """
    cmd = "A"
    filename = "B"

    ret = {
        "comment": "check_cmd execution failed",
        "result": False,
        "skip_watch": True,
    }

    mock = MagicMock(side_effect=[{"retcode": 1}, {"retcode": 0}])
    with patch.dict(filestate.__salt__, {"cmd.run_all": mock}):
        assert filestate.mod_run_check_cmd(cmd, filename) == ret

        assert filestate.mod_run_check_cmd(cmd, filename)
