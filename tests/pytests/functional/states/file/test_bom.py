"""
Functional tests for file states that edit lines in files that start with a
UTF-16 or UTF-32 byte order mark (issue #65906).

Each state reports a text diff in test mode without writing, changes the file
on the first run, and reports no changes on later runs. The byte order mark,
byte order and line endings are preserved.
"""

import codecs

import pytest

pytestmark = [
    pytest.mark.windows_whitelisted,
]

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


def _converges(state, target, original, expected, **kwargs):
    target.write_bytes(original)

    ret = state(name=str(target), test=True, **kwargs)
    assert ret.result is None
    assert ret.changes
    assert ret.changes.get("diff") != "Replace binary file"
    assert target.read_bytes() == original

    ret = state(name=str(target), **kwargs)
    assert ret.result is True
    assert ret.changes
    assert ret.changes.get("diff") != "Replace binary file"
    assert target.read_bytes() == expected

    for _ in range(2):
        ret = state(name=str(target), **kwargs)
        assert ret.result is True
        assert not ret.changes
        assert target.read_bytes() == expected


@pytest.mark.parametrize("eol", EOLS)
def test_append(file, target, encoded, eol):
    _converges(
        file.append,
        target,
        encoded(f"first{eol}"),
        encoded(f"first{eol}second{eol}third{eol}"),
        text=["second", "third"],
    )


@pytest.mark.parametrize("eol", EOLS)
def test_prepend(file, target, encoded, eol):
    _converges(
        file.prepend,
        target,
        encoded(f"existing{eol}"),
        encoded(f"first{eol}second{eol}existing{eol}"),
        text=["first", "second"],
    )


@pytest.mark.parametrize("eol", EOLS)
def test_prepend_header(file, target, encoded, eol):
    _converges(
        file.prepend,
        target,
        encoded(f"existing{eol}"),
        encoded(f"# managed{eol}existing{eol}"),
        text="# managed",
        header=True,
    )


@pytest.mark.parametrize("eol", EOLS)
def test_comment(file, target, encoded, eol):
    _converges(
        file.comment,
        target,
        encoded(f"foo = 1{eol}bar{eol}"),
        encoded(f"#foo = 1{eol}bar{eol}"),
        regex=r"^foo = 1$",
        backup=False,
    )


@pytest.mark.parametrize("eol", EOLS)
def test_uncomment(file, target, encoded, eol):
    _converges(
        file.uncomment,
        target,
        encoded(f"bar{eol}#foo = 1{eol}"),
        encoded(f"bar{eol}foo = 1{eol}"),
        regex=r"^foo = 1$",
        backup=False,
    )


@pytest.mark.parametrize("eol", EOLS)
def test_line(file, target, encoded, eol):
    _converges(
        file.line,
        target,
        encoded(f"first{eol}last{eol}"),
        encoded(f"first{eol}new{eol}last{eol}"),
        content="new",
        after=r"^first$",
        mode="ensure",
    )


@pytest.mark.parametrize("eol", EOLS)
def test_blockreplace(file, target, encoded, eol):
    _converges(
        file.blockreplace,
        target,
        encoded(f"existing{eol}"),
        encoded(f"# start{eol}new{eol}# end{eol}existing{eol}"),
        marker_start="# start",
        marker_end="# end",
        content="new",
        prepend_if_not_found=True,
        backup=False,
    )
