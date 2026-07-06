import builtins

import pytest

import salt.states.file as filestate
import salt.utils.files
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


def test_append_clean_encoding_unaffected_50903(tmp_path):
    """
    Guard against overcorrection of the #50903 fix: decoding with
    errors="replace" must not change behaviour for files that decode
    cleanly in the system encoding. The diff must still be generated,
    contain the original non-ASCII text unmangled, and hold no U+FFFD
    replacement characters. This test passes with and without the fix.
    """
    name = tmp_path / "cleanfile"
    # Valid UTF-8 content that decodes cleanly with the utf-8 system encoding
    name.write_bytes("h\u00e9llo\n".encode("utf-8"))

    def fake_append(fname, args=None):
        # Perform the real append so the state's second read sees a change
        with salt.utils.files.fopen(fname, "a", encoding="utf-8") as fp_:
            for line in args:
                fp_.write(line + "\n")

    salt_mock = {
        "file.search": MagicMock(return_value=False),
        "file.append": MagicMock(side_effect=fake_append),
    }
    utils_mock = {"files.is_text": MagicMock(return_value=True)}

    # Production callers (the state compiler running an SLS file.append)
    # pass name and text; __salt_system_encoding__ is the locale-derived
    # builtin read by the decode sites, so it is patched rather than passed.
    with patch.object(builtins, "__salt_system_encoding__", "utf-8"), patch.dict(
        filestate.__salt__, salt_mock
    ), patch.dict(filestate.__utils__, utils_mock):
        result = filestate.append(name=str(name), text="cheese")

    assert result["result"] is True
    assert result["comment"] == "Appended 1 lines"
    diff = result["changes"]["diff"]
    assert "+cheese" in diff
    assert "h\u00e9llo" in diff
    assert "\ufffd" not in diff
