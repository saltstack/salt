"""
State level checks for files with CRLF line endings (#52457).

Every state is run twice against an LF file and its CRLF copy. The first run
has to make the same change on both, keeping the line endings of the file,
and the second run must report no changes: a state that keeps changing a file
on every run is what the issue is about.
"""

import pytest

pytestmark = [
    pytest.mark.windows_whitelisted,
]

INITIAL = (
    "# managed by salt\n"
    "host all all 127.0.0.1/32 trust\n"
    "host all all 10.0.0.0/8 md5  \n"
    "\n"
    "key = value\n"
    "#other = 1\n"
)


@pytest.fixture(params=["\n", "\r\n"], ids=["lf", "crlf"])
def eol(request):
    return request.param


@pytest.fixture
def target(tmp_path, eol):
    path = tmp_path / "target.conf"
    path.write_bytes(INITIAL.replace("\n", eol).encode())
    return path


def _expected(eol, text):
    return text.replace("\n", eol).encode()


def _assert_converges(run, path, expected):
    first = run()
    assert first.result is True, first.comment
    assert first.changes
    assert path.read_bytes() == expected
    for _ in range(2):
        again = run()
        assert again.result is True, again.comment
        assert not again.changes
        assert path.read_bytes() == expected


def test_replace(file, target, eol):
    def run():
        return file.replace(
            name=str(target),
            pattern=r"^host all all 10\.0\.0\.0/8 md5.*$",
            repl="host all all 10.0.0.0/8 scram-sha-256",
            backup=False,
        )

    expected = _expected(
        eol,
        INITIAL.replace(
            "host all all 10.0.0.0/8 md5  ", "host all all 10.0.0.0/8 scram-sha-256"
        ),
    )
    _assert_converges(run, target, expected)


def test_replace_dollar_anchor_only(file, target, eol):
    def run():
        return file.replace(
            name=str(target),
            pattern=r"^key = value$",
            repl="key = other",
            backup=False,
        )

    expected = _expected(eol, INITIAL.replace("key = value", "key = other"))
    _assert_converges(run, target, expected)


def test_replace_append_if_not_found(file, target, eol):
    def run():
        return file.replace(
            name=str(target),
            pattern=r"^new = 1.*$",
            repl="new = 1",
            append_if_not_found=True,
            backup=False,
        )

    _assert_converges(run, target, _expected(eol, INITIAL + "new = 1\n"))


def test_replace_prepend_if_not_found(file, target, eol):
    def run():
        return file.replace(
            name=str(target),
            pattern=r"^new = 1.*$",
            repl="new = 1",
            prepend_if_not_found=True,
            backup=False,
        )

    _assert_converges(run, target, _expected(eol, "new = 1\n" + INITIAL))


def test_comment(file, target, eol):
    def run():
        return file.comment(name=str(target), regex=r"^key = value$", backup=False)

    expected = _expected(eol, INITIAL.replace("key = value", "#key = value"))
    _assert_converges(run, target, expected)


def test_uncomment(file, target, eol):
    def run():
        return file.uncomment(name=str(target), regex=r"^other = 1$", backup=False)

    expected = _expected(eol, INITIAL.replace("#other = 1", "other = 1"))
    _assert_converges(run, target, expected)


def test_append(file, target, eol):
    def run():
        return file.append(name=str(target), text="appended = 1")

    _assert_converges(run, target, _expected(eol, INITIAL + "appended = 1\n"))


def test_prepend(file, target, eol):
    def run():
        return file.prepend(name=str(target), text="prepended = 1")

    _assert_converges(run, target, _expected(eol, "prepended = 1\n" + INITIAL))


@pytest.mark.parametrize(
    "kwargs,old,new",
    [
        pytest.param(
            {"mode": "replace", "content": "key = changed", "match": r"^key = value$"},
            "key = value\n",
            "key = changed\n",
            id="replace-dollar",
        ),
        pytest.param(
            {"mode": "delete", "match": r"^key = value$"},
            "key = value\n",
            "",
            id="delete-dollar",
        ),
        pytest.param(
            {
                "mode": "ensure",
                "content": "inserted = 1",
                "after": r"^# managed by salt$",
            },
            "# managed by salt\n",
            "# managed by salt\ninserted = 1\n",
            id="insert-after-first-line",
        ),
        pytest.param(
            {
                "mode": "ensure",
                "content": "inserted = 1",
                "before": r"^key = value$",
            },
            "key = value\n",
            "inserted = 1\nkey = value\n",
            id="insert-before",
        ),
    ],
)
def test_line(file, target, eol, kwargs, old, new):
    def run():
        return file.line(name=str(target), backup=False, **kwargs)

    _assert_converges(run, target, _expected(eol, INITIAL.replace(old, new)))
