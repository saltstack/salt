import pytest

from salt.fileserver import _matches_prefix

FILES = [
    "demo/a_file",
    "demo/a/b_file",
    "demo/a/b/c_file",
    "demo/a/b/c_file2",
    "demo/a/b/c/targetfile1",
    "demo/a/b/c/targetfile2",
]


@pytest.mark.parametrize(
    "prefix,expected",
    [
        ("", FILES),
        ("/", FILES),
        ("demo/a/b/c/", ["demo/a/b/c/targetfile1", "demo/a/b/c/targetfile2"]),
        ("/demo/a/b/c/", ["demo/a/b/c/targetfile1", "demo/a/b/c/targetfile2"]),
        (
            "demo/a/b/c",
            [
                "demo/a/b/c_file",
                "demo/a/b/c_file2",
                "demo/a/b/c/targetfile1",
                "demo/a/b/c/targetfile2",
            ],
        ),
    ],
)
def test_matches_prefix(prefix, expected):
    assert [f for f in FILES if _matches_prefix(f, prefix)] == expected
