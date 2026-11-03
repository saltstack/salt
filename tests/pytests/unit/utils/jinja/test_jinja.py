"""
Tests for salt.utils.jinja
"""

import salt.utils.dateutils  # pylint: disable=unused-import
from salt.utils.jinja import Markup, PrintableDict, indent, tojson


def test_tojson():
    """
    Test the ported tojson filter. Non-ascii unicode content should be
    dumped with ensure_ascii=True.
    """
    data = {"Non-ascii words": ["süß", "спам", "яйца"]}
    result = tojson(data)
    expected = (
        '{"Non-ascii words": ["s\\u00fc\\u00df", '
        '"\\u0441\\u043f\\u0430\\u043c", '
        '"\\u044f\\u0439\\u0446\\u0430"]}'
    )
    assert result == expected, result


def test_indent():
    """
    Test the indent filter with Markup object as input. Double-quotes
    should not be URL-encoded.
    """
    data = Markup('foo:\n  "bar"')
    result = indent(data)
    expected = Markup('foo:\n      "bar"')
    assert result == expected, result


def test_tojson_should_ascii_sort_keys_when_told():
    data = {"z": "zzz", "y": "yyy", "x": "xxx"}
    expected = '{"x": "xxx", "y": "yyy", "z": "zzz"}'

    actual = tojson(data, sort_keys=True)
    assert actual == expected


def test_printabledict_long_multiline_str_not_folded_issue_69658():
    """
    Regression test for issue #69658.

    ``PrintableDict.__str__`` emits string values containing newlines as
    YAML double-quoted scalars via ``yaml.safe_dump()`` (see #30690).
    ``safe_dump()`` folds double-quoted scalars at ~80 columns by default,
    which inserts real newlines into the emitted scalar. When the resulting
    representation is interpolated into a YAML state file via Jinja inside
    a ``|``/``|-`` block scalar, the folded continuation lines break the
    document and rendering fails with ``could not find expected ':'``.

    The emitted representation must therefore stay on a single physical
    line even for long strings so it can be safely interpolated inside a
    block scalar.
    """
    long_value = (
        "ServerName my-very-long-hostname.example.com and more words "
        "to exceed eighty columns\n"
        "ServerAlias alias.example.com\n"
    )
    rendered = str(PrintableDict({"conf": long_value}))
    # The rendered dict must be a single physical line: any newline
    # inside it would be a fold-point that breaks YAML block-scalar
    # interpolation.
    assert "\n" not in rendered, rendered
