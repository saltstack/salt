"""
Tests for file.replace with encoding support (issue #52793).

Verifies that UTF-16 and other multi-byte encoded files can be handled by
file.replace when an explicit encoding is provided.
"""

import logging

import pytest

import salt.modules.cmdmod as cmdmod
import salt.modules.file as filemod
import salt.utils.files
import salt.utils.platform
import salt.utils.stringutils
from salt.exceptions import SaltInvocationError
from tests.support.mock import MagicMock

log = logging.getLogger(__name__)


@pytest.fixture
def configure_loader_modules():
    if salt.utils.platform.is_windows():
        grains = {"kernel": "Windows"}
    else:
        grains = {"kernel": "Linux"}
    opts = {
        "test": False,
        "file_roots": {"base": "tmp"},
        "pillar_roots": {"base": "tmp"},
        "cachedir": "tmp",
        "grains": grains,
    }
    return {
        filemod: {
            "__salt__": {
                "config.manage_mode": MagicMock(),
                "cmd.run": cmdmod.run,
                "cmd.run_all": cmdmod.run_all,
            },
            "__opts__": opts,
            "__grains__": grains,
            "__utils__": {
                "files.is_text": salt.utils.files.is_text,
                "stringutils.get_diff": salt.utils.stringutils.get_diff,
            },
        }
    }


@pytest.fixture
def utf16_file(tmp_path):
    """A UTF-16 encoded file with a known pattern to replace."""
    p = tmp_path / "test.psd1"
    content = "PowerShellVersion = '2.0'\r\nModuleVersion = '1.0'\r\n"
    p.write_text(content, encoding="utf-16")
    return p


@pytest.fixture
def utf8_file(tmp_path):
    """A plain UTF-8 text file."""
    p = tmp_path / "test.txt"
    p.write_text("hello world\n", encoding="utf-8")
    return p


def test_replace_utf16_matches_and_rewrites(utf16_file):
    """
    file.replace with encoding='utf-16' should find and replace a pattern in a
    UTF-16 encoded file and write the result back in the same encoding.
    """
    result = filemod.replace(
        str(utf16_file),
        pattern=r"PowerShellVersion = '2\.0'",
        repl="PowerShellVersion = '3.0'",
        encoding="utf-16",
        show_changes=False,
    )
    assert result is True
    updated = utf16_file.read_text(encoding="utf-16")
    assert "PowerShellVersion = '3.0'" in updated
    assert "PowerShellVersion = '2.0'" not in updated
    assert "ModuleVersion = '1.0'" in updated


def test_replace_utf16_no_match_returns_false(utf16_file):
    """
    file.replace with encoding='utf-16' should return False (no changes) when
    the pattern is not found.
    """
    result = filemod.replace(
        str(utf16_file),
        pattern=r"DoesNotExist",
        repl="something",
        encoding="utf-16",
        show_changes=False,
    )
    assert result is False
    assert "PowerShellVersion = '2.0'" in utf16_file.read_text(encoding="utf-16")


def test_replace_utf16_preserves_encoding(utf16_file):
    """
    After file.replace with encoding='utf-16', the file must remain valid
    UTF-16 (not silently re-encoded as UTF-8/ANSI).
    """
    filemod.replace(
        str(utf16_file),
        pattern=r"ModuleVersion = '1\.0'",
        repl="ModuleVersion = '2.0'",
        encoding="utf-16",
        show_changes=False,
    )
    raw = utf16_file.read_bytes()
    assert raw[:2] in (
        b"\xff\xfe",
        b"\xfe\xff",
    ), "BOM missing: file is no longer UTF-16"
    content = utf16_file.read_text(encoding="utf-16")
    assert "ModuleVersion = '2.0'" in content


def test_replace_utf16_search_only(utf16_file):
    """
    search_only=True should return True when the pattern is found in a UTF-16
    file without modifying it.
    """
    original_bytes = utf16_file.read_bytes()
    result = filemod.replace(
        str(utf16_file),
        pattern=r"PowerShellVersion",
        repl="irrelevant",
        encoding="utf-16",
        search_only=True,
    )
    assert result is True
    assert utf16_file.read_bytes() == original_bytes


def test_replace_utf16_search_only_no_match(utf16_file):
    """
    search_only=True should return False when the pattern is absent.
    """
    result = filemod.replace(
        str(utf16_file),
        pattern=r"NotPresent",
        repl="irrelevant",
        encoding="utf-16",
        search_only=True,
    )
    assert result is False


def test_replace_utf16_show_changes_returns_diff(utf16_file):
    """
    show_changes=True (the default) should return a non-empty unified diff
    string when a substitution is made.
    """
    result = filemod.replace(
        str(utf16_file),
        pattern=r"PowerShellVersion = '2\.0'",
        repl="PowerShellVersion = '3.0'",
        encoding="utf-16",
    )
    assert isinstance(result, str)
    assert result != ""


def test_replace_utf16_dry_run_does_not_write(utf16_file):
    """
    dry_run=True should report changes without modifying the file byte-for-byte.
    """
    original_bytes = utf16_file.read_bytes()
    filemod.replace(
        str(utf16_file),
        pattern=r"PowerShellVersion = '2\.0'",
        repl="PowerShellVersion = '3.0'",
        encoding="utf-16",
        dry_run=True,
        show_changes=False,
    )
    assert utf16_file.read_bytes() == original_bytes


def test_replace_utf16_append_if_not_found(tmp_path):
    """
    append_if_not_found=True should append the repl text when the pattern is
    absent from a UTF-16 file.
    """
    p = tmp_path / "append_test.txt"
    p.write_text("existing line\r\n", encoding="utf-16")

    filemod.replace(
        str(p),
        pattern=r"MissingLine",
        repl="NewLine",
        encoding="utf-16",
        append_if_not_found=True,
        show_changes=False,
    )
    content = p.read_text(encoding="utf-16")
    assert "existing line" in content
    assert "NewLine" in content


def test_replace_utf32_matches_and_rewrites(tmp_path):
    """
    file.replace with encoding='utf-32' should find and replace a pattern in a
    UTF-32 encoded file and write the result back in the same encoding.
    """
    p = tmp_path / "test.txt"
    p.write_text("key = old_value\n", encoding="utf-32")

    result = filemod.replace(
        str(p),
        pattern=r"key = old_value",
        repl="key = new_value",
        encoding="utf-32",
        show_changes=False,
    )

    assert result is True
    content = p.read_text(encoding="utf-32")
    assert "key = new_value" in content
    assert "key = old_value" not in content

    raw = p.read_bytes()
    assert raw[:4] in (
        b"\xff\xfe\x00\x00",
        b"\x00\x00\xfe\xff",
    ), "BOM missing: file is no longer UTF-32"


def test_replace_binary_without_encoding_raises(tmp_path):
    """
    A file containing null bytes should still raise SaltInvocationError when
    no encoding is specified (existing behaviour is preserved).
    """
    p = tmp_path / "binary.bin"
    p.write_bytes(b"\x00\x01\x02\x03binary data")

    with pytest.raises(SaltInvocationError, match="binary file"):
        filemod.replace(
            str(p),
            pattern=r"binary",
            repl="text",
        )
