import math

import jinja2
import pytest
from jinja2 import StrictUndefined
from jinja2.sandbox import SandboxedEnvironment

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


def _render_with_salt_filters(template_src):
    env = jinja2.Environment(
        extensions=[jinja.SerializerExtension], undefined=jinja2.StrictUndefined
    )
    env.filters.update(jinja.jinja_filter.salt_jinja_filters)
    return env.from_string(template_src).render()


def _render_fail(yaml):
    with pytest.raises(jinja2.exceptions.UndefinedError):
        _render(yaml)


def _render_sandboxed(template_src):
    """Match production: salt.utils.templates uses SandboxedEnvironment + StrictUndefined."""
    return (
        SandboxedEnvironment(
            extensions=[jinja.SerializerExtension], undefined=jinja2.StrictUndefined
        )
        .from_string(template_src)
        .render()
    )


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


def test_yaml_strict_undefined_sandboxed_environment():
    with pytest.raises(jinja2.exceptions.UndefinedError):
        _render_sandboxed(YAML_SLS_ERROR)
    assert _render_sandboxed(YAML_SLS) == YAML_SLS_RIGHT


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


def test_tojson():
    tojson_error = """
{%- set ports = {'http': 80} %}
x: {{ ports['https'] | tojson }}
"""
    tojson_ok = """
{%- set ports = {'https': 80} %}
x: {{ ports['https'] | tojson }}
"""
    tojson_right = """
x: 80"""
    with pytest.raises(jinja2.exceptions.UndefinedError):
        _render_with_salt_filters(tojson_error)
    assert _render_with_salt_filters(tojson_ok).strip() == tojson_right.strip()


PYTHON_SLS_ERROR = """
{%- set ports = {'http': 80} %}

huh:
  test.configurable_test_state:
    - changes: true
    - result: true
    - comment: https port is {{ [ports['https23'], ports['https']] | python }}
    - comment2: https port is {{ [666 + 1, ports['https2']] | python }}
    - comment3: https port is {{ [666 + 1, ports['https2']] | python }}
"""


PYTHON_SLS = """
{%- set ports = {'https': 80} %}

huh:
  test.configurable_test_state:
    - changes: true
    - result: true
    - comment: https port is {{ [666 + 1, ports['https']] | python }}
"""


PYTHON_SLS_RIGHT = """

huh:
  test.configurable_test_state:
    - changes: true
    - result: true
    - comment: https port is [667, 80]"""


def test_python():
    _render_fail(PYTHON_SLS_ERROR)
    assert _render(PYTHON_SLS) == PYTHON_SLS_RIGHT


def test_to_bool_none():
    """None always returns False."""
    assert jinja.to_bool(None) is False


def test_to_bool_already_bool():
    """Booleans are returned unchanged."""
    assert jinja.to_bool(True) is True
    assert jinja.to_bool(False) is False


def test_to_bool_strings():
    """Only yes/1/true (any case) are truthy strings."""
    assert jinja.to_bool("yes") is True
    assert jinja.to_bool("YES") is True
    assert jinja.to_bool("True") is True
    assert jinja.to_bool("TRUE") is True
    assert jinja.to_bool("1") is True
    assert jinja.to_bool("no") is False
    assert jinja.to_bool("false") is False
    assert jinja.to_bool("False") is False
    assert jinja.to_bool("0") is False
    assert jinja.to_bool("anything else") is False
    assert jinja.to_bool("") is False


def test_to_bool_ints():
    """Integers are truthy only when greater than zero."""
    assert jinja.to_bool(5) is True
    assert jinja.to_bool(1) is True
    assert jinja.to_bool(0) is False
    assert jinja.to_bool(-3) is False


def test_to_bool_non_hashable_uses_length():
    """Non-hashable values fall back to a length check."""
    assert jinja.to_bool([1, 2]) is True
    assert jinja.to_bool([0]) is True
    assert jinja.to_bool([]) is False
    assert jinja.to_bool({"a": 1}) is True
    assert jinja.to_bool({}) is False


def test_to_bool_unknown_hashable():
    """An unrecognized hashable type (tuple) returns False."""
    assert jinja.to_bool((1, 2)) is False
    assert jinja.to_bool(()) is False


def test_indent_default_width():
    """Subsequent lines are indented by the default width of 4."""
    assert jinja.indent("a\nb") == "a\n    b"


def test_indent_custom_width():
    """The width argument controls the indentation size."""
    assert jinja.indent("a\nb", width=2) == "a\n  b"


def test_indent_first():
    """first=True also indents the first line."""
    assert jinja.indent("a\nb", width=2, first=True) == "  a\n  b"


def test_indent_blank():
    """blank=True indents blank lines as well."""
    assert jinja.indent("a\n\nb", width=2, blank=True) == "a\n  \n  b"


def test_indent_no_blank_skips_empty_lines():
    """Without blank, empty lines stay empty rather than getting whitespace."""
    assert jinja.indent("a\n\nb", width=2) == "a\n\n  b"


def test_indent_indentfirst_deprecated():
    """The deprecated indentfirst argument still maps onto first."""
    with pytest.warns(DeprecationWarning):
        assert jinja.indent("a\nb", width=2, indentfirst=True) == "  a\n  b"


def test_regex_search_no_match_returns_none():
    """A non-matching pattern returns None."""
    assert jinja.regex_search("abc", "xyz") is None


def test_regex_search_no_group():
    """The filter returns ``match.groups()``, so a successful match with no
    capture groups yields an empty (falsy) tuple, not the matched text."""
    assert jinja.regex_search("abcd", "bc") == ()


def test_regex_search_groups_ignorecase():
    """Groups are returned and ignorecase makes the match case-insensitive."""
    assert jinja.regex_search("abcd", "^(.*)BC(.*)$", ignorecase=True) == ("a", "d")


def test_regex_search_multiline():
    """multiline lets ^ and $ anchor to line boundaries."""
    assert jinja.regex_search("foo\nbar", "^(bar)$", multiline=True) == ("bar",)
    assert jinja.regex_search("foo\nbar", "^(bar)$") is None


def test_regex_match_no_match_returns_none():
    """match anchors at the start; a mid-string pattern returns None."""
    assert jinja.regex_match("abc", "bc") is None


def test_regex_match_no_group():
    """Like regex_search, a match with no capture groups returns an empty
    (falsy) tuple because the filter returns ``match.groups()``."""
    assert jinja.regex_match("abcd", "ab") == ()


def test_regex_match_groups_ignorecase():
    """Groups are returned with ignorecase honored."""
    assert jinja.regex_match("abcd", "^(.*)BC(.*)$", ignorecase=True) == ("a", "d")


def test_regex_replace_basic():
    """Whitespace runs are replaced with the given value."""
    assert jinja.regex_replace("lets replace spaces", r"\s+", "__") == (
        "lets__replace__spaces"
    )


def test_regex_replace_ignorecase():
    """ignorecase lets the pattern match regardless of case."""
    assert jinja.regex_replace("Hello WORLD", "world", "X", ignorecase=True) == (
        "Hello X"
    )


def test_regex_replace_multiline():
    """multiline anchors ^ at each line start for replacement."""
    assert jinja.regex_replace("a\nb", "^", "> ", multiline=True) == "> a\n> b"


def test_test_match_true_false():
    """test_match returns True only when the pattern matches at the start."""
    assert jinja.test_match("abc", "^a") is True
    assert jinja.test_match("abc", "^z") is False


def test_test_match_ignorecase():
    """ignorecase makes test_match case-insensitive."""
    assert jinja.test_match("ABC", "^a", ignorecase=True) is True
    assert jinja.test_match("ABC", "^a") is False


def test_test_match_multiline():
    """multiline does not affect a leading match anchor for test_match."""
    assert jinja.test_match("foo\nbar", "^bar", multiline=True) is False
    assert jinja.test_match("foo\nbar", "^foo", multiline=True) is True


def test_test_equalto():
    """test_equalto compares two values for equality."""
    assert jinja.test_equalto(1, 1) is True
    assert jinja.test_equalto(1, 2) is False
    assert jinja.test_equalto("salt", "salt") is True


def test_match_is_test_via_render():
    """The 'is match' jinja test produces the expected result when rendered."""
    env = jinja2.Environment(extensions=[jinja.SerializerExtension])
    env.tests["match"] = jinja.test_match
    tmpl = env.from_string("{{ 'abc' is match('^a') }}|{{ 'abc' is match('^z') }}")
    assert tmpl.render() == "True|False"


def test_match_is_test_ignorecase_via_render():
    """The 'is match' jinja test honors the ignorecase keyword when rendered."""
    env = jinja2.Environment(extensions=[jinja.SerializerExtension])
    env.tests["match"] = jinja.test_match
    tmpl = env.from_string("{{ 'ABC' is match('^a', ignorecase=True) }}")
    assert tmpl.render() == "True"


def test_equalto_is_test_via_render():
    """The 'is equalto' jinja test produces the expected result when rendered."""
    env = jinja2.Environment(extensions=[jinja.SerializerExtension])
    env.tests["equalto"] = jinja.test_equalto
    tmpl = env.from_string("{{ 1 is equalto(1) }}|{{ 1 is equalto(2) }}")
    assert tmpl.render() == "True|False"


def test_union_hashable_strings():
    """Two hashable inputs produce a set union."""
    assert jinja.union("abc", "cde") == {"a", "b", "c", "d", "e"}


def test_union_lists_preserve_order():
    """Lists are not hashable, so order is preserved and duplicates dropped."""
    assert jinja.union([1, 2, 3, 4], [2, 4, 6]) == [1, 2, 3, 4, 6]


def test_intersect_hashable_strings():
    """Two hashable inputs produce a set intersection."""
    assert jinja.intersect("abc", "bcd") == {"b", "c"}


def test_intersect_lists_preserve_order():
    """Lists return the order-preserving intersection."""
    assert jinja.intersect([1, 2, 3, 4], [2, 4, 6]) == [2, 4]


def test_difference_hashable_strings():
    """Two hashable inputs produce a set difference."""
    assert jinja.difference("abc", "bc") == {"a"}


def test_difference_lists_preserve_order():
    """Lists return the order-preserving difference."""
    assert jinja.difference([1, 2, 3, 4], [2, 4, 6]) == [1, 3]


def test_symmetric_difference_hashable_strings():
    """Two hashable inputs produce a set symmetric difference."""
    assert jinja.symmetric_difference("abc", "cde") == {"a", "b", "d", "e"}


def test_symmetric_difference_lists():
    """Lists return the order-preserving symmetric difference."""
    assert jinja.symmetric_difference([1, 2, 3, 4], [2, 4, 6]) == [1, 3, 6]


def test_lst_avg_list():
    """A list (non-hashable) averages its elements as a float."""
    result = jinja.lst_avg([1, 2, 3, 4])
    assert result == 2.5
    assert isinstance(result, float)


def test_lst_avg_single_value():
    """A single hashable value is cast straight to float."""
    result = jinja.lst_avg(5)
    assert result == 5.0
    assert isinstance(result, float)


def test_method_call_with_args():
    """method_call invokes the named method with the supplied args."""
    assert jinja.method_call("foo bar", "split") == ["foo", "bar"]
    assert jinja.method_call("foo,bar", "split", ",") == ["foo", "bar"]
    assert jinja.method_call("FOO", "lower") == "foo"


def test_method_call_missing_method_returns_none():
    """An unknown method name falls back to a no-op returning None."""
    assert jinja.method_call("x", "does_not_exist") is None


def test_tojson_default_order():
    """tojson keeps insertion order by default (no implicit sort_keys)."""
    assert jinja.tojson({"b": 2, "a": 1}) == '{"b": 2, "a": 1}'


def test_tojson_sort_keys():
    """sort_keys=True sorts the keys in the output."""
    assert jinja.tojson({"b": 2, "a": 1}, sort_keys=True) == '{"a": 1, "b": 2}'


def test_tojson_escapes_html_chars():
    """HTML-sensitive characters are escaped to their unicode forms."""
    assert jinja.tojson('<a href="x">') == '"\\u003ca href=\\"x\\"\\u003e"'


def test_tojson_non_ascii_passthrough():
    """ensure_ascii=False leaves non-ASCII characters intact."""
    assert jinja.tojson("☃", ensure_ascii=False) == '"☃"'


def test_tojson_indent():
    """The indent option is forwarded to the JSON serializer."""
    assert jinja.tojson([1, 2], indent=2) == "[\n  1,\n  2\n]"


def test_tojson_strict_undefined_short_circuits():
    """A StrictUndefined input is returned as StrictUndefined, not serialized."""
    result = jinja.tojson(StrictUndefined(name="missing"))
    assert isinstance(result, StrictUndefined)


def test_skip_filter():
    """skip_filter always renders an empty string regardless of input."""
    assert jinja.skip_filter("foo") == ""
    assert jinja.skip_filter(None) == ""
    assert jinja.skip_filter([1, 2, 3]) == ""
