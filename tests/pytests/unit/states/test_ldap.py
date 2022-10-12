import pytest

import salt.states.ldap as ldap
from salt.utils.ldap import AttributeValueSet


def _toset_testcases():
    def _gen(x):
        yield x

    # Single values:
    for input, want_list in [
        ("", [b""]),
        (b"", [b""]),
        (False, [b"False"]),
        (True, [b"True"]),
        (0, [b"0"]),
        (-1, [b"-1"]),
        (0xF, [b"15"]),
        ("🚀", ["🚀".encode()]),
        ("🚀".encode(), ["🚀".encode()]),
        (bytearray("🚀".encode()), ["🚀".encode()]),
        (memoryview("🚀".encode()), ["🚀".encode()]),
        (b"\x80", [b"\x80"]),  # Intentionally invalid UTF-8.
    ]:
        # Single values can be provided directly or in an iterable.
        for xform in [
            lambda x: x,
            lambda x: [x],
            lambda x: (x,),
            _gen,
        ]:
            yield (xform(input), want_list)

    yield from [
        # Sequences:
        (None, []),
        ([], []),
        ((), []),
        (set(), []),
        (["a", "b"], [b"a", b"b"]),
        ([b"a", b"b"], [b"a", b"b"]),
        (["a", b"b", 0], [b"a", b"b", b"0"]),  # Mix of types.
        # A sequence of integers in [0, 256) can be converted to a bytes object,
        # but they shouldn't be -- they should be treated as a sequence of
        # integers.  (Otherwise, it would be impossible to store integers unless
        # one of the values was outside [0, 256).)
        ([128], [b"128"]),
        ((128,), [b"128"]),
        (list("🚀".encode()), [b"240", b"159", b"154", b"128"]),
        (tuple("🚀".encode()), [b"240", b"159", b"154", b"128"]),
        # Invalid values:
        (1.1, TypeError),
        ([[]], TypeError),
    ]


@pytest.mark.parametrize("input,want_list", _toset_testcases())
def test__toset(input, want_list):
    if isinstance(want_list, type):
        with pytest.raises(want_list):
            got = ldap._toset(input)
    else:
        want = AttributeValueSet(want_list)
        got = ldap._toset(input)
        assert got == want
        assert list(got) == want_list
