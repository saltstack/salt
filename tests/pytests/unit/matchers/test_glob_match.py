import pytest

from salt.matchers import glob_match
from salt.utils.context import func_globals_inject


@pytest.mark.parametrize(
    "pattern, minion_id, expected",
    [
        # --- Basic Wildcards ---
        # '*' matches everything
        ("*", "any_id", True),
        ("*", "", True),
        ("*", None, False),
        # '?' matches exactly one character
        ("?", "a", True),
        ("?", "ab", False),
        ("t?st", "test", True),
        ("t?st", "tst", False),
        ("t?st", "teest", False),
        # --- Character Sets ---
        # '[a-z]' matches a range
        ("[a-z]abc", "xabc", True),
        ("[a-z]abc", "1abc", False),
        ("[0-9]abc", "1abc", True),
        ("[0-9]abc", "aabc", False),
        # Multiple character sets
        ("[a-z][0-9]", "a1", True),
        ("[a-z][0-9]", "ab", False),
        ("[a-z][0-9]", "11", False),
        # --- Prefix/Suffix Matching ---
        ("web*", "web01", True),
        ("web*", "web_server", True),
        ("web*", "other_web", False),
        ("*web", "other_web", True),
        ("*web", "web_only", False),
        # --- Edge Cases ---
        # Empty pattern matches empty ID
        ("", "", True),
        # Empty pattern does not match non-empty ID
        ("", "something", False),
        # Non-empty pattern does not match empty ID
        ("something*", "", False),
    ],
)
def test_glob_match_logic(pattern, minion_id, expected):
    with func_globals_inject(
        glob_match.match,
        __opts__={},
    ):
        assert (
            glob_match.match(
                pattern,
                opts={"id": minion_id},
                minion_id=minion_id,
            )
            == expected
        )


@pytest.mark.parametrize(
    "pattern, opts, minion_id",
    [
        (None, {}, "anything"),
        ("*", {}, None),
        ("", {}, None),
    ],
)
def test_invalid_glob_cases(pattern, opts, minion_id):
    with func_globals_inject(
        glob_match.match,
        __opts__={},
    ):
        opts["id"] = minion_id
        assert glob_match.match(pattern, opts=opts, minion_id=minion_id) is False


def test_glob_match_regex_safety():
    """
    Ensure that special regex characters are treated as literals
    and not interpreted as regex (standard glob behavior).
    """
    with func_globals_inject(
        glob_match.match,
        __opts__={},
    ):
        # In regex, '.' matches any char. In glob, '.' is a literal.
        # If pattern is 'a.b', it should ONLY match 'a.b', not 'axb'.
        assert glob_match.match("a.b", {}, "a.b") is True
        assert glob_match.match("a.b", {}, "axb") is False

        # Test other regex meta-characters
        assert glob_match.match("a+b", {}, "a+b") is True
        assert glob_match.match("a+b", {}, "ab") is False

        assert glob_match.match("a(b)c", {}, "a(b)c") is True
        assert glob_match.match("a(b)c", {}, "abc") is False
