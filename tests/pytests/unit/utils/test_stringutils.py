"""
Tests for stringutils utility file.
"""

import builtins
import re
import textwrap

import pytest

import salt.utils.stringutils
from tests.support.mock import patch
from tests.support.unit import LOREM_IPSUM


@pytest.fixture(scope="function")
def unicode():
    UNICODE = "中国語 (繁体)"
    STR = BYTES = UNICODE.encode("utf-8")
    return UNICODE, STR, BYTES


@pytest.fixture(scope="function")
def eggs():
    # This is an example of a unicode string with й constructed using two separate
    # code points. Do not modify it.
    eggs = "\u044f\u0438\u0306\u0446\u0430"
    return eggs


@pytest.fixture(scope="function")
def latin1_unicode():
    LATIN1_UNICODE = "räksmörgås"
    LATIN1_BYTES = LATIN1_UNICODE.encode("latin-1")
    return LATIN1_UNICODE, LATIN1_BYTES


@pytest.fixture()
def single_txt():
    return """
# set variable identifying the chroot you work in (used in the prompt below)
if [ -z '$debian_chroot' ] && [ -r /etc/debian_chroot ]; then
    debian_chroot=$(cat /etc/debian_chroot)
fi
"""


@pytest.fixture()
def double_txt():
    return """
# set variable identifying the chroot you work in (used in the prompt below)
if [ -z "$debian_chroot" ] && [ -r /etc/debian_chroot ]; then
    debian_chroot=$(cat /etc/debian_chroot)
fi
"""


@pytest.fixture()
def single_double_txt():
    return """
# set variable identifying the chroot you work in (used in the prompt below)
if [ -z '$debian_chroot' ] && [ -r /etc/debian_chroot ]; then
    debian_chroot=$(cat /etc/debian_chroot)
fi

# set variable identifying the chroot you work in (used in the prompt below)
if [ -z "$debian_chroot" ] && [ -r /etc/debian_chroot ]; then
    debian_chroot=$(cat /etc/debian_chroot)
fi
"""


@pytest.fixture()
def single_double_same_line_txt():
    return """
# set variable identifying the chroot you work in (used in the prompt below)
if [ -z '$debian_chroot' ] && [ -r "/etc/debian_chroot" ]; then
    debian_chroot=$(cat /etc/debian_chroot)
fi
"""


@pytest.fixture()
def match():
    return """
# set variable identifying the chroot you work in (used in the prompt below)
if [ -z '$debian_chroot' ] && [ -r /etc/debian_chroot ]; then
    debian_chroot=$(cat /etc/debian_chroot)
fi


# set variable identifying the chroot you work in (used in the prompt below)
if [ -z "$debian_chroot" ] && [ -r /etc/debian_chroot ]; then
    debian_chroot=$(cat /etc/debian_chroot)
fi


# set variable identifying the chroot you work in (used in the prompt below)
if [ -z "$debian_chroot" ] && [ -r /etc/debian_chroot ]; then
    debian_chroot=$(cat /etc/debian_chroot)
fi


# set variable identifying the chroot you work in (used in the prompt below)
if [ -z '$debian_chroot' ] && [ -r /etc/debian_chroot ]; then
    debian_chroot=$(cat /etc/debian_chroot)
fi


# set variable identifying the chroot you work in (used in the prompt below)
if [ -z '$debian_chroot' ] && [ -r "/etc/debian_chroot" ]; then
    debian_chroot=$(cat /etc/debian_chroot)
fi
"""


def test_single_quotes(single_txt, match):
    regex = salt.utils.stringutils.build_whitespace_split_regex(single_txt)
    assert re.search(regex, match)


def test_double_quotes(double_txt, match):
    regex = salt.utils.stringutils.build_whitespace_split_regex(double_txt)
    assert re.search(regex, match)


def test_single_and_double_quotes(single_double_txt, match):
    regex = salt.utils.stringutils.build_whitespace_split_regex(single_double_txt)
    assert re.search(regex, match)


def test_issue_2227(single_double_same_line_txt, match):
    regex = salt.utils.stringutils.build_whitespace_split_regex(
        single_double_same_line_txt
    )
    assert re.search(regex, match)


def test_contains_whitespace():
    does_contain_whitespace = "A brown fox jumped over the red hen."
    does_not_contain_whitespace = "Abrownfoxjumpedovertheredhen."

    assert salt.utils.stringutils.contains_whitespace(does_contain_whitespace) is True
    assert (
        salt.utils.stringutils.contains_whitespace(does_not_contain_whitespace) is False
    )


def test_to_num():
    assert salt.utils.stringutils.to_num("7") == 7
    assert isinstance(salt.utils.stringutils.to_num("7"), int)
    assert salt.utils.stringutils.to_num("7.0") == 7
    assert isinstance(salt.utils.stringutils.to_num("7.0"), float)
    assert salt.utils.stringutils.to_num("Seven") == "Seven"
    assert isinstance(salt.utils.stringutils.to_num("Seven"), str)


def test_to_none():
    assert salt.utils.stringutils.to_none("") is None
    assert salt.utils.stringutils.to_none("  ") is None
    # Ensure that we do not inadvertently convert certain strings or 0 to None
    assert salt.utils.stringutils.to_none("None") is not None
    assert salt.utils.stringutils.to_none(0) is not None


def test_is_binary():
    assert salt.utils.stringutils.is_binary(LOREM_IPSUM) is False
    # Also test bytestring
    assert (
        salt.utils.stringutils.is_binary(salt.utils.stringutils.is_binary(LOREM_IPSUM))
        is False
    )

    zero_str = "{}{}".format(LOREM_IPSUM, "\0")
    assert salt.utils.stringutils.is_binary(zero_str) is True
    # Also test bytestring
    assert (
        salt.utils.stringutils.is_binary(salt.utils.stringutils.to_bytes(zero_str))
        is True
    )

    # To to ensure safe exit if str passed doesn't evaluate to True
    assert salt.utils.stringutils.is_binary("") is False
    assert salt.utils.stringutils.is_binary(b"") is False

    nontext = 3 * "".join([chr(x) for x in range(1, 32) if x not in (8, 9, 10, 12, 13)])
    almost_bin_str = f"{LOREM_IPSUM[:100]}{nontext[:42]}"

    assert salt.utils.stringutils.is_binary(almost_bin_str) is False
    # Also test bytestring
    assert (
        salt.utils.stringutils.is_binary(
            salt.utils.stringutils.to_bytes(almost_bin_str)
        )
        is False
    )

    bin_str = almost_bin_str + "\x01"
    assert salt.utils.stringutils.is_binary(bin_str) is True
    # Also test bytestring
    assert (
        salt.utils.stringutils.is_binary(salt.utils.stringutils.to_bytes(bin_str))
        is True
    )


def test_to_str(unicode):
    UNICODE = unicode[0]
    BYTES = unicode[2]

    for x in (123, (1, 2, 3), [1, 2, 3], {1: 23}, None):
        assert pytest.raises(TypeError, salt.utils.stringutils.to_str, x)
    assert salt.utils.stringutils.to_str("plugh") == "plugh"
    assert salt.utils.stringutils.to_str("áéíóúý", "utf-8") == "áéíóúý"
    assert salt.utils.stringutils.to_str(BYTES, "utf-8") == UNICODE
    assert salt.utils.stringutils.to_str(bytearray(BYTES), "utf-8") == UNICODE
    # Test situation when a minion returns incorrect utf-8 string because of... million reasons
    ut2 = b"\x9c"
    assert pytest.raises(
        UnicodeDecodeError, salt.utils.stringutils.to_str, ut2, "utf-8"
    )
    assert salt.utils.stringutils.to_str(ut2, "utf-8", "replace") == "\ufffd"
    assert pytest.raises(
        UnicodeDecodeError,
        salt.utils.stringutils.to_str,
        bytearray(ut2),
        "utf-8",
    )
    assert salt.utils.stringutils.to_str(bytearray(ut2), "utf-8", "replace") == "\ufffd"


def test_to_bytes(unicode):
    UNICODE = unicode[0]
    BYTES = unicode[2]

    for x in (123, (1, 2, 3), [1, 2, 3], {1: 23}, None):
        assert pytest.raises(TypeError, salt.utils.stringutils.to_bytes, x)

    assert salt.utils.stringutils.to_bytes("xyzzy") == b"xyzzy"
    assert salt.utils.stringutils.to_bytes(BYTES) == BYTES
    assert salt.utils.stringutils.to_bytes(bytearray(BYTES)) == BYTES
    assert salt.utils.stringutils.to_bytes(UNICODE, "utf-8") == BYTES

    # Test utf-8 fallback with ascii default encoding
    with patch.object(builtins, "__salt_system_encoding__", "ascii"):
        assert salt.utils.stringutils.to_bytes("Ψ") == b"\xce\xa8"


def test_to_unicode(eggs, unicode, latin1_unicode):
    UNICODE = unicode[0]
    BYTES = unicode[2]
    LATIN1_UNICODE = latin1_unicode[0]
    LATIN1_BYTES = latin1_unicode[1]

    assert salt.utils.stringutils.to_unicode(eggs, normalize=True) == "яйца"
    assert salt.utils.stringutils.to_unicode(eggs, normalize=False) != "яйца"
    assert (
        salt.utils.stringutils.to_unicode(LATIN1_BYTES, encoding="latin-1")
        == LATIN1_UNICODE
    )
    assert salt.utils.stringutils.to_unicode("plugh") == "plugh"
    assert salt.utils.stringutils.to_unicode("áéíóúý") == "áéíóúý"
    assert salt.utils.stringutils.to_unicode(BYTES, "utf-8") == UNICODE
    assert salt.utils.stringutils.to_unicode(bytearray(BYTES), "utf-8") == UNICODE


def test_to_unicode_multi_encoding(latin1_unicode):
    LATIN1_UNICODE = latin1_unicode[0]
    LATIN1_BYTES = latin1_unicode[1]
    assert (
        salt.utils.stringutils.to_unicode(LATIN1_BYTES, encoding=("utf-8", "latin1"))
        == LATIN1_UNICODE
    )


def test_build_whitespace_split_regex():
    # With 3.7+,  re.escape only escapes special characters, no longer
    # escaping all characters other than ASCII letters, numbers and
    # underscores.  This includes commas.
    expected_regex = (
        "(?m)^(?:[\\s]+)?Lorem(?:[\\s]+)?ipsum(?:[\\s]+)?dolor(?:[\\s]+)?sit(?:[\\s]+)?amet,"
        "(?:[\\s]+)?$"
    )
    assert (
        salt.utils.stringutils.build_whitespace_split_regex(
            " ".join(LOREM_IPSUM.split()[:5])
        )
        == expected_regex
    )


def test_get_context():
    expected_context = textwrap.dedent(
        """\
        ---
        Lorem ipsum dolor sit amet, consectetur adipiscing elit. Quisque eget urna a arcu lacinia sagittis.
        Sed scelerisque, lacus eget malesuada vestibulum, justo diam facilisis tortor, in sodales dolor
        [...]
        ---"""
    )
    assert (
        salt.utils.stringutils.get_context(LOREM_IPSUM, 1, num_lines=1)
        == expected_context
    )


def test_get_context_has_enough_context():
    template = "1\n2\n3\n4\n5\n6\n7\n8\n9\na\nb\nc\nd\ne\nf"
    context = salt.utils.stringutils.get_context(template, 8)
    expected = "---\n[...]\n3\n4\n5\n6\n7\n8\n9\na\nb\nc\nd\n[...]\n---"
    assert expected == context


def test_get_context_at_top_of_file():
    template = "1\n2\n3\n4\n5\n6\n7\n8\n9\na\nb\nc\nd\ne\nf"
    context = salt.utils.stringutils.get_context(template, 1)
    expected = "---\n1\n2\n3\n4\n5\n6\n[...]\n---"
    assert expected == context


def test_get_context_at_bottom_of_file():
    template = "1\n2\n3\n4\n5\n6\n7\n8\n9\na\nb\nc\nd\ne\nf"
    context = salt.utils.stringutils.get_context(template, 15)
    expected = "---\n[...]\na\nb\nc\nd\ne\nf\n---"
    assert expected == context


def test_get_context_2_context_lines():
    template = "1\n2\n3\n4\n5\n6\n7\n8\n9\na\nb\nc\nd\ne\nf"
    context = salt.utils.stringutils.get_context(template, 8, num_lines=2)
    expected = "---\n[...]\n6\n7\n8\n9\na\n[...]\n---"
    assert expected == context


def test_get_context_with_marker():
    template = "1\n2\n3\n4\n5\n6\n7\n8\n9\na\nb\nc\nd\ne\nf"
    context = salt.utils.stringutils.get_context(
        template, 8, num_lines=2, marker=" <---"
    )
    expected = "---\n[...]\n6\n7\n8 <---\n9\na\n[...]\n---"
    assert expected == context


def test_expr_match():
    val = "foo/bar/baz"
    # Exact match
    assert salt.utils.stringutils.expr_match(val, val) is True
    # Glob match
    assert salt.utils.stringutils.expr_match(val, "foo/*/baz") is True
    # Glob non-match
    assert salt.utils.stringutils.expr_match(val, "foo/*/bar") is False
    # Regex match
    assert salt.utils.stringutils.expr_match(val, r"foo/\w+/baz") is True
    # Regex non-match
    assert salt.utils.stringutils.expr_match(val, r"foo/\w/baz") is False


def test_check_whitelist_blacklist():
    """
    Ensure that whitelist matching works on both PY2 and PY3
    """
    whitelist = ["one/two/three", r"web[0-9]"]
    blacklist = ["four/five/six", r"web[5-9]"]

    # Tests with string whitelist/blacklist
    assert (
        salt.utils.stringutils.check_whitelist_blacklist(
            "web_one",
            whitelist=whitelist[1],
            blacklist=None,
        )
        is False
    )

    assert (
        salt.utils.stringutils.check_whitelist_blacklist(
            "web_one",
            whitelist=whitelist[1],
            blacklist=[],
        )
        is False
    )

    assert (
        salt.utils.stringutils.check_whitelist_blacklist(
            "web1",
            whitelist=whitelist[1],
            blacklist=None,
        )
        is True
    )
    assert (
        salt.utils.stringutils.check_whitelist_blacklist(
            "web1",
            whitelist=whitelist[1],
            blacklist=[],
        )
        is True
    )

    assert (
        salt.utils.stringutils.check_whitelist_blacklist(
            "web5",
            whitelist=None,
            blacklist=blacklist[1],
        )
        is False
    )

    assert (
        salt.utils.stringutils.check_whitelist_blacklist(
            "web5",
            whitelist=[],
            blacklist=blacklist[1],
        )
        is False
    )

    assert (
        salt.utils.stringutils.check_whitelist_blacklist(
            "web_five",
            whitelist=None,
            blacklist=blacklist[1],
        )
        is True
    )

    assert (
        salt.utils.stringutils.check_whitelist_blacklist(
            "web_five",
            whitelist=[],
            blacklist=blacklist[1],
        )
        is True
    )

    assert (
        salt.utils.stringutils.check_whitelist_blacklist(
            "web5",
            whitelist=whitelist[1],
            blacklist=blacklist[1],
        )
        is False
    )

    assert (
        salt.utils.stringutils.check_whitelist_blacklist(
            "web4",
            whitelist=whitelist[1],
            blacklist=blacklist[1],
        )
        is True
    )

    # Tests with list whitelist/blacklist
    assert (
        salt.utils.stringutils.check_whitelist_blacklist(
            "web_one",
            whitelist=whitelist,
            blacklist=None,
        )
        is False
    )

    assert (
        salt.utils.stringutils.check_whitelist_blacklist(
            "web_one",
            whitelist=whitelist,
            blacklist=[],
        )
        is False
    )

    assert (
        salt.utils.stringutils.check_whitelist_blacklist(
            "web1",
            whitelist=whitelist,
            blacklist=None,
        )
        is True
    )

    assert salt.utils.stringutils.check_whitelist_blacklist(
        "web1",
        whitelist=whitelist,
        blacklist=[],
    )

    assert (
        salt.utils.stringutils.check_whitelist_blacklist(
            "web5",
            whitelist=None,
            blacklist=blacklist,
        )
        is False
    )

    assert (
        salt.utils.stringutils.check_whitelist_blacklist(
            "web5",
            whitelist=[],
            blacklist=blacklist,
        )
        is False
    )

    assert (
        salt.utils.stringutils.check_whitelist_blacklist(
            "web_five",
            whitelist=None,
            blacklist=blacklist,
        )
        is True
    )

    assert (
        salt.utils.stringutils.check_whitelist_blacklist(
            "web_five",
            whitelist=[],
            blacklist=blacklist,
        )
        is True
    )

    assert (
        salt.utils.stringutils.check_whitelist_blacklist(
            "web5",
            whitelist=whitelist,
            blacklist=blacklist,
        )
        is False
    )

    assert (
        salt.utils.stringutils.check_whitelist_blacklist(
            "web4",
            whitelist=whitelist,
            blacklist=blacklist,
        )
        is True
    )

    # Tests with set whitelist/blacklist
    assert (
        salt.utils.stringutils.check_whitelist_blacklist(
            "web_one",
            whitelist=set(whitelist),
            blacklist=None,
        )
        is False
    )

    assert (
        salt.utils.stringutils.check_whitelist_blacklist(
            "web_one",
            whitelist=set(whitelist),
            blacklist=set(),
        )
        is False
    )

    assert (
        salt.utils.stringutils.check_whitelist_blacklist(
            "web1",
            whitelist=set(whitelist),
            blacklist=None,
        )
        is True
    )

    assert (
        salt.utils.stringutils.check_whitelist_blacklist(
            "web1",
            whitelist=set(whitelist),
            blacklist=set(),
        )
        is True
    )

    assert (
        salt.utils.stringutils.check_whitelist_blacklist(
            "web5",
            whitelist=None,
            blacklist=set(blacklist),
        )
        is False
    )

    assert (
        salt.utils.stringutils.check_whitelist_blacklist(
            "web5",
            whitelist=set(),
            blacklist=set(blacklist),
        )
        is False
    )

    assert (
        salt.utils.stringutils.check_whitelist_blacklist(
            "web_five",
            whitelist=None,
            blacklist=set(blacklist),
        )
        is True
    )

    assert (
        salt.utils.stringutils.check_whitelist_blacklist(
            "web_five",
            whitelist=set(),
            blacklist=set(blacklist),
        )
        is True
    )

    assert (
        salt.utils.stringutils.check_whitelist_blacklist(
            "web5",
            whitelist=set(whitelist),
            blacklist=set(blacklist),
        )
        is False
    )

    assert (
        salt.utils.stringutils.check_whitelist_blacklist(
            "web4",
            whitelist=set(whitelist),
            blacklist=set(blacklist),
        )
        is True
    )

    # Test with invalid type for whitelist/blacklist
    assert pytest.raises(
        TypeError,
        salt.utils.stringutils.check_whitelist_blacklist,
        "foo",
        whitelist=123,
    )
    assert pytest.raises(
        TypeError,
        salt.utils.stringutils.check_whitelist_blacklist,
        "foo",
        blacklist=123,
    )


def test_check_include_exclude_empty():
    assert salt.utils.stringutils.check_include_exclude("/some/test") is True


def test_check_include_exclude_exclude():
    assert (
        salt.utils.stringutils.check_include_exclude("/some/test", None, "*test*")
        is False
    )


def test_check_include_exclude_exclude_list():
    assert (
        salt.utils.stringutils.check_include_exclude("/some/test", None, ["*test"])
        is False
    )


def test_check_include_exclude_exclude_include():
    assert (
        salt.utils.stringutils.check_include_exclude("/some/test", "*test*", "/some/")
        is True
    )


def test_check_include_exclude_regex():
    assert (
        salt.utils.stringutils.check_include_exclude(
            "/some/test", None, "E@/some/(test|other)"
        )
        is False
    )


@pytest.mark.parametrize(
    "unit",
    [
        "B",
        "K",
        "KB",
        "KiB",
        "M",
        "MB",
        "MiB",
        "G",
        "GB",
        "GiB",
        "T",
        "TB",
        "TiB",
        "P",
        "PB",
        "PiB",
        "E",
        "EB",
        "EiB",
        "Z",
        "ZB",
        "ZiB",
        "Y",
        "YB",
        "YiB",
    ],
)
def test_human_to_bytes(unit):
    # first multiplier is IEC/binary
    # second multiplier is metric/decimal
    conversion = {
        "B": (1, 1),
        "K": (2**10, 10**3),
        "M": (2**20, 10**6),
        "G": (2**30, 10**9),
        "T": (2**40, 10**12),
        "P": (2**50, 10**15),
        "E": (2**60, 10**18),
        "Z": (2**70, 10**21),
        "Y": (2**80, 10**24),
    }

    idx = 0
    if len(unit) == 2:
        idx = 1

    # pull out the multipliers for the units
    multiplier = conversion[unit.upper()[0]][idx]
    iec = conversion[unit.upper()[0]][0]

    vals = [32]
    # don't calculate a half a byte
    if unit != "B":
        # otherwise, test a float as well
        vals.append(64.5)

    for val in vals:
        # calculate KB, MB, GB, etc. as 1024 instead of 1000 (legacy use)
        assert salt.utils.stringutils.human_to_bytes(f"{val}{unit}") == val * iec
        assert salt.utils.stringutils.human_to_bytes(f"{val} {unit}") == val * iec
        # handle metric (KB, MB, GB, etc.) per standard
        assert (
            salt.utils.stringutils.human_to_bytes(f"{val}{unit}", handle_metric=True)
            == val * multiplier
        )
        assert (
            salt.utils.stringutils.human_to_bytes(f"{val} {unit}", handle_metric=True)
            == val * multiplier
        )


def test_human_to_bytes_edge_cases():
    # no unit - bytes
    assert salt.utils.stringutils.human_to_bytes("32") == 32
    # no unit - default MB
    assert salt.utils.stringutils.human_to_bytes("32", default_unit="M") == 32 * 2**20
    # bad value
    assert salt.utils.stringutils.human_to_bytes("32-1") == 0
    assert salt.utils.stringutils.human_to_bytes("3.4.MB") == 0
    assert salt.utils.stringutils.human_to_bytes("") == 0
    assert salt.utils.stringutils.human_to_bytes("bytes") == 0
    # bad unit
    assert salt.utils.stringutils.human_to_bytes("32gigajammers") == 0
    assert salt.utils.stringutils.human_to_bytes("512bytes") == 0
    assert salt.utils.stringutils.human_to_bytes("4 Kbytes") == 0
    assert salt.utils.stringutils.human_to_bytes("9ib") == 0
    assert salt.utils.stringutils.human_to_bytes("2HB") == 0
