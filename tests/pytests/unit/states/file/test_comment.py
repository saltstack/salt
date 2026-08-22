import builtins
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
from tests.support.mock import MagicMock, mock_open, patch

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


# 'comment' function tests: 1
def test_comment():
    """
    Test to comment out specified lines in a file.
    """
    with patch.object(os.path, "exists", MagicMock(return_value=True)):
        name = "/etc/aliases" if salt.utils.platform.is_darwin() else "/etc/fstab"
        regex = "bind 127.0.0.1"

        ret = {"name": name, "result": False, "comment": "", "changes": {}}

        comt = "Must provide name to file.comment"
        ret.update({"comment": comt, "name": ""})
        assert filestate.comment("", regex) == ret

        mock_t = MagicMock(return_value=True)
        mock_f = MagicMock(return_value=False)
        with patch.object(os.path, "isabs", mock_f):
            comt = f"Specified file {name} is not an absolute path"
            ret.update({"comment": comt, "name": name})
            assert filestate.comment(name, regex) == ret

        with patch.object(os.path, "isabs", mock_t):
            with patch.dict(
                filestate.__salt__,
                {
                    "file.search": MagicMock(
                        side_effect=[False, True, False, False, False, False]
                    )
                },
            ):
                comt = "Pattern already commented"
                ret.update({"comment": comt, "result": True})
                assert filestate.comment(name, regex) == ret

                comt = "Pattern not found and ignore_missing set to True"
                ret.update({"comment": comt, "result": True})
                assert filestate.comment(name, regex, ignore_missing=True) == ret

                comt = f"{regex}: Pattern not found"
                ret.update({"comment": comt, "result": False})
                assert filestate.comment(name, regex) == ret

            with patch.dict(
                filestate.__salt__,
                {
                    "file.search": MagicMock(
                        side_effect=[True, True, True, False, True]
                    ),
                    "file.comment": mock_t,
                    "file.comment_line": mock_t,
                },
            ):
                with patch.dict(filestate.__opts__, {"test": True}):
                    comt = f"File {name} is set to be updated"
                    ret.update(
                        {"comment": comt, "result": None, "changes": {name: "updated"}}
                    )
                    assert filestate.comment(name, regex) == ret

                with patch.dict(filestate.__opts__, {"test": False}):
                    with patch.object(
                        salt.utils.files, "fopen", MagicMock(mock_open())
                    ):
                        comt = "Commented lines successfully"
                        ret.update({"comment": comt, "result": True, "changes": {}})
                        assert filestate.comment(name, regex) == ret

                with patch.dict(filestate.__opts__, {"test": True}):
                    comt = "Pattern already commented"
                    ret.update({"comment": comt, "result": True, "changes": {}})
                    assert filestate.comment(name, regex) == ret


def test_comment_encoding_mismatch_strict_raises_50903(tmp_path):
    """
    With the default encoding_errors="strict" (matching Python's own default),
    file.comment aborts with a UnicodeDecodeError when the target file contains
    bytes not valid in the encoding used to build the diff. This documents the
    #50903 default; encoding_errors="replace" is the escape hatch, covered next.
    """
    name = tmp_path / "fstab"
    # 0xed is not valid ASCII and not valid UTF-8 on its own
    name.write_bytes(b"bind 127.0.0.1\nabc\xedxyz\n")

    salt_mock = {
        "file.search": MagicMock(side_effect=[True, True]),
        "file.comment_line": MagicMock(return_value=True),
    }

    with patch.object(builtins, "__salt_system_encoding__", "ascii"), patch.dict(
        filestate.__salt__, salt_mock
    ):
        with pytest.raises(UnicodeDecodeError):
            filestate.comment(str(name), "^bind 127.0.0.1")


def test_comment_encoding_mismatch_replace_50903(tmp_path):
    """
    Setting encoding_errors="replace" lets file.comment proceed on a file whose
    bytes are not valid in the diff encoding, instead of aborting. The #50903
    escape hatch, called with the production-exact argument shape.
    """
    name = tmp_path / "fstab"
    name.write_bytes(b"bind 127.0.0.1\nabc\xedxyz\n")

    salt_mock = {
        # First search: uncommented pattern found; second: commented after edit
        "file.search": MagicMock(side_effect=[True, True]),
        "file.comment_line": MagicMock(return_value=True),
    }

    with patch.object(builtins, "__salt_system_encoding__", "ascii"), patch.dict(
        filestate.__salt__, salt_mock
    ):
        result = filestate.comment(
            str(name), "^bind 127.0.0.1", encoding_errors="replace"
        )

    assert result["result"] is True
    assert result["comment"] == "Commented lines successfully"
    salt_mock["file.comment_line"].assert_called_once()


# 'uncomment' function tests: 1
def test_uncomment():
    """
    Test to uncomment specified commented lines in a file
    """
    with patch.object(os.path, "exists", MagicMock(return_value=True)):
        name = "/etc/aliases" if salt.utils.platform.is_darwin() else "/etc/fstab"
        regex = "bind 127.0.0.1"

        ret = {"name": name, "result": False, "comment": "", "changes": {}}

        comt = "Must provide name to file.uncomment"
        ret.update({"comment": comt, "name": ""})
        assert filestate.uncomment("", regex) == ret

        mock_t = MagicMock(return_value=True)
        mock_f = MagicMock(return_value=False)
        mock = MagicMock(side_effect=[False, True, False, False, True, True, True])
        with patch.object(os.path, "isabs", mock_f):
            comt = f"Specified file {name} is not an absolute path"
            ret.update({"comment": comt, "name": name})
            assert filestate.uncomment(name, regex) == ret

        with patch.object(os.path, "isabs", mock_t):
            with patch.dict(
                filestate.__salt__,
                {
                    "file.search": mock,
                    "file.uncomment": mock_t,
                    "file.comment_line": mock_t,
                },
            ):
                comt = "Pattern already uncommented"
                ret.update({"comment": comt, "result": True})
                assert filestate.uncomment(name, regex) == ret

                comt = f"{regex}: Pattern not found"
                ret.update({"comment": comt, "result": False})
                assert filestate.uncomment(name, regex) == ret

                with patch.dict(filestate.__opts__, {"test": True}):
                    comt = f"File {name} is set to be updated"
                    ret.update(
                        {"comment": comt, "result": None, "changes": {name: "updated"}}
                    )
                    assert filestate.uncomment(name, regex) == ret

                with patch.dict(filestate.__opts__, {"test": False}):
                    with patch.object(
                        salt.utils.files, "fopen", MagicMock(mock_open())
                    ):
                        comt = "Uncommented lines successfully"
                        ret.update({"comment": comt, "result": True, "changes": {}})
                        assert filestate.uncomment(name, regex) == ret
