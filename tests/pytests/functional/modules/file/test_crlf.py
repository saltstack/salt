"""
Functional tests for line ending handling in the file execution module.

Python's ``re`` only treats ``\\n`` as a line boundary and the file module
does no newline translation, so on a CRLF file ``.*`` swallows the ``\\r`` and
``$`` never matches before ``\\r\\n`` (issue #52457).

Most tests here are metamorphic: they run a function on a file with LF line
endings and on the same file converted to CRLF, and require that

* both calls return the same value (ignoring ``\\r\\n`` vs ``\\n`` in diffs), and
* the CRLF file ends up with exactly the bytes of the LF result converted to
  CRLF, so no line ending is lost, mixed or doubled.

This makes CRLF files behave like LF files, and the same assertions run on
Linux, macOS and Windows. Files are written as bytes so ``os.linesep`` and
newline translation never interfere.
"""

import pytest

pytestmark = [
    pytest.mark.windows_whitelisted,
]

HOSTS = (
    b"# header\n"
    b"host all all 0.0.0.0/0 md5\n"
    b"host all all ::/0 md5  \n"
    b"\n"
    b"key = value\n"
    b"Foo Bar\n"
)
# No trailing newline on the last line
TAIL = b"alpha\nbeta\ngamma"
COMMENTED = b"#host one\n# key = 1\nplain\n"


@pytest.fixture(scope="module")
def file(modules):
    return modules.file


def _to_crlf(data):
    return data.replace(b"\n", b"\r\n")


def _normalize(ret, path):
    if isinstance(ret, str):
        return ret.replace(str(path), "<PATH>").replace("\r\n", "\n")
    return ret


def _run_both(file, tmp_path, func, initial, *args, **kwargs):
    """
    Call ``file.<func>`` on an LF and a CRLF copy of ``initial``.

    Returns ``(lf_ret, crlf_ret, lf_bytes, crlf_bytes)``.
    """
    lf = tmp_path / "lf.txt"
    crlf = tmp_path / "crlf.txt"
    lf.write_bytes(initial)
    crlf.write_bytes(_to_crlf(initial))
    rets = []
    for path in (lf, crlf):
        try:
            ret = getattr(file, func)(str(path), *args, **kwargs)
        except Exception as exc:  # pylint: disable=broad-except
            ret = f"raised {type(exc).__name__}"
        rets.append(_normalize(ret, path))
    return rets[0], rets[1], lf.read_bytes(), crlf.read_bytes()


def _assert_equivalent(
    file, tmp_path, func, initial, *args, expect_changed=None, **kwargs
):
    lf_ret, crlf_ret, lf_bytes, crlf_bytes = _run_both(
        file, tmp_path, func, initial, *args, **kwargs
    )
    assert crlf_ret == lf_ret
    assert crlf_bytes == _to_crlf(lf_bytes)
    if expect_changed is not None:
        # Guard against tests that pass without exercising anything
        assert (lf_bytes != initial) is expect_changed


# ---------------------------------------------------------------------------
# file.replace
# ---------------------------------------------------------------------------

REPLACE_CASES = [
    pytest.param(
        HOSTS,
        {"pattern": r"^key = value$", "repl": "key = new"},
        True,
        id="dollar-anchor",
    ),
    pytest.param(
        HOSTS,
        {
            "pattern": r"^host all all 0\.0\.0\.0/0 md5.*",
            "repl": "host all all 0.0.0.0/0 md5",
        },
        False,
        id="dot-star-same-text-is-noop",
    ),
    pytest.param(
        HOSTS, {"pattern": r"^host.*", "repl": "H"}, True, id="dot-star-changes"
    ),
    pytest.param(
        HOSTS, {"pattern": r"[ \t]+$", "repl": ""}, True, id="trailing-whitespace"
    ),
    pytest.param(HOSTS, {"pattern": r"^$", "repl": "EMPTY"}, True, id="empty-lines"),
    pytest.param(
        HOSTS,
        {"pattern": r"^key\s*=\s*(\w+)$", "repl": r"\1-\1"},
        True,
        id="group-backreference",
    ),
    pytest.param(
        HOSTS,
        {"pattern": "foo bar", "repl": "X", "flags": ["IGNORECASE"]},
        True,
        id="flags-list",
    ),
    pytest.param(
        HOSTS,
        {"pattern": r"^host.*", "repl": "H", "count": 1},
        True,
        id="count",
    ),
    pytest.param(
        HOSTS,
        {
            "pattern": r"^key = value$",
            "repl": "C:\\dir",
            "backslash_literal": True,
        },
        True,
        id="backslash-literal",
    ),
    pytest.param(
        HOSTS,
        {"pattern": r"^key = value\s*", "repl": "key = value"},
        True,
        id="whitespace-class-consumes-newline",
    ),
    pytest.param(
        HOSTS,
        {"pattern": r"^host.*", "repl": "H", "dry_run": True},
        False,
        id="dry-run",
    ),
    pytest.param(
        HOSTS,
        {"pattern": r"^host.*", "repl": "H", "show_changes": False},
        True,
        id="no-show-changes",
    ),
    pytest.param(
        HOSTS,
        {"pattern": r"^host.*", "repl": "H", "bufsize": "file"},
        True,
        id="bufsize-file",
    ),
    pytest.param(
        HOSTS,
        {"pattern": r"^host.*", "repl": "H", "bufsize": 1},
        True,
        id="bufsize-line",
    ),
    pytest.param(
        HOSTS,
        {"pattern": r"^missing$", "repl": "appended", "append_if_not_found": True},
        True,
        id="append-if-not-found",
    ),
    pytest.param(
        TAIL,
        {"pattern": r"^delta$", "repl": "delta", "append_if_not_found": True},
        True,
        id="append-if-not-found-no-trailing-newline",
    ),
    pytest.param(
        HOSTS,
        {"pattern": r"^missing$", "repl": "prepended", "prepend_if_not_found": True},
        True,
        id="prepend-if-not-found",
    ),
    pytest.param(
        HOSTS,
        {
            "pattern": r"^missing$",
            "repl": "ignored",
            "not_found_content": "from-not-found-content",
            "append_if_not_found": True,
        },
        True,
        id="not-found-content",
    ),
    pytest.param(
        TAIL,
        {"pattern": r"^gamma$", "repl": "gamma", "append_if_not_found": True},
        False,
        id="append-if-not-found-already-present",
    ),
    pytest.param(
        HOSTS,
        {"pattern": r"^key = value$", "repl": "key = new", "encoding": "utf-8"},
        True,
        id="encoding-dollar-anchor",
    ),
    pytest.param(
        HOSTS,
        {
            "pattern": r"^host all all ::/0 md5.*",
            "repl": "host all all ::/0 md5",
            "encoding": "utf-8",
        },
        True,
        id="encoding-dot-star",
    ),
    pytest.param(
        HOSTS,
        {
            "pattern": r"^missing$",
            "repl": "appended",
            "append_if_not_found": True,
            "encoding": "utf-8",
        },
        True,
        id="encoding-append-if-not-found",
    ),
]


@pytest.mark.parametrize("content,kwargs,expect_changed", REPLACE_CASES)
def test_replace_crlf_matches_lf(file, tmp_path, content, kwargs, expect_changed):
    kwargs = dict(kwargs, backup=False)
    _assert_equivalent(
        file, tmp_path, "replace", content, expect_changed=expect_changed, **kwargs
    )


@pytest.mark.parametrize(
    "pattern,expected",
    [
        (r"^key = value$", True),
        (r"^host.*md5  $", True),
        (r"^$", True),
        (r"^zzz$", False),
    ],
)
def test_replace_search_only_crlf_matches_lf(file, tmp_path, pattern, expected):
    lf_ret, crlf_ret, lf_bytes, crlf_bytes = _run_both(
        file, tmp_path, "replace", HOSTS, pattern, "", search_only=True
    )
    assert lf_ret is expected
    assert crlf_ret is expected
    assert lf_bytes == HOSTS
    assert crlf_bytes == _to_crlf(HOSTS)


def test_replace_converges_after_one_run_on_crlf(file, tmp_path):
    """
    The scenario of #52457: two replace calls appending to the same CRLF file
    must reach a fixed point after the first run.
    """
    path = tmp_path / "pg_hba.conf"
    path.write_bytes(b"# managed\r\n")
    calls = [
        (r"^host\s+all\s+all\s+0\.0\.0\.0/0\s+md5.*", "host all all 0.0.0.0/0 md5"),
        (r"^host\s+all\s+all\s+::/0\s+md5.*", "host all all ::/0 md5"),
    ]

    def run():
        return [
            file.replace(
                str(path),
                pattern=pattern,
                repl=repl,
                append_if_not_found=True,
                backup=False,
                show_changes=False,
            )
            for pattern, repl in calls
        ]

    assert run() == [True, True]
    expected = b"# managed\r\nhost all all 0.0.0.0/0 md5\r\nhost all all ::/0 md5\r\n"
    assert path.read_bytes() == expected
    for _ in range(2):
        assert run() == [False, False]
        assert path.read_bytes() == expected


def test_replace_explicit_cr_pattern_still_works(file, tmp_path):
    """
    A pattern that refers to ``\\r`` keeps working, for example to convert
    CRLF to LF.
    """
    path = tmp_path / "dos.txt"
    path.write_bytes(b"a\r\nb\r\n")
    assert file.replace(str(path), r"\r$", "", backup=False, show_changes=False)
    assert path.read_bytes() == b"a\nb\n"


def test_replace_mixed_line_endings_are_left_alone(file, tmp_path):
    """
    Files that are not CRLF throughout are not normalized, so the existing
    line endings survive and untouched lines are never rewritten.
    """
    path = tmp_path / "mixed.txt"
    path.write_bytes(b"a\r\nb\nc\r\n")
    assert file.replace(str(path), r"^b$", "B", backup=False, show_changes=False)
    assert path.read_bytes() == b"a\r\nB\nc\r\n"


# ---------------------------------------------------------------------------
# file.search and file.contains_regex
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("content", [HOSTS, TAIL], ids=["hosts", "tail"])
@pytest.mark.parametrize(
    "pattern",
    [r"^key = value$", r"^Foo Bar$", r"^gamma$", r"^$", r"^zzz$", r"md5  $", r"d\s*$"],
)
@pytest.mark.parametrize("multiline", [False, True])
def test_search_crlf_matches_lf(file, tmp_path, content, pattern, multiline):
    _assert_equivalent(
        file, tmp_path, "search", content, pattern, multiline=multiline, flags=8
    )


@pytest.mark.parametrize("pattern", [r"^key = value$", r"^Foo Bar$", r"^zzz$"])
def test_search_crlf_finds_dollar_anchored_line(file, tmp_path, pattern):
    lf = tmp_path / "lf.txt"
    crlf = tmp_path / "crlf.txt"
    lf.write_bytes(HOSTS)
    crlf.write_bytes(_to_crlf(HOSTS))
    expected = pattern != r"^zzz$"
    assert file.search(str(lf), pattern, multiline=True) is expected
    assert file.search(str(crlf), pattern, multiline=True) is expected


@pytest.mark.parametrize(
    "content,regex,lchar,expected",
    [
        (HOSTS, r"^key = value$", "", True),
        (HOSTS, r"^Foo Bar$", "", True),
        (HOSTS, r"^zzz$", "", False),
        (COMMENTED, r"^host one$", "#", True),
    ],
)
def test_contains_regex_crlf_matches_lf(
    file, tmp_path, content, regex, lchar, expected
):
    lf_ret, crlf_ret, _, _ = _run_both(
        file, tmp_path, "contains_regex", content, regex, lchar=lchar
    )
    assert lf_ret is expected
    assert crlf_ret is expected


# ---------------------------------------------------------------------------
# file.comment_line, file.comment and file.uncomment
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "content,regex,cmnt,expect_changed",
    [
        (HOSTS, r"^key = value$", True, True),
        (HOSTS, r"^host.*md5$", True, True),
        (HOSTS, r"^key", True, True),
        (HOSTS, r"^zzz$", True, False),
        (COMMENTED, r"^host one$", False, True),
        (COMMENTED, r"^key = 1$", False, True),
        (COMMENTED, r"^zzz$", False, False),
    ],
)
def test_comment_line_crlf_matches_lf(
    file, tmp_path, content, regex, cmnt, expect_changed
):
    _assert_equivalent(
        file,
        tmp_path,
        "comment_line",
        content,
        regex,
        cmnt=cmnt,
        backup=False,
        expect_changed=expect_changed,
    )


@pytest.mark.parametrize("func", ["comment", "uncomment"])
def test_comment_and_uncomment_crlf_match_lf(file, tmp_path, func):
    content = HOSTS if func == "comment" else COMMENTED
    regex = r"^key = value$" if func == "comment" else r"^host one$"
    _assert_equivalent(
        file, tmp_path, func, content, regex, backup=False, expect_changed=True
    )


# ---------------------------------------------------------------------------
# file.line
# ---------------------------------------------------------------------------

LINE_CASES = [
    pytest.param(
        {"mode": "replace", "match": r"^key.*$", "content": "key = new"},
        True,
        id="replace",
    ),
    pytest.param(
        {"mode": "replace", "match": r"^key = value$", "content": "key = new"},
        True,
        id="replace-dollar",
    ),
    pytest.param({"mode": "delete", "match": r"^Foo Bar$"}, True, id="delete-dollar"),
    pytest.param({"mode": "delete", "match": r"^zzz$"}, False, id="delete-no-match"),
    pytest.param(
        {"mode": "insert", "after": r"^# header$", "content": "inserted"},
        True,
        id="insert-after",
    ),
    pytest.param(
        {"mode": "insert", "before": r"^key = value$", "content": "inserted"},
        True,
        id="insert-before",
    ),
    pytest.param(
        {"mode": "insert", "location": "start", "content": "first"},
        True,
        id="insert-start",
    ),
    pytest.param(
        {"mode": "insert", "location": "end", "content": "last"},
        True,
        id="insert-end",
    ),
    pytest.param(
        {"mode": "ensure", "after": r"^# header$", "content": "ensured"},
        True,
        id="ensure-after",
    ),
]


@pytest.mark.parametrize("kwargs,expect_changed", LINE_CASES)
def test_line_crlf_matches_lf(file, tmp_path, kwargs, expect_changed):
    _assert_equivalent(
        file,
        tmp_path,
        "line",
        HOSTS,
        backup=False,
        expect_changed=expect_changed,
        **kwargs,
    )


def test_line_is_idempotent_on_crlf(file, tmp_path):
    path = tmp_path / "crlf.txt"
    path.write_bytes(_to_crlf(HOSTS))
    kwargs = {
        "mode": "ensure",
        "after": r"^# header$",
        "content": "ensured",
        "backup": False,
    }
    assert file.line(str(path), **kwargs)
    after_first = path.read_bytes()
    assert after_first == _to_crlf(
        b"# header\nensured\nhost all all 0.0.0.0/0 md5\n"
        b"host all all ::/0 md5  \n\nkey = value\nFoo Bar\n"
    )
    assert not file.line(str(path), **kwargs)
    assert path.read_bytes() == after_first


# ---------------------------------------------------------------------------
# file.append, file.prepend, file.write and file.blockreplace
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("content", [HOSTS, TAIL], ids=["hosts", "no-trailing-newline"])
@pytest.mark.parametrize(
    "args", [("one",), ("one", "two"), ("multi\nline",)], ids=["1", "2", "embedded-lf"]
)
def test_append_crlf_matches_lf(file, tmp_path, content, args):
    lf_ret, crlf_ret, lf_bytes, crlf_bytes = _run_both(
        file, tmp_path, "append", content, *args
    )
    assert crlf_ret == lf_ret
    # Newlines inside an argument are written as given, only the terminator
    # that append adds follows the file.
    expected = content
    if not content.endswith(b"\n"):
        expected += b"\n"
    for arg in args:
        expected += arg.encode() + b"\n"
    assert lf_bytes == expected
    expected_crlf = _to_crlf(content)
    if not content.endswith(b"\n"):
        expected_crlf += b"\r\n"
    for arg in args:
        expected_crlf += arg.encode() + b"\r\n"
    assert crlf_bytes == expected_crlf


@pytest.mark.parametrize("content", [HOSTS, TAIL], ids=["hosts", "no-trailing-newline"])
@pytest.mark.parametrize("args", [("one",), ("one", "two")], ids=["1", "2"])
def test_prepend_crlf_matches_lf(file, tmp_path, content, args):
    lf_ret, crlf_ret, lf_bytes, crlf_bytes = _run_both(
        file, tmp_path, "prepend", content, *args
    )
    assert crlf_ret == lf_ret
    assert lf_bytes == b"".join(a.encode() + b"\n" for a in args) + content
    assert crlf_bytes == b"".join(a.encode() + b"\r\n" for a in args) + _to_crlf(
        content
    )


def test_write_always_terminates_with_lf(file, tmp_path):
    """
    file.write replaces the whole file and writes the caller's strings as
    given, so it terminates them with ``\\n`` whatever the previous file used.
    This is intentional, see the note in the docstring of file.write.
    """
    path = tmp_path / "target.txt"
    path.write_bytes(_to_crlf(HOSTS))
    file.write(str(path), "a", "b\r\nc")
    assert path.read_bytes() == b"a\nb\r\nc\n"


def test_blockreplace_crlf_matches_lf(file, tmp_path):
    """
    blockreplace already follows the line endings of the file; make sure it
    keeps doing so.
    """
    _assert_equivalent(
        file,
        tmp_path,
        "blockreplace",
        HOSTS,
        marker_start="#-- start",
        marker_end="#-- end",
        content="one\ntwo",
        append_if_not_found=True,
        backup=False,
        expect_changed=True,
    )
