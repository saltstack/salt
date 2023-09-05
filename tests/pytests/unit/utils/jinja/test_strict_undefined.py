import math

from jinja2 import StrictUndefined

from salt.utils import jinja


def test_has_undefined():
    assert jinja._has_strict_undefined(StrictUndefined()) is True


def test_has_none():
    assert jinja._has_strict_undefined(None) is False


def test_has_bool():
    assert jinja._has_strict_undefined(True) is False
    assert jinja._has_strict_undefined(False) is False


def test_has_int():
    for i in range(-300, 300):
        assert jinja._has_strict_undefined(i) is False
    assert jinja._has_strict_undefined(8231940728139704) is False
    assert jinja._has_strict_undefined(-8231940728139704) is False


def test_has_float():
    assert jinja._has_strict_undefined(0.0) is False
    assert jinja._has_strict_undefined(-0.0000000000001324) is False
    assert jinja._has_strict_undefined(451452.13414) is False
    assert jinja._has_strict_undefined(math.inf) is False
    assert jinja._has_strict_undefined(math.nan) is False


def test_has_str():
    assert jinja._has_strict_undefined("") is False
    assert jinja._has_strict_undefined(" ") is False
    assert jinja._has_strict_undefined("\0") is False
    assert jinja._has_strict_undefined("salt salt salt") is False
    assert (
        jinja._has_strict_undefined('assert jinja._has_strict_undefined("") is False')
        is False
    )


def test_hash_mapping():
    assert jinja._has_strict_undefined({}) is False
    assert jinja._has_strict_undefined({True: False, False: True}) is False
    assert (
        jinja._has_strict_undefined({True: False, None: True, 88: 98, "salt": 300})
        is False
    )
    assert jinja._has_strict_undefined({True: StrictUndefined()}) is True
    assert jinja._has_strict_undefined({True: {True: StrictUndefined()}}) is True
    assert (
        jinja._has_strict_undefined(
            {True: False, None: True, 88: 98, "salt": StrictUndefined()}
        )
        is True
    )


def test_has_sequence():
    assert jinja._has_strict_undefined(()) is False
    assert jinja._has_strict_undefined([]) is False
    assert jinja._has_strict_undefined([None, 1, 2, 3]) is False
    assert jinja._has_strict_undefined([None, 1, 2, [(None, "str")]]) is False
    assert jinja._has_strict_undefined({None, 1, 2, (None, "str")}) is False
    assert jinja._has_strict_undefined((StrictUndefined(),)) is True
    assert (
        jinja._has_strict_undefined([None, 1, 2, [(None, StrictUndefined())]]) is True
    )


def test_has_iter():
    # We should not be running iters make sure iters are not called
    assert jinja._has_strict_undefined(iter([])) is False
    assert jinja._has_strict_undefined(iter({1: 1})) is False
    assert (
        jinja._has_strict_undefined(iter([None, "\0", StrictUndefined(), False]))
        is False
    )
    assert jinja._has_strict_undefined(iter({1: StrictUndefined()})) is False


def test_full():
    assert (
        jinja._has_strict_undefined(
            {1: 45, None: (0, 1, [[{"": {"": (3.2, 34.2)}}]], False)}
        )
        is False
    )
    assert (
        jinja._has_strict_undefined(
            {1: 45, None: (0, 1, [[{"": {"": (StrictUndefined(), 34.2)}}]], False)}
        )
        is True
    )


@jinja._handle_strict_undefined
def _handle_test_helper(value, k=34, *args, **kwargs):
    return None


def test_handle_strict_undefined():
    assert _handle_test_helper(False) is None
    assert _handle_test_helper((1, 2, 3)) is None
    assert _handle_test_helper({1, 2, 3}) is None
    assert _handle_test_helper([1, 2, 3, {"": None, "str": 0.0}]) is None
    # Note StrictUndefined overrides __eq__
    assert isinstance(_handle_test_helper(StrictUndefined()), StrictUndefined)
    assert isinstance(
        _handle_test_helper([1, 2, 3, {"": None, "str": StrictUndefined()}]), list
    )
