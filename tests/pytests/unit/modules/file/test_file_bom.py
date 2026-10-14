"""
Tests for file module functions on files that start with a UTF-16 or UTF-32
byte order mark (BOM) (issue #65906).

These files contain null bytes, so the text check treats them as binary. They
are detected from the BOM, edited as text, and written back with the BOM, byte
order and line endings unchanged. Files are written and compared as bytes.
"""

import codecs
import os

import pytest

import salt.modules.cmdmod as cmdmod
import salt.modules.config as configmod
import salt.modules.file as filemod
import salt.utils.files
import salt.utils.stringutils
from salt.exceptions import SaltInvocationError
from tests.support.mock import MagicMock, patch

BOM_ENCODINGS = [
    pytest.param(("utf-16-le", codecs.BOM_UTF16_LE), id="utf-16-le"),
    pytest.param(("utf-16-be", codecs.BOM_UTF16_BE), id="utf-16-be"),
    pytest.param(("utf-32-le", codecs.BOM_UTF32_LE), id="utf-32-le"),
    pytest.param(("utf-32-be", codecs.BOM_UTF32_BE), id="utf-32-be"),
]

EOLS = [
    pytest.param("\n", id="lf"),
    pytest.param("\r\n", id="crlf"),
]

# An unpaired high surrogate after a UTF-16-LE BOM is not valid UTF-16
INVALID_UTF16 = codecs.BOM_UTF16_LE + b"\x00\xd8\x00\x00\x01\x02"


@pytest.fixture
def configure_loader_modules():
    return {
        filemod: {
            "__salt__": {
                "config.manage_mode": configmod.manage_mode,
                "cmd.run": cmdmod.run,
                "cmd.run_all": cmdmod.run_all,
            },
            "__opts__": {
                "test": False,
                "file_roots": {"base": "tmp"},
                "pillar_roots": {"base": "tmp"},
                "cachedir": "tmp",
                "grains": {},
            },
            "__grains__": {"kernel": "Linux"},
            "__utils__": {
                "files.get_encoding": salt.utils.files.get_encoding,
                "files.is_binary": salt.utils.files.is_binary,
                "files.is_text": salt.utils.files.is_text,
                "stringutils.get_diff": salt.utils.stringutils.get_diff,
            },
        }
    }


@pytest.fixture(params=BOM_ENCODINGS)
def encoded(request):
    """
    Return a function that encodes text like the file under test, including
    the byte order mark.
    """
    codec, bom = request.param

    def _encode(text):
        return bom + text.encode(codec)

    return _encode


@pytest.fixture
def target(tmp_path):
    return tmp_path / "target.txt"


@pytest.fixture
def no_check_perms():
    # blockreplace calls check_perms with Windows arguments on Windows, which
    # salt.modules.file.check_perms does not accept outside of win_file
    with patch.object(filemod, "check_perms", MagicMock()):
        yield


# --------------------------------------------------------------------------
# salt.utils.files.get_bom_encoding
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "data,expected",
    [
        (codecs.BOM_UTF32_LE + "a".encode("utf-32-le"), "UTF-32-LE"),
        (codecs.BOM_UTF32_BE + "a".encode("utf-32-be"), "UTF-32-BE"),
        (codecs.BOM_UTF16_LE + "a".encode("utf-16-le"), "UTF-16-LE"),
        (codecs.BOM_UTF16_BE + "a".encode("utf-16-be"), "UTF-16-BE"),
        (codecs.BOM_UTF16_LE, "UTF-16-LE"),
        (codecs.BOM_UTF8 + b"a", None),
        (b"plain text\n", None),
        (b"", None),
    ],
)
def test_get_bom_encoding(target, data, expected):
    target.write_bytes(data)
    assert salt.utils.files.get_bom_encoding(str(target)) == expected


def test_get_bom_encoding_missing_file(tmp_path):
    assert salt.utils.files.get_bom_encoding(str(tmp_path / "missing")) is None


# --------------------------------------------------------------------------
# file.append
# --------------------------------------------------------------------------


@pytest.mark.parametrize("eol", EOLS)
def test_append(target, encoded, eol):
    target.write_bytes(encoded(f"first{eol}"))
    filemod.append(str(target), "second", "third")
    assert target.read_bytes() == encoded(f"first{eol}second{eol}third{eol}")


@pytest.mark.parametrize("eol", EOLS)
def test_append_adds_missing_final_eol(target, encoded, eol):
    target.write_bytes(encoded(f"first{eol}last"))
    filemod.append(str(target), "new")
    assert target.read_bytes() == encoded(f"first{eol}last{eol}new{eol}")


def test_append_to_bom_only_file(target, encoded):
    target.write_bytes(encoded(""))
    filemod.append(str(target), "new")
    assert target.read_bytes() == encoded(f"new{os.linesep}")


def test_append_invalid_bom_file_raises(target):
    target.write_bytes(INVALID_UTF16)
    with pytest.raises(SaltInvocationError, match="binary file"):
        filemod.append(str(target), "new")
    assert target.read_bytes() == INVALID_UTF16


# --------------------------------------------------------------------------
# file.prepend
# --------------------------------------------------------------------------


@pytest.mark.parametrize("eol", EOLS)
def test_prepend_goes_after_bom(target, encoded, eol):
    target.write_bytes(encoded(f"existing{eol}"))
    filemod.prepend(str(target), "first", "second")
    assert target.read_bytes() == encoded(f"first{eol}second{eol}existing{eol}")


def test_prepend_invalid_bom_file_raises(target):
    target.write_bytes(INVALID_UTF16)
    with pytest.raises(SaltInvocationError, match="binary file"):
        filemod.prepend(str(target), "new")
    assert target.read_bytes() == INVALID_UTF16


# --------------------------------------------------------------------------
# file.line
# --------------------------------------------------------------------------


@pytest.mark.parametrize("eol", EOLS)
def test_line_replace(target, encoded, eol):
    target.write_bytes(encoded(f"foo = 1{eol}bar{eol}"))
    ret = filemod.line(
        str(target), content="foo = 2", match=r"^foo = .*$", mode="replace"
    )
    assert ret
    assert "\ufeff" not in ret
    assert target.read_bytes() == encoded(f"foo = 2{eol}bar{eol}")


@pytest.mark.parametrize("eol", EOLS)
def test_line_insert_after(target, encoded, eol):
    target.write_bytes(encoded(f"first{eol}second{eol}"))
    filemod.line(str(target), content="new", after=r"^first$", mode="insert")
    assert target.read_bytes() == encoded(f"first{eol}new{eol}second{eol}")


@pytest.mark.parametrize("eol", EOLS)
def test_line_insert_start_goes_after_bom(target, encoded, eol):
    target.write_bytes(encoded(f"first{eol}"))
    filemod.line(str(target), content="top", mode="insert", location="start")
    assert target.read_bytes() == encoded(f"top{eol}first{eol}")


@pytest.mark.parametrize("eol", EOLS)
def test_line_ensure_is_idempotent(target, encoded, eol):
    target.write_bytes(encoded(f"first{eol}last{eol}"))
    kwargs = {"content": "new", "after": r"^first$", "mode": "ensure"}
    assert filemod.line(str(target), **kwargs)
    expected = encoded(f"first{eol}new{eol}last{eol}")
    assert target.read_bytes() == expected
    assert not filemod.line(str(target), **kwargs)
    assert target.read_bytes() == expected


@pytest.mark.parametrize("eol", EOLS)
def test_line_delete_first_line(target, encoded, eol):
    target.write_bytes(encoded(f"foo{eol}bar{eol}"))
    filemod.line(str(target), match=r"^foo$", mode="delete")
    assert target.read_bytes() == encoded(f"bar{eol}")


def test_line_test_mode_does_not_write(target, encoded):
    original = encoded("foo\r\n")
    target.write_bytes(original)
    with patch.dict(filemod.__opts__, {"test": True}):
        ret = filemod.line(str(target), content="bar", match=r"^foo$", mode="replace")
    assert "+bar" in ret
    assert target.read_bytes() == original


def test_line_invalid_bom_file_raises(target):
    target.write_bytes(INVALID_UTF16)
    with pytest.raises(SaltInvocationError, match="binary file"):
        filemod.line(str(target), content="new", mode="ensure", location="end")
    assert target.read_bytes() == INVALID_UTF16


# --------------------------------------------------------------------------
# file.comment_line
# --------------------------------------------------------------------------


@pytest.mark.parametrize("eol", EOLS)
def test_comment_line_first_line(target, encoded, eol):
    target.write_bytes(encoded(f"foo{eol}bar{eol}"))
    ret = filemod.comment_line(str(target), r"^foo$", backup=False)
    assert "+#foo" in ret
    assert "\ufeff" not in ret
    assert target.read_bytes() == encoded(f"#foo{eol}bar{eol}")


@pytest.mark.parametrize("eol", EOLS)
def test_uncomment_line(target, encoded, eol):
    target.write_bytes(encoded(f"bar{eol}#foo{eol}"))
    filemod.comment_line(str(target), r"^foo$", cmnt=False, backup=False)
    assert target.read_bytes() == encoded(f"bar{eol}foo{eol}")


def test_comment_line_backup(target, encoded):
    original = encoded("foo\r\n")
    target.write_bytes(original)
    filemod.comment_line(str(target), r"^foo$")
    assert target.read_bytes() == encoded("#foo\r\n")
    assert (target.parent / "target.txt.bak").read_bytes() == original


def test_comment_line_no_match(target, encoded):
    original = encoded("foo\r\n")
    target.write_bytes(original)
    assert filemod.comment_line(str(target), r"^missing$") is False
    assert target.read_bytes() == original


def test_comment_line_invalid_bom_file_raises(target):
    target.write_bytes(INVALID_UTF16)
    with pytest.raises(SaltInvocationError, match="binary file"):
        filemod.comment_line(str(target), r"^foo$")
    assert target.read_bytes() == INVALID_UTF16


# --------------------------------------------------------------------------
# file.blockreplace
# --------------------------------------------------------------------------


def _blockreplace(path, **kwargs):
    kwargs.setdefault("content", "new")
    kwargs.setdefault("append_newline", True)
    kwargs.setdefault("backup", False)
    return filemod.blockreplace(str(path), "# start", "# end", **kwargs)


@pytest.mark.parametrize("eol", EOLS)
def test_blockreplace_marker_on_first_line(target, encoded, eol, no_check_perms):
    target.write_bytes(encoded(f"# start{eol}old{eol}# end{eol}rest{eol}"))
    ret = _blockreplace(target)
    assert "+new" in ret
    assert "\ufeff" not in ret
    assert target.read_bytes() == encoded(f"# start{eol}new{eol}# end{eol}rest{eol}")


@pytest.mark.parametrize("eol", EOLS)
def test_blockreplace_prepend_goes_after_bom(target, encoded, eol, no_check_perms):
    target.write_bytes(encoded(f"existing{eol}"))
    _blockreplace(target, prepend_if_not_found=True)
    expected = encoded(f"# start{eol}new{eol}# end{eol}existing{eol}")
    assert target.read_bytes() == expected
    assert not _blockreplace(target, prepend_if_not_found=True)
    assert target.read_bytes() == expected


@pytest.mark.parametrize("eol", EOLS)
def test_blockreplace_append(target, encoded, eol, no_check_perms):
    target.write_bytes(encoded(f"existing{eol}"))
    _blockreplace(target, append_if_not_found=True)
    assert target.read_bytes() == encoded(
        f"existing{eol}# start{eol}new{eol}# end{eol}"
    )


def test_blockreplace_utf8_bom_prepend_goes_after_bom(target, no_check_perms):
    target.write_bytes(codecs.BOM_UTF8 + b"existing\n")
    _blockreplace(target, prepend_if_not_found=True)
    assert target.read_bytes() == codecs.BOM_UTF8 + b"# start\nnew\n# end\nexisting\n"


def test_blockreplace_invalid_bom_file_raises(target, no_check_perms):
    target.write_bytes(INVALID_UTF16)
    with pytest.raises(SaltInvocationError, match="binary file"):
        _blockreplace(target, append_if_not_found=True)
    assert target.read_bytes() == INVALID_UTF16


# --------------------------------------------------------------------------
# Files without a UTF-16/32 BOM keep the existing behavior
# --------------------------------------------------------------------------


def test_text_file_append_unchanged(target):
    target.write_bytes(b"first\n")
    filemod.append(str(target), "second")
    assert target.read_bytes() == b"first\nsecond\n"


def test_text_file_prepend_unchanged(target):
    target.write_bytes(b"first\r\n")
    filemod.prepend(str(target), "zero")
    assert target.read_bytes() == b"zero\r\nfirst\r\n"


@pytest.mark.parametrize("eol", [b"\n", b"\r\n"], ids=["lf", "crlf"])
def test_text_file_line_replace_keeps_eol(target, eol):
    """
    Replacing the only line of a file keeps its line ending instead of using
    the system's.
    """
    target.write_bytes(b"foo = 1" + eol)
    filemod.line(str(target), content="foo = 2", match="^foo", mode="replace")
    assert target.read_bytes() == b"foo = 2" + eol


def test_text_file_comment_line_unchanged(target):
    target.write_bytes(b"foo\nbar\n")
    filemod.comment_line(str(target), r"^bar$", backup=False)
    assert target.read_bytes() == b"foo\n#bar\n"


def test_binary_file_comment_line_still_raises(target):
    data = b"\x00\x01\x02\x03foo"
    target.write_bytes(data)
    with pytest.raises(SaltInvocationError, match="binary file"):
        filemod.comment_line(str(target), r"foo")
    assert target.read_bytes() == data
