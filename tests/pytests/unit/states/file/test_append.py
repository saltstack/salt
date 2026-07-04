import builtins

import pytest

import salt.states.file as filestate
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {
        filestate: {
            "__env__": "base",
            "__salt__": {},
            "__opts__": {"test": False, "cachedir": ""},
            "__instance_id__": "",
            "__low__": {},
            "__utils__": {},
        }
    }


def test_append_file_encoding_mismatch(tmp_path):
    """
    file.append must not raise UnicodeDecodeError when the target file
    contains bytes that are not valid in the system encoding. The decoded
    contents are only used to build the diff, so undecodable bytes should
    be tolerated rather than aborting the state.

    Regression test for #50903.
    """
    name = tmp_path / "bugfile"
    # 0xed is not valid ASCII and not valid UTF-8 on its own
    name.write_bytes(b"abc\xedxyz\n")

    salt_mock = {
        "file.search": MagicMock(return_value=False),
        "file.append": MagicMock(return_value=None),
    }
    utils_mock = {"files.is_text": MagicMock(return_value=True)}

    with patch.object(builtins, "__salt_system_encoding__", "ascii"), patch.dict(
        filestate.__salt__, salt_mock
    ), patch.dict(filestate.__utils__, utils_mock):
        result = filestate.append(name=str(name), text="cheese")

    assert result["result"] is True
    salt_mock["file.append"].assert_called_once()
