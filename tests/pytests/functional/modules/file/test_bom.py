"""
Functional tests for file module functions that edit lines in files that start
with a UTF-16 or UTF-32 byte order mark (issue #65906).

These files contain null bytes, so the text check treats them as binary. They
are detected from the byte order mark, edited as text, and written back with
the byte order mark, byte order and line endings unchanged. Files are written
and compared as bytes so newline translation never interferes.
"""

import codecs

import pytest

from salt.exceptions import SaltInvocationError

pytestmark = [
    pytest.mark.windows_whitelisted,
]

BOM_ENCODINGS = [
    pytest.param(("utf-16-le", codecs.BOM_UTF16_LE), id="utf-16-le"),
    pytest.param(("utf-16-be", codecs.BOM_UTF16_BE), id="utf-16-be"),
    pytest.param(("utf-32-le", codecs.BOM_UTF32_LE), id="utf-32-le"),
    pytest.param(("utf-32-be", codecs.BOM_UTF32_BE), id="utf-32-be"),
    pytest.param(("utf-8", codecs.BOM_UTF8), id="utf-8"),
]

EOLS = [
    pytest.param("\n", id="lf"),
    pytest.param("\r\n", id="crlf"),
]

# An unpaired high surrogate after a UTF-16-LE BOM is not valid UTF-16
INVALID_UTF16 = codecs.BOM_UTF16_LE + b"\x00\xd8\x00\x00\x01\x02"


@pytest.fixture(scope="module")
def file(modules):
    return modules.file


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


@pytest.mark.parametrize("eol", EOLS)
def test_append(file, target, encoded, eol):
    target.write_bytes(encoded(f"first{eol}"))
    file.append(str(target), "second", "third")
    assert target.read_bytes() == encoded(f"first{eol}second{eol}third{eol}")


@pytest.mark.parametrize("eol", EOLS)
def test_prepend(file, target, encoded, eol):
    target.write_bytes(encoded(f"existing{eol}"))
    file.prepend(str(target), "first", "second")
    assert target.read_bytes() == encoded(f"first{eol}second{eol}existing{eol}")


@pytest.mark.parametrize("eol", EOLS)
def test_line_replace(file, target, encoded, eol):
    target.write_bytes(encoded(f"foo = 1{eol}bar{eol}"))
    ret = file.line(str(target), content="foo = 2", match=r"^foo = .*$", mode="replace")
    assert "+foo = 2" in ret
    assert "\ufeff" not in ret
    assert target.read_bytes() == encoded(f"foo = 2{eol}bar{eol}")


@pytest.mark.parametrize("eol", EOLS)
def test_line_insert_start(file, target, encoded, eol):
    target.write_bytes(encoded(f"first{eol}"))
    file.line(str(target), content="top", mode="insert", location="start")
    assert target.read_bytes() == encoded(f"top{eol}first{eol}")


@pytest.mark.parametrize("eol", EOLS)
def test_line_ensure_is_idempotent(file, target, encoded, eol):
    target.write_bytes(encoded(f"first{eol}last{eol}"))
    kwargs = {"content": "new", "after": r"^first$", "mode": "ensure"}
    expected = encoded(f"first{eol}new{eol}last{eol}")
    assert file.line(str(target), **kwargs)
    assert target.read_bytes() == expected
    assert not file.line(str(target), **kwargs)
    assert target.read_bytes() == expected


@pytest.mark.parametrize("eol", EOLS)
def test_line_delete(file, target, encoded, eol):
    target.write_bytes(encoded(f"foo{eol}bar{eol}"))
    file.line(str(target), match=r"^foo$", mode="delete")
    assert target.read_bytes() == encoded(f"bar{eol}")


@pytest.mark.parametrize("eol", EOLS)
def test_comment_line(file, target, encoded, eol):
    target.write_bytes(encoded(f"foo{eol}bar{eol}"))
    ret = file.comment_line(str(target), r"^foo$", backup=False)
    assert "+#foo" in ret
    assert "\ufeff" not in ret
    assert target.read_bytes() == encoded(f"#foo{eol}bar{eol}")

    file.comment_line(str(target), r"^foo$", cmnt=False, backup=False)
    assert target.read_bytes() == encoded(f"foo{eol}bar{eol}")


def test_comment_line_backup(file, target, encoded):
    original = encoded("foo\r\n")
    target.write_bytes(original)
    file.comment_line(str(target), r"^foo$")
    assert target.read_bytes() == encoded("#foo\r\n")
    assert (target.parent / "target.txt.bak").read_bytes() == original


def _blockreplace(file, path, **kwargs):
    kwargs.setdefault("content", "new")
    kwargs.setdefault("append_newline", True)
    kwargs.setdefault("backup", False)
    return file.blockreplace(str(path), "# start", "# end", **kwargs)


@pytest.mark.parametrize("eol", EOLS)
def test_blockreplace_marker_on_first_line(file, target, encoded, eol):
    target.write_bytes(encoded(f"# start{eol}old{eol}# end{eol}rest{eol}"))
    ret = _blockreplace(file, target)
    assert "+new" in ret
    assert "\ufeff" not in ret
    assert target.read_bytes() == encoded(f"# start{eol}new{eol}# end{eol}rest{eol}")


@pytest.mark.parametrize("eol", EOLS)
def test_blockreplace_prepend_is_idempotent(file, target, encoded, eol):
    target.write_bytes(encoded(f"existing{eol}"))
    expected = encoded(f"# start{eol}new{eol}# end{eol}existing{eol}")
    _blockreplace(file, target, prepend_if_not_found=True)
    assert target.read_bytes() == expected
    assert not _blockreplace(file, target, prepend_if_not_found=True)
    assert target.read_bytes() == expected


@pytest.mark.parametrize("eol", EOLS)
def test_blockreplace_append(file, target, encoded, eol):
    target.write_bytes(encoded(f"existing{eol}"))
    _blockreplace(file, target, append_if_not_found=True)
    assert target.read_bytes() == encoded(
        f"existing{eol}# start{eol}new{eol}# end{eol}"
    )


@pytest.mark.parametrize(
    "func,args,kwargs",
    [
        pytest.param("append", ("new",), {}, id="append"),
        pytest.param("prepend", ("new",), {}, id="prepend"),
        pytest.param(
            "line",
            (),
            {"content": "new", "mode": "ensure", "location": "end"},
            id="line",
        ),
        pytest.param("comment_line", (r"^foo$",), {}, id="comment_line"),
        pytest.param(
            "blockreplace",
            ("# start", "# end"),
            {"content": "new", "append_if_not_found": True},
            id="blockreplace",
        ),
    ],
)
def test_invalid_bom_file_raises(file, target, func, args, kwargs):
    """
    A file that starts with a byte order mark but does not decode in the
    encoding it names is rejected and left untouched.
    """
    target.write_bytes(INVALID_UTF16)
    with pytest.raises(SaltInvocationError, match="binary file"):
        getattr(file, func)(str(target), *args, **kwargs)
    assert target.read_bytes() == INVALID_UTF16
    assert not (target.parent / "target.txt.bak").exists()


def test_text_file_append_unchanged(file, target):
    target.write_bytes(b"first\n")
    file.append(str(target), "second")
    assert target.read_bytes() == b"first\nsecond\n"


def test_text_file_prepend_unchanged(file, target):
    target.write_bytes(b"first\r\n")
    file.prepend(str(target), "zero")
    assert target.read_bytes() == b"zero\r\nfirst\r\n"


def test_text_file_comment_line_unchanged(file, target):
    target.write_bytes(b"foo\nbar\n")
    file.comment_line(str(target), r"^bar$", backup=False)
    assert target.read_bytes() == b"foo\n#bar\n"


def test_binary_file_comment_line_still_raises(file, target):
    data = b"\x00\x01\x02\x03foo"
    target.write_bytes(data)
    with pytest.raises(SaltInvocationError, match="binary file"):
        file.comment_line(str(target), r"foo")
    assert target.read_bytes() == data
