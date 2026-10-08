"""
Tests for CRLF line ending handling in the file execution module.

Python's ``re`` only treats ``\\n`` as a line boundary and the file module does
no newline translation, so on a CRLF file ``.*`` swallows the ``\\r`` and ``$``
never matches before ``\\r\\n``. These tests make sure CRLF files behave like LF
files (see issue #52457).

All files are written as bytes so the tests behave identically on every
platform.
"""

import os

import pytest

import salt.modules.cmdmod as cmdmod
import salt.modules.config as configmod
import salt.modules.file as filemod
import salt.utils.files
import salt.utils.stringutils


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
                "files.is_text": salt.utils.files.is_text,
                "stringutils.get_diff": salt.utils.stringutils.get_diff,
            },
        }
    }


@pytest.fixture
def make_file(tmp_path):
    def _make_file(data):
        path = tmp_path / "target.txt"
        path.write_bytes(data)
        return path

    return _make_file


# --------------------------------------------------------------------------
# file.replace
# --------------------------------------------------------------------------


def test_replace_dot_star_does_not_eat_cr(make_file):
    """
    ``.*`` must not consume the ``\\r`` of a CRLF line terminator. Replacing a
    line with identical text is a no-op and must leave the file untouched.
    """
    original = b"host all md5\r\nhost two md5\r\n"
    path = make_file(original)
    ret = filemod.replace(
        str(path),
        pattern=r"^host all.*",
        repl="host all md5",
        backup=False,
        show_changes=False,
    )
    assert ret is False
    assert path.read_bytes() == original


def test_replace_dollar_matches_before_crlf(make_file):
    """
    ``$`` must match at the end of a CRLF terminated line.
    """
    path = make_file(b"host all md5\r\nhost two md5\r\n")
    ret = filemod.replace(
        str(path),
        pattern=r"^host all md5$",
        repl="host all trust",
        backup=False,
        show_changes=False,
    )
    assert ret is True
    assert path.read_bytes() == b"host all trust\r\nhost two md5\r\n"


def test_replace_dot_star_changed_line_keeps_crlf(make_file):
    """
    When a line really changes, every line terminator stays CRLF.
    """
    path = make_file(b"key = old\r\nother = 1\r\n")
    ret = filemod.replace(
        str(path),
        pattern=r"^key = .*",
        repl="key = new",
        backup=False,
        show_changes=False,
    )
    assert ret is True
    assert path.read_bytes() == b"key = new\r\nother = 1\r\n"


def test_replace_template_newline_in_repl_becomes_crlf(make_file):
    """
    A ``\\n`` escape in ``repl`` expands to a line terminator that matches the
    file, so the result does not mix endings.
    """
    path = make_file(b"a\r\nx\r\nb\r\n")
    filemod.replace(
        str(path),
        pattern=r"^x$",
        repl=r"x1\nx2",
        backup=False,
        show_changes=False,
    )
    assert path.read_bytes() == b"a\r\nx1\r\nx2\r\nb\r\n"


def test_replace_explicit_cr_in_pattern_is_honored(make_file):
    """
    A pattern that explicitly targets ``\\r`` keeps working, for example to
    convert a CRLF file to LF.
    """
    path = make_file(b"a\r\nb\r\n")
    ret = filemod.replace(
        str(path),
        pattern=r"\r$",
        repl="",
        backup=False,
        show_changes=False,
    )
    assert ret is True
    assert path.read_bytes() == b"a\nb\n"


def test_replace_lf_file_unchanged_behavior(make_file):
    original = b"host all md5\nhost two md5\n"
    path = make_file(original)
    assert (
        filemod.replace(
            str(path),
            pattern=r"^host all.*",
            repl="host all md5",
            backup=False,
            show_changes=False,
        )
        is False
    )
    assert path.read_bytes() == original


def test_replace_mixed_endings_are_not_normalized(make_file):
    """
    Only pure CRLF files are treated as CRLF; mixed files keep their endings.
    """
    path = make_file(b"a\r\nb\nc\r\n")
    filemod.replace(
        str(path),
        pattern=r"^b$",
        repl="B",
        backup=False,
        show_changes=False,
    )
    assert path.read_bytes() == b"a\r\nB\nc\r\n"


def test_replace_append_if_not_found_is_idempotent_on_crlf(make_file):
    """
    Reproduces #52457: two ``file.replace`` states appending to the same file
    must reach a fixed point after the first run, not the third.
    """
    path = make_file(b"existing\r\n")
    states = [
        (r"^host\s+all\s+all\s+0\.0\.0\.0/0\s+md5.*", "host all all 0.0.0.0/0 md5"),
        (r"^host\s+all\s+all\s+::/0\s+md5.*", "host all all ::/0 md5"),
    ]

    def run():
        return [
            filemod.replace(
                str(path),
                pattern=pattern,
                repl=repl,
                append_if_not_found=True,
                backup=False,
                show_changes=False,
            )
            for pattern, repl in states
        ]

    assert run() == [True, True]
    expected = (
        b"existing\r\n" b"host all all 0.0.0.0/0 md5\r\n" b"host all all ::/0 md5\r\n"
    )
    assert path.read_bytes() == expected
    assert run() == [False, False]
    assert path.read_bytes() == expected


def test_replace_append_if_not_found_follows_lf_endings(make_file):
    path = make_file(b"existing\n")
    filemod.replace(
        str(path),
        pattern=r"^new$",
        repl="new",
        append_if_not_found=True,
        backup=False,
        show_changes=False,
    )
    assert path.read_bytes() == b"existing\nnew\n"


def test_replace_prepend_if_not_found_follows_crlf_endings(make_file):
    path = make_file(b"existing\r\n")
    filemod.replace(
        str(path),
        pattern=r"^new$",
        repl="new",
        prepend_if_not_found=True,
        backup=False,
        show_changes=False,
    )
    assert path.read_bytes() == b"new\r\nexisting\r\n"


def test_replace_encoding_dot_star_does_not_eat_cr(make_file):
    original = b"host all md5\r\nhost two md5\r\n"
    path = make_file(original)
    ret = filemod.replace(
        str(path),
        pattern=r"^host all.*",
        repl="host all md5",
        encoding="utf-8",
        backup=False,
        show_changes=False,
    )
    assert ret is False
    assert path.read_bytes() == original


def test_replace_encoding_dollar_matches_before_crlf(make_file):
    path = make_file(b"host all md5\r\nhost two md5\r\n")
    ret = filemod.replace(
        str(path),
        pattern=r"^host all md5$",
        repl="host all trust",
        encoding="utf-8",
        backup=False,
        show_changes=False,
    )
    assert ret is True
    assert path.read_bytes() == b"host all trust\r\nhost two md5\r\n"


def test_replace_encoding_append_if_not_found_is_idempotent(make_file):
    path = make_file(b"existing\r\n")

    def run():
        return filemod.replace(
            str(path),
            pattern=r"^new.*",
            repl="new",
            append_if_not_found=True,
            encoding="utf-8",
            backup=False,
            show_changes=False,
        )

    assert run() is True
    assert path.read_bytes() == b"existing\r\nnew\r\n"
    assert run() is False
    assert path.read_bytes() == b"existing\r\nnew\r\n"


# --------------------------------------------------------------------------
# file.search / file.contains_regex
# --------------------------------------------------------------------------


def test_search_dollar_matches_crlf(make_file):
    path = make_file(b"alpha\r\nbeta\r\n")
    assert filemod.search(str(path), r"^alpha$") is True
    assert filemod.search(str(path), r"^alpha$", multiline=True) is True
    assert filemod.search(str(path), r"^gamma$") is False


def test_contains_regex_dollar_matches_crlf(make_file):
    path = make_file(b"alpha\r\nbeta\r\n")
    assert filemod.contains_regex(str(path), r"^beta$") is True
    assert filemod.contains_regex(str(path), r"^gamma$") is False


# --------------------------------------------------------------------------
# file.comment_line / file.comment / file.uncomment
# --------------------------------------------------------------------------


def test_comment_line_dollar_matches_crlf(make_file):
    path = make_file(b"foo\r\nbar\r\n")
    ret = filemod.comment_line(str(path), r"^foo$", backup=False)
    assert ret
    assert path.read_bytes() == b"#foo\r\nbar\r\n"


def test_uncomment_line_dollar_matches_crlf(make_file):
    path = make_file(b"#foo\r\nbar\r\n")
    ret = filemod.comment_line(str(path), r"^foo$", cmnt=False, backup=False)
    assert ret
    assert path.read_bytes() == b"foo\r\nbar\r\n"


def test_comment_dollar_matches_crlf(make_file):
    path = make_file(b"foo\r\nbar\r\n")
    ret = filemod.comment(str(path), r"^foo$", backup=False)
    assert ret
    assert path.read_bytes() == b"#foo\r\nbar\r\n"


# --------------------------------------------------------------------------
# file.line
# --------------------------------------------------------------------------


def test_line_replace_dollar_matches_crlf(make_file):
    path = make_file(b"foo\r\nbar\r\n")
    ret = filemod.line(str(path), content="baz", match=r"^foo$", mode="replace")
    assert ret
    assert path.read_bytes() == b"baz\r\nbar\r\n"


@pytest.mark.parametrize("eol", [b"\n", b"\r\n"], ids=["lf", "crlf"])
def test_line_insert_after_first_line_follows_file_endings(make_file, eol):
    """
    The line ending of an inserted line comes from the previous line. For the
    second line of the file it used to be taken from the line itself, which
    has none yet, so os.linesep was used.
    """
    path = make_file(eol.join([b"first", b"second", b"third", b""]))
    ret = filemod.line(
        str(path), content="new", after=r"^first$", mode="insert", backup=False
    )
    assert ret
    assert path.read_bytes() == eol.join([b"first", b"new", b"second", b"third", b""])


def test_line_delete_dollar_matches_crlf(make_file):
    path = make_file(b"foo\r\nbar\r\n")
    ret = filemod.line(str(path), match=r"^foo$", mode="delete")
    assert ret
    assert path.read_bytes() == b"bar\r\n"


# --------------------------------------------------------------------------
# file.append / file.prepend / file.write
# --------------------------------------------------------------------------


def test_append_follows_crlf_endings(make_file):
    path = make_file(b"foo\r\nbar")
    filemod.append(str(path), "baz")
    assert path.read_bytes() == b"foo\r\nbar\r\nbaz\r\n"


def test_append_follows_lf_endings(make_file):
    path = make_file(b"foo\nbar")
    filemod.append(str(path), "baz")
    assert path.read_bytes() == b"foo\nbar\nbaz\n"


def test_append_to_file_ending_in_newline_adds_no_blank_line(make_file):
    path = make_file(b"foo\n")
    filemod.append(str(path), "bar")
    assert path.read_bytes() == b"foo\nbar\n"

    path = make_file(b"foo\r\n")
    filemod.append(str(path), "bar", "baz")
    assert path.read_bytes() == b"foo\r\nbar\r\nbaz\r\n"


def test_append_to_empty_file_uses_os_linesep(make_file):
    path = make_file(b"")
    filemod.append(str(path), "bar")
    expected = salt.utils.stringutils.to_bytes("bar" + os.linesep)
    assert path.read_bytes() == expected


def test_prepend_follows_crlf_endings(make_file):
    path = make_file(b"foo\r\nbar\r\n")
    filemod.prepend(str(path), "baz")
    assert path.read_bytes() == b"baz\r\nfoo\r\nbar\r\n"


def test_prepend_follows_lf_endings(make_file):
    path = make_file(b"foo\nbar\n")
    filemod.prepend(str(path), "baz")
    assert path.read_bytes() == b"baz\nfoo\nbar\n"


def test_write_always_uses_lf_even_on_crlf_file(make_file):
    """
    file.write intentionally does not follow the line endings of the file it
    overwrites, unlike file.append and file.prepend. It replaces the whole
    file and writes the caller's strings as given (callers such as
    iptables.save pass multi-line strings with their own newlines), so the
    only terminator it adds is "\\n". Callers that want CRLF pass "\\r\\n".
    Do not "fix" this without reading the note in the file.write docstring.
    """
    path = make_file(b"old\r\ncontent\r\n")
    filemod.write(str(path), "a", "b")
    assert path.read_bytes() == b"a\nb\n"


def test_write_passes_embedded_crlf_through(make_file):
    path = make_file(b"old\n")
    filemod.write(str(path), "a\r\nb")
    assert path.read_bytes() == b"a\r\nb\n"


def test_write_new_file_uses_lf(tmp_path):
    path = tmp_path / "new.txt"
    filemod.write(str(path), "a", "b")
    assert path.read_bytes() == b"a\nb\n"
