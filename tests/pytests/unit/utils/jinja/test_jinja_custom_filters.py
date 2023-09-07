import math

import jinja2
import pytest
from jinja2 import StrictUndefined

from salt.utils import jinja


def test_get_undefined():
    assert len(jinja._get_strict_undefined(StrictUndefined())) == 1


def test_get_none():
    assert len(jinja._get_strict_undefined(None)) == 0


def test_get_bool():
    assert len(jinja._get_strict_undefined(True)) == 0
    assert len(jinja._get_strict_undefined(False)) == 0


def test_get_int():
    for i in range(-300, 300):
        assert len(jinja._get_strict_undefined(i)) == 0
    assert len(jinja._get_strict_undefined(8231940728139704)) == 0
    assert len(jinja._get_strict_undefined(-8231940728139704)) == 0


def test_get_float():
    assert bool(jinja._get_strict_undefined(0.0)) == 0
    assert bool(jinja._get_strict_undefined(-0.0000000000001324)) == 0
    assert bool(jinja._get_strict_undefined(451452.13414)) == 0
    assert bool(jinja._get_strict_undefined(math.inf)) == 0
    assert bool(jinja._get_strict_undefined(math.nan)) == 0


def test_get_str():
    assert len(jinja._get_strict_undefined("")) == 0
    assert len(jinja._get_strict_undefined(" ")) == 0
    assert len(jinja._get_strict_undefined("\0")) == 0
    assert len(jinja._get_strict_undefined("salt salt salt")) == 0
    assert (
        len(
            jinja._get_strict_undefined(
                'assert jinja._has_strict_undefined("") is False'
            )
        )
        == 0
    )


def test_get_mapping():
    assert len(jinja._get_strict_undefined({})) == 0
    assert len(jinja._get_strict_undefined({True: False, False: True})) == 0
    assert (
        len(jinja._get_strict_undefined({True: False, None: True, 88: 98, "salt": 300}))
        == 0
    )
    assert len(jinja._get_strict_undefined({True: StrictUndefined()})) == 1
    assert len(jinja._get_strict_undefined({True: {True: StrictUndefined()}})) == 1
    assert (
        len(
            jinja._get_strict_undefined(
                {True: False, None: True, 88: 98, "salt": StrictUndefined()}
            )
        )
        == 1
    )


def test_get_sequence():
    assert len(jinja._get_strict_undefined(())) == 0
    assert len(jinja._get_strict_undefined([])) == 0
    assert len(jinja._get_strict_undefined([None, 1, 2, 3])) == 0
    assert len(jinja._get_strict_undefined([None, 1, 2, [(None, "str")]])) == 0
    assert len(jinja._get_strict_undefined({None, 1, 2, (None, "str")})) == 0
    assert len(jinja._get_strict_undefined((StrictUndefined(),))) == 1
    assert (
        len(jinja._get_strict_undefined([None, 1, 2, [(None, StrictUndefined())]])) == 1
    )


def test_get_iter():
    # We should not be running iters make sure iters are not called
    assert len(jinja._get_strict_undefined(iter([]))) == 0
    assert len(jinja._get_strict_undefined(iter({1: 1}))) == 0
    assert (
        len(jinja._get_strict_undefined(iter([None, "\0", StrictUndefined(), False])))
        == 0
    )
    assert len(jinja._get_strict_undefined(iter({1: StrictUndefined()}))) == 0


def test_full():
    assert (
        len(
            jinja._get_strict_undefined(
                {1: 45, None: (0, 1, [[{"": {"": (3.2, 34.2)}}]], False)}
            )
        )
        == 0
    )
    assert (
        len(
            jinja._get_strict_undefined(
                {1: 45, None: (0, 1, [[{"": {"": (StrictUndefined(), 34.2)}}]], False)}
            )
        )
        == 1
    )
    assert (
        len(
            jinja._get_strict_undefined(
                {
                    1: 45,
                    None: (
                        0,
                        1,
                        [
                            [
                                {
                                    "": {"": (StrictUndefined(), 34.2)},
                                    45: StrictUndefined(),
                                }
                            ]
                        ],
                        False,
                    ),
                }
            )
        )
        == 2
    )
    assert (
        len(
            jinja._get_strict_undefined(
                {
                    1: 45,
                    None: (
                        0,
                        1,
                        [
                            StrictUndefined(),
                            [
                                {
                                    "": {"": (StrictUndefined(), 34.2)},
                                    45: StrictUndefined(),
                                }
                            ],
                            StrictUndefined(),
                        ],
                        False,
                    ),
                }
            )
        )
        == 4
    )


@jinja._handle_strict_undefined
def _handle_test_helper(value, k=34, *args, **kwargs):
    return None


def test_handle_strict_undefined():
    assert _handle_test_helper(False) is None
    assert _handle_test_helper((1, 2, 3)) is None
    assert _handle_test_helper({1, 2, 3}) is None
    assert _handle_test_helper([1, 2, 3, {"": None, "str": 0.0}]) is None
    assert isinstance(_handle_test_helper(StrictUndefined()), StrictUndefined)
    assert isinstance(
        _handle_test_helper(
            [1, 2, 3, {"": StrictUndefined(), "str": StrictUndefined()}]
        ),
        StrictUndefined,
    )


def _render(yaml):
    return (
        jinja2.Environment(
            extensions=[jinja.SerializerExtension], undefined=jinja2.StrictUndefined
        )
        .from_string(yaml)
        .render()
    )


def _render_fail(yaml):
    with pytest.raises(jinja2.exceptions.UndefinedError):
        _render(yaml)


YAML_SLS_ERROR = """
{%- set ports = {'http': 80} %}

huh:
  test.configurable_test_state:
    - changes: true
    - result: true
    - comment: https port is {{ ports['https'] | yaml }}
"""


YAML_SLS = """
{%- set ports = {'https': 80} %}

huh:
  test.configurable_test_state:
    - changes: true
    - result: true
    - comment: https port is {{ ports['https'] | yaml }}
"""


YAML_SLS_RIGHT = """

huh:
  test.configurable_test_state:
    - changes: true
    - result: true
    - comment: https port is 80"""


def test_yaml():
    _render_fail(YAML_SLS_ERROR)
    assert _render(YAML_SLS) == YAML_SLS_RIGHT


JSON_SLS_ERROR = """
{%- set ports = {'http': 80} %}

huh:
  test.configurable_test_state:
    - changes: true
    - result: true
    - comment: https port is {{ [ports['https23'], ports['https']] | json }}
    - comment2: https port is {{ [666, ports['https2']] | json }}
    - comment3: https port is {{ [666, ports['https2']] | json }}
"""


JSON_SLS = """
{%- set ports = {'https': 80} %}

huh:
  test.configurable_test_state:
    - changes: true
    - result: true
    - comment: https port is {{ [666, ports['https']] | json }}
"""


JSON_SLS_RIGHT = """

huh:
  test.configurable_test_state:
    - changes: true
    - result: true
    - comment: https port is [666, 80]"""


def test_json():
    _render_fail(JSON_SLS_ERROR)
    assert _render(JSON_SLS) == JSON_SLS_RIGHT
