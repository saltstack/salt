"""
Tests for salt.utils.jinja
"""

import os

import salt.config
import salt.loader

# dateutils is needed so that the strftime jinja filter is loaded
import salt.utils.dateutils  # pylint: disable=unused-import
import salt.utils.files
import salt.utils.json
import salt.utils.stringutils
import salt.utils.yaml
from jinja2 import Markup
from salt.utils.jinja import indent, tojson

try:
    import timelib  # pylint: disable=W0611

    HAS_TIMELIB = True
except ImportError:
    HAS_TIMELIB = False

BLINESEP = salt.utils.stringutils.to_bytes(os.linesep)


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
