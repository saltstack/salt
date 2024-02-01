import logging
import os
import shutil

import pytest

import salt.serializers.json as jsonserializer
import salt.serializers.msgpack as msgpackserializer
import salt.serializers.yaml as yamlserializer
import salt.states.file as filestate
import salt.utils.platform
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


# 'rename' function tests: 1
def test_rename(tmp_path):
    """
    Test if the source file exists on the system,
    rename it to the named file.
    """
    name = str(tmp_path / "salt")
    source = str(tmp_path / "salt" / "salt")

    ret = {"name": name, "result": False, "comment": "", "changes": {}}

    comt = "Must provide name to file.rename"
    ret.update({"comment": comt, "name": ""})
    assert filestate.rename("", source) == ret

    mock_t = MagicMock(return_value=True)
    mock_f = MagicMock(return_value=False)

    mock_lex = MagicMock(side_effect=[False, True, True])
    with patch.object(os.path, "isabs", mock_f):
        comt = f"Specified file {name} is not an absolute path"
        ret.update({"comment": comt, "name": name})
        assert filestate.rename(name, source) == ret

    mock_lex = MagicMock(return_value=False)
    with patch.object(os.path, "isabs", mock_t):
        with patch.object(os.path, "lexists", mock_lex):
            comt = f'Source file "{source}" has already been moved out of place'
            ret.update({"comment": comt, "result": True})
            assert filestate.rename(name, source) == ret

    mock_lex = MagicMock(side_effect=[True, True, True])
    with patch.object(os.path, "isabs", mock_t):
        with patch.object(os.path, "lexists", mock_lex):
            comt = 'The target file "{}" exists and will not be overwritten'.format(
                name
            )
            ret.update({"comment": comt, "result": True})
            assert filestate.rename(name, source) == ret

    mock_lex = MagicMock(side_effect=[True, True, True])
    mock_rem = MagicMock(side_effect=IOError)
    with patch.object(os.path, "isabs", mock_t):
        with patch.object(os.path, "lexists", mock_lex):
            with patch.dict(filestate.__opts__, {"test": False}):
                comt = 'Failed to delete "{}" in preparation for forced move'.format(
                    name
                )
                with patch.dict(filestate.__salt__, {"file.remove": mock_rem}):
                    ret.update({"name": name, "comment": comt, "result": False})
                    assert filestate.rename(name, source, force=True) == ret

    mock_lex = MagicMock(side_effect=[True, False, False])
    with patch.object(os.path, "isabs", mock_t):
        with patch.object(os.path, "lexists", mock_lex):
            with patch.dict(filestate.__opts__, {"test": True}):
                comt = f'File "{source}" is set to be moved to "{name}"'
                ret.update({"name": name, "comment": comt, "result": None})
                assert filestate.rename(name, source) == ret

    mock_lex = MagicMock(side_effect=[True, False, False])
    with patch.object(os.path, "isabs", mock_t):
        with patch.object(os.path, "lexists", mock_lex):
            with patch.object(os.path, "isdir", mock_f):
                with patch.dict(filestate.__opts__, {"test": False}):
                    comt = f"The target directory {tmp_path} is not present"
                    ret.update({"name": name, "comment": comt, "result": False})
                    assert filestate.rename(name, source) == ret

    mock_lex = MagicMock(side_effect=[True, False, False])
    with patch.object(os.path, "isabs", mock_t):
        with patch.object(os.path, "lexists", mock_lex):
            with patch.object(os.path, "isdir", mock_t):
                with patch.object(os.path, "islink", mock_f):
                    with patch.dict(filestate.__opts__, {"test": False}):
                        with patch.object(
                            shutil, "move", MagicMock(side_effect=IOError)
                        ):
                            comt = f'Failed to move "{source}" to "{name}"'
                            ret.update({"name": name, "comment": comt, "result": False})
                            assert filestate.rename(name, source) == ret

    mock_lex = MagicMock(side_effect=[True, False, False])
    with patch.object(os.path, "isabs", mock_t):
        with patch.object(os.path, "lexists", mock_lex):
            with patch.object(os.path, "isdir", mock_t):
                with patch.object(os.path, "islink", mock_f):
                    with patch.dict(filestate.__opts__, {"test": False}):
                        with patch.object(shutil, "move", MagicMock()):
                            comt = f'Moved "{source}" to "{name}"'
                            ret.update(
                                {
                                    "name": name,
                                    "comment": comt,
                                    "result": True,
                                    "changes": {name: source},
                                }
                            )
                            assert filestate.rename(name, source) == ret

    mock_lex = MagicMock(side_effect=[True, False, False])
    with patch.object(os.path, "isabs", mock_t), patch.object(
        os.path, "lexists", mock_lex
    ), patch.object(os.path, "isdir", mock_f), patch.dict(
        filestate.__salt__,
        {"file.makedirs": MagicMock(side_effect=filestate.CommandExecutionError())},
    ), patch.object(
        os.path, "islink", mock_f
    ), patch.dict(
        filestate.__opts__, {"test": False}
    ), patch.object(
        shutil, "move", MagicMock()
    ):
        if salt.utils.platform.is_windows():
            comt = "Drive C: is not mapped"
        else:
            comt = "Drive  is not mapped"
        ret.update(
            {
                "name": name,
                "comment": comt,
                "result": False,
                "changes": {},
            }
        )
        assert filestate.rename(name, source, makedirs=True) == ret

    mock_lex = MagicMock(side_effect=[True, False, False])
    mock_link = str(tmp_path / "salt" / "link")
    with patch.object(os.path, "isabs", mock_t), patch.object(
        os.path, "lexists", mock_lex
    ), patch.object(os.path, "isdir", mock_t), patch.object(
        os.path, "islink", mock_t
    ), patch(
        "salt.utils.path.readlink", MagicMock(return_value=mock_link)
    ), patch.dict(
        filestate.__opts__, {"test": False}
    ), patch.object(
        os, "symlink", MagicMock()
    ), patch.object(
        os, "unlink", MagicMock()
    ):
        comt = f'Moved "{source}" to "{name}"'
        ret.update(
            {
                "name": name,
                "comment": comt,
                "result": True,
                "changes": {name: source},
            }
        )
        assert filestate.rename(name, source) == ret
