import logging
import os

import pytest
import salt.serializers.json as jsonserializer
import salt.serializers.msgpack as msgpackserializer
import salt.serializers.plist as plistserializer
import salt.serializers.python as pythonserializer
import salt.serializers.yaml as yamlserializer
import salt.states.file as filestate
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


# 'absent' function tests: 1
def test_absent():
    """
    Test to make sure that the named file or directory is absent.
    """
    name = "/fake/file.conf"

    ret = {"name": name, "result": False, "comment": "", "changes": {}}

    mock_t = MagicMock(return_value=True)
    mock_f = MagicMock(return_value=False)
    mock_file = MagicMock(side_effect=[True, CommandExecutionError])
    mock_tree = MagicMock(side_effect=[True, OSError])

    comt = "Must provide name to file.absent"
    ret.update({"comment": comt, "name": ""})

    with patch.object(os.path, "islink", MagicMock(return_value=False)):
        assert filestate.absent("") == ret

        with patch.object(os.path, "isabs", mock_f):
            comt = "Specified file {} is not an absolute path".format(name)
            ret.update({"comment": comt, "name": name})
            assert filestate.absent(name) == ret

        with patch.object(os.path, "isabs", mock_t):
            comt = 'Refusing to make "/" absent'
            ret.update({"comment": comt, "name": "/"})
            assert filestate.absent("/") == ret

        with patch.object(os.path, "isfile", mock_t):
            with patch.dict(filestate.__opts__, {"test": True}):
                comt = "File {} is set for removal".format(name)
                ret.update(
                    {
                        "comment": comt,
                        "name": name,
                        "result": None,
                        "changes": {"removed": "/fake/file.conf"},
                    }
                )
                assert filestate.absent(name) == ret

            with patch.dict(filestate.__opts__, {"test": False}):
                with patch.dict(filestate.__salt__, {"file.remove": mock_file}):
                    comt = "Removed file {}".format(name)
                    ret.update(
                        {"comment": comt, "result": True, "changes": {"removed": name}}
                    )
                    assert filestate.absent(name) == ret

                    comt = "Removed file {}".format(name)
                    ret.update({"comment": "", "result": False, "changes": {}})
                    assert filestate.absent(name) == ret

        with patch.object(os.path, "isfile", mock_f):
            with patch.object(os.path, "isdir", mock_t):
                with patch.dict(filestate.__opts__, {"test": True}):
                    comt = "Directory {} is set for removal".format(name)
                    ret.update(
                        {"comment": comt, "changes": {"removed": name}, "result": None}
                    )
                    assert filestate.absent(name) == ret

                with patch.dict(filestate.__opts__, {"test": False}):
                    with patch.dict(filestate.__salt__, {"file.remove": mock_tree}):
                        comt = "Removed directory {}".format(name)
                        ret.update(
                            {
                                "comment": comt,
                                "result": True,
                                "changes": {"removed": name},
                            }
                        )
                        assert filestate.absent(name) == ret

                        comt = "Failed to remove directory {}".format(name)
                        ret.update({"comment": comt, "result": False, "changes": {}})
                        assert filestate.absent(name) == ret

            with patch.object(os.path, "isdir", mock_f):
                with patch.dict(filestate.__opts__, {"test": True}):
                    comt = "File {} is not present".format(name)
                    ret.update({"comment": comt, "result": True})
                    assert filestate.absent(name) == ret
