import pytest

from salt.matchers.glob_match import match


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
        # Invalid value cases
        (None, {}, "anything", False),
        ("*", {}, None, False),
        ("", {}, None, False),
    ],
)
def test_glob_match_logic(pattern, minion_id, expected):
    assert match(pattern, opts={}, minion_id=minion_id) == expected


def test_glob_match_regex_safety():
    """
    Ensure that special regex characters are treated as literals
    and not interpreted as regex (standard glob behavior).
    """
    # In regex, '.' matches any char. In glob, '.' is a literal.
    # If pattern is 'a.b', it should ONLY match 'a.b', not 'axb'.
    assert match("a.b", {}, "a.b") is True
    assert match("a.b", {}, "axb") is False

    # Test other regex meta-characters
    assert match("a+b", {}, "a+b") is True
    assert match("a+b", {}, "ab") is False

    assert match("a(b)c", {}, "a(b)c") is True
    assert match("a(b)c", {}, "abc") is False
