"""
Functional tests for ``file.replace`` on files that start with a UTF-16 or
UTF-32 byte order mark (issue #65906).

These files contain null bytes, so the text check treats them as binary. They
are detected from the byte order mark without an explicit ``encoding``, and
the byte order mark, byte order and line endings are written back unchanged.
Files are written as bytes so newline translation never interferes.
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


@pytest.fixture(scope="module")
def file(modules):
    return modules.file


@pytest.fixture(params=BOM_ENCODINGS)
def encoded(request):
    """
    Return a function that encodes text the way the file under test is
    encoded, including the byte order mark.
    """
    codec, bom = request.param

    def _encode(text):
        return bom + text.encode(codec)

    return _encode


def _lines(*lines, eol):
    return "".join(line + eol for line in lines)


@pytest.mark.parametrize("eol", EOLS)
def test_replace(file, tmp_path, encoded, eol):
    path = tmp_path / "settings.psd1"
    path.write_bytes(
        encoded(_lines("ModuleVersion = '1.0'", "PowerShellVersion = '2.0'", eol=eol))
    )

    ret = file.replace(
        str(path),
        pattern=r"PowerShellVersion\s+=\s+'2\.0'",
        repl="PowerShellVersion = '3.0'",
        backup=False,
    )

    assert "+PowerShellVersion = '3.0'" in ret
    assert path.read_bytes() == encoded(
        _lines("ModuleVersion = '1.0'", "PowerShellVersion = '3.0'", eol=eol)
    )


@pytest.mark.parametrize("eol", EOLS)
def test_replace_issue_65906_pattern(file, tmp_path, encoded, eol):
    """
    The pattern from the issue, anchored at the start of a line in the middle
    of the file. Passing ``flags`` replaces the default ``MULTILINE``, so it
    has to be listed for ``^`` to match at the start of every line.
    """
    initial = _lines(
        "one two", "three", "four", "      something=111111", "ten", "nine", eol=eol
    )
    path = tmp_path / "abc.txt"
    path.write_bytes(encoded(initial))

    file.replace(
        str(path),
        pattern=r"^(.*)something=\d+",
        repl=r"\1something=123",
        flags=["IGNORECASE", "MULTILINE"],
        backup=False,
    )

    assert path.read_bytes() == encoded(
        initial.replace("something=111111", "something=123")
    )


@pytest.mark.parametrize("eol", EOLS)
def test_replace_end_anchor(file, tmp_path, encoded, eol):
    """
    ``$`` matches at the end of every line, including on CRLF files and on the
    first line right after the byte order mark.
    """
    path = tmp_path / "anchors.txt"
    path.write_bytes(encoded(_lines("key = 1", "other = 1", eol=eol)))

    file.replace(str(path), pattern=r"^(\w+) = 1$", repl=r"\1 = 2", backup=False)

    assert path.read_bytes() == encoded(_lines("key = 2", "other = 2", eol=eol))


@pytest.mark.parametrize("eol", EOLS)
def test_replace_is_idempotent(file, tmp_path, encoded, eol):
    path = tmp_path / "idempotent.txt"
    path.write_bytes(encoded(_lines("key = old", eol=eol)))

    kwargs = {"pattern": r"^key = .*$", "repl": "key = new", "backup": False}
    assert file.replace(str(path), show_changes=False, **kwargs) is True
    expected = encoded(_lines("key = new", eol=eol))
    assert path.read_bytes() == expected

    assert file.replace(str(path), show_changes=False, **kwargs) is False
    assert path.read_bytes() == expected


@pytest.mark.parametrize("eol", EOLS)
def test_replace_append_if_not_found(file, tmp_path, encoded, eol):
    path = tmp_path / "append.txt"
    path.write_bytes(encoded(_lines("ModuleVersion = '1.0'", eol=eol)))
    expected = encoded(
        _lines("ModuleVersion = '1.0'", "PowerShellVersion = '3.0'", eol=eol)
    )

    for _ in range(3):
        file.replace(
            str(path),
            pattern=r"^PowerShellVersion\s*=.*$",
            repl="PowerShellVersion = '3.0'",
            append_if_not_found=True,
            backup=False,
        )
        assert path.read_bytes() == expected


@pytest.mark.parametrize("eol", EOLS)
def test_replace_prepend_if_not_found(file, tmp_path, encoded, eol):
    """
    The prepended line goes after the byte order mark.
    """
    path = tmp_path / "prepend.txt"
    path.write_bytes(encoded(_lines("existing", eol=eol)))
    expected = encoded(_lines("# managed", "existing", eol=eol))

    for _ in range(3):
        file.replace(
            str(path),
            pattern=r"^# managed$",
            repl="# managed",
            prepend_if_not_found=True,
            backup=False,
        )
        assert path.read_bytes() == expected


def test_replace_backup(file, tmp_path, encoded):
    path = tmp_path / "backup.txt"
    original = encoded("key = old\r\n")
    path.write_bytes(original)

    file.replace(str(path), pattern="old", repl="new")

    assert path.read_bytes() == encoded("key = new\r\n")
    assert (tmp_path / "backup.txt.bak").read_bytes() == original


def test_replace_dry_run(file, tmp_path, encoded):
    path = tmp_path / "dry_run.txt"
    original = encoded("key = old\r\n")
    path.write_bytes(original)

    ret = file.replace(str(path), pattern="old", repl="new", dry_run=True)

    assert "+key = new" in ret
    assert "\ufeff" not in ret
    assert path.read_bytes() == original
    assert not (tmp_path / "dry_run.txt.bak").exists()


def test_replace_search_only(file, tmp_path, encoded):
    path = tmp_path / "search.txt"
    original = encoded("first\r\nsecond\r\n")
    path.write_bytes(original)

    assert file.replace(str(path), pattern=r"^first$", repl="", search_only=True)
    assert not file.replace(str(path), pattern=r"third", repl="", search_only=True)
    assert path.read_bytes() == original


def test_replace_non_ascii(file, tmp_path, encoded):
    path = tmp_path / "unicode.txt"
    path.write_bytes(encoded("name = caf\u00e9\r\ncity = \u6771\u4eac\r\n"))

    file.replace(str(path), pattern="\u6771\u4eac", repl="\u5927\u962a", backup=False)

    assert path.read_bytes() == encoded("name = caf\u00e9\r\ncity = \u5927\u962a\r\n")


@pytest.mark.parametrize(
    "data",
    [
        pytest.param("key = old\r\n".encode("utf-16-le"), id="utf-16-without-bom"),
        pytest.param(b"\x00\x01\x02\x03key = old", id="binary"),
        pytest.param(
            codecs.BOM_UTF16_LE + b"\x00\xd8\x00\x00\x01\x02", id="invalid-utf-16"
        ),
        pytest.param(
            codecs.BOM_UTF32_LE + b"\x00\x00\x11\x00\x01\x02\x03\x04",
            id="invalid-utf-32",
        ),
    ],
)
def test_replace_binary_raises(file, tmp_path, data):
    """
    Files that cannot be identified from a byte order mark, or that do not
    decode in the encoding it names, are rejected and left untouched.
    """
    path = tmp_path / "data.bin"
    path.write_bytes(data)

    with pytest.raises(SaltInvocationError, match="binary file"):
        file.replace(str(path), pattern="old", repl="new")
    assert path.read_bytes() == data
    assert not (tmp_path / "data.bin.bak").exists()


@pytest.mark.parametrize(
    "data",
    [
        pytest.param(b"key = old\r\nnext\r\n", id="ascii"),
        pytest.param("key = old caf\u00e9\n".encode("utf-8"), id="utf-8"),
        pytest.param(
            codecs.BOM_UTF8 + "key = old caf\u00e9\r\n".encode("utf-8"),
            id="utf-8-bom",
        ),
    ],
)
def test_replace_text_files_unchanged_behavior(file, tmp_path, data):
    """
    Files that already pass the text check are handled as before.
    """
    path = tmp_path / "text.txt"
    path.write_bytes(data)

    file.replace(str(path), pattern="key = old", repl="key = new", backup=False)

    assert path.read_bytes() == data.replace(b"key = old", b"key = new")
