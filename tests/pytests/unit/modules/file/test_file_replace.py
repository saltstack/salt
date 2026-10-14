"""
Tests for file.replace with encoding support (issues #52793 and #65906).

Verifies that UTF-16 and other multi-byte encoded files can be handled by
file.replace when an explicit encoding is provided, and that files starting
with a UTF-16 or UTF-32 byte order mark are detected without one.
"""

import codecs
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
                "files.get_encoding": salt.utils.files.get_encoding,
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


BOM_ENCODINGS = [
    pytest.param("utf-16-le", codecs.BOM_UTF16_LE, id="utf-16-le"),
    pytest.param("utf-16-be", codecs.BOM_UTF16_BE, id="utf-16-be"),
    pytest.param("utf-32-le", codecs.BOM_UTF32_LE, id="utf-32-le"),
    pytest.param("utf-32-be", codecs.BOM_UTF32_BE, id="utf-32-be"),
]


def _bom_bytes(codec, bom, text):
    return bom + text.encode(codec)


@pytest.mark.parametrize("codec,bom", BOM_ENCODINGS)
def test_replace_bom_file_without_encoding(tmp_path, codec, bom):
    """
    A file starting with a UTF-16 or UTF-32 BOM is detected without an
    explicit encoding, and the BOM and byte order are written back unchanged.
    """
    p = tmp_path / "bom.txt"
    p.write_bytes(_bom_bytes(codec, bom, "key = old\r\nother = 1\r\n"))

    result = filemod.replace(
        str(p), pattern=r"key = old", repl="key = new", show_changes=False
    )

    assert result is True
    assert p.read_bytes() == _bom_bytes(codec, bom, "key = new\r\nother = 1\r\n")


@pytest.mark.parametrize("codec,bom", BOM_ENCODINGS)
def test_replace_bom_file_anchor_on_first_line(tmp_path, codec, bom):
    """
    The BOM is not part of the text, so ``^`` matches at the start of the
    first line.
    """
    p = tmp_path / "bom.txt"
    p.write_bytes(_bom_bytes(codec, bom, "first = 1\nsecond = 2\n"))

    filemod.replace(str(p), pattern=r"^first = \d+$", repl="first = 9")

    assert p.read_bytes() == _bom_bytes(codec, bom, "first = 9\nsecond = 2\n")


@pytest.mark.parametrize("codec,bom", BOM_ENCODINGS)
def test_replace_bom_file_prepend_after_bom(tmp_path, codec, bom):
    """
    prepend_if_not_found puts the new line after the BOM, and a second run
    finds it and makes no change.
    """
    p = tmp_path / "bom.txt"
    p.write_bytes(_bom_bytes(codec, bom, "existing\r\n"))

    filemod.replace(str(p), pattern=r"^added$", repl="added", prepend_if_not_found=True)
    expected = _bom_bytes(codec, bom, "added\r\nexisting\r\n")
    assert p.read_bytes() == expected

    result = filemod.replace(
        str(p),
        pattern=r"^added$",
        repl="added",
        prepend_if_not_found=True,
        show_changes=False,
    )
    assert result is False
    assert p.read_bytes() == expected


@pytest.mark.parametrize("codec,bom", BOM_ENCODINGS)
def test_replace_bom_file_append_uses_file_eol(tmp_path, codec, bom):
    """
    append_if_not_found adds the line with the file's line ending.
    """
    p = tmp_path / "bom.txt"
    p.write_bytes(_bom_bytes(codec, bom, "existing\r\n"))

    filemod.replace(str(p), pattern=r"^added$", repl="added", append_if_not_found=True)

    assert p.read_bytes() == _bom_bytes(codec, bom, "existing\r\nadded\r\n")


@pytest.mark.parametrize("codec,bom", BOM_ENCODINGS)
def test_replace_bom_file_dry_run(tmp_path, codec, bom):
    """
    dry_run reports a diff without the BOM in it and leaves the file alone.
    """
    p = tmp_path / "bom.txt"
    original = _bom_bytes(codec, bom, "key = old\n")
    p.write_bytes(original)

    diff = filemod.replace(str(p), pattern=r"key = old", repl="key = new", dry_run=True)

    assert "+key = new" in diff
    assert "\ufeff" not in diff
    assert p.read_bytes() == original


@pytest.mark.parametrize("codec,bom", BOM_ENCODINGS)
def test_replace_bom_file_search_only(tmp_path, codec, bom):
    p = tmp_path / "bom.txt"
    original = _bom_bytes(codec, bom, "key = old\n")
    p.write_bytes(original)

    assert filemod.replace(str(p), pattern=r"^key", repl="", search_only=True)
    assert not filemod.replace(str(p), pattern=r"missing", repl="", search_only=True)
    assert p.read_bytes() == original


@pytest.mark.parametrize("codec,bom", BOM_ENCODINGS)
def test_replace_bom_file_no_match_is_unchanged(tmp_path, codec, bom):
    p = tmp_path / "bom.txt"
    original = _bom_bytes(codec, bom, "key = old\n")
    p.write_bytes(original)

    result = filemod.replace(str(p), pattern=r"missing", repl="new", show_changes=False)

    assert result is False
    assert p.read_bytes() == original
    assert not (tmp_path / "bom.txt.bak").exists()


def test_replace_invalid_utf16_after_bom_raises(tmp_path):
    """
    A binary file that happens to start with a UTF-16 BOM fails to decode, so
    it is reported as binary and never modified.
    """
    p = tmp_path / "fake.bin"
    # An unpaired high surrogate is invalid UTF-16
    original = codecs.BOM_UTF16_LE + b"\x00\xd8\x00\x00\x01\x02"
    p.write_bytes(original)

    with pytest.raises(SaltInvocationError, match="binary file"):
        filemod.replace(str(p), pattern=r"x", repl="y")
    assert p.read_bytes() == original


def test_replace_utf16_without_bom_still_raises(tmp_path):
    """
    Without a BOM the encoding can only be guessed, so an explicit encoding is
    still required.
    """
    p = tmp_path / "nobom.txt"
    original = "key = old\r\n".encode("utf-16-le")
    p.write_bytes(original)

    with pytest.raises(SaltInvocationError, match="binary file"):
        filemod.replace(str(p), pattern=r"key = old", repl="key = new")
    assert p.read_bytes() == original


def test_replace_explicit_endian_encoding_keeps_bom(tmp_path):
    """
    An endian specific codec keeps the BOM as U+FEFF when decoding. It is
    stripped before matching and written back.
    """
    p = tmp_path / "bom.txt"
    p.write_bytes(codecs.BOM_UTF16_LE + "first = 1\n".encode("utf-16-le"))

    filemod.replace(
        str(p), pattern=r"^first = 1$", repl="first = 2", encoding="utf-16-le"
    )

    assert p.read_bytes() == codecs.BOM_UTF16_LE + "first = 2\n".encode("utf-16-le")


@pytest.mark.parametrize(
    "data",
    [
        pytest.param(b"key = old\nnext\n", id="ascii"),
        pytest.param("key = old caf\u00e9\n".encode("utf-8"), id="utf-8"),
        pytest.param(
            codecs.BOM_UTF8 + "key = old caf\u00e9\n".encode("utf-8"), id="utf-8-bom"
        ),
    ],
)
def test_replace_text_files_unaffected(tmp_path, data):
    """
    Files that already pass the text check keep using the bytes code path.
    """
    p = tmp_path / "text.txt"
    p.write_bytes(data)

    filemod.replace(str(p), pattern=r"key = old", repl="key = new")

    assert p.read_bytes() == data.replace(b"key = old", b"key = new")
