"""
Tests for salt.utils.templates
"""

import re

from collections import OrderedDict
import pytest
from salt.exceptions import SaltRenderError
from salt.utils.templates import render_jinja_tmpl

from tests.support.mock import patch


def test_undefined_error_context(render_context):
    """
    Test that jinja provides both the line number on which the error occurred
    in the Jinja template, and also several lines of context around the error
    in the Jinja template source when ``jinja2.exceptions.UndefinedError`` is
    raised.
    """

    jinja_code = """
    {%- set sections = {"first": {"a": "b"}, "second": ["a", "b"]} %}
    {%- for section in sections %}
      {%- for name, config in section.items() %}
      {%- endfor %}
    {%- endfor %}
    """
    marker = "    <======================"

    # Test that the exception messages includes the source file context details
    # and marker.  Since salt catches and re-emits internal jinja exceptions as
    # `SaltRenderError`, the easiest way to distinguish which original
    # exception was raised is to match on the initial wording of the exception
    # message.
    match_regex = re.compile(
        rf"^Jinja variable .*; line .*{marker}$", re.DOTALL | re.MULTILINE
    )
    with pytest.raises(SaltRenderError, match=match_regex):
        render_jinja_tmpl(
            jinja_code,
            render_context,
        )


def test_render_sanity(render_context):
    tmpl = """OK"""
    res = render_jinja_tmpl(tmpl, render_context)
    assert res == "OK"


def test_render_evaluate(render_context):
    tmpl = """{{ "OK" }}"""
    res = render_jinja_tmpl(tmpl, render_context)
    assert res == "OK"


def test_render_evaluate_multi(render_context):
    tmpl = """{% if 1 -%}OK{%- endif %}"""
    res = render_jinja_tmpl(tmpl, render_context)
    assert res == "OK"


def test_render_variable(render_context):
    tmpl = """{{ var }}"""
    render_context["var"] = "OK"
    res = render_jinja_tmpl(tmpl, render_context)
    assert res == "OK"


def test_render_tojson_sorted(render_context):
    templ = """thing: {{ var|tojson(sort_keys=True) }}"""
    expected = """thing: {"x": "xxx", "y": "yyy", "z": "zzz"}"""

    with patch.dict(render_context, {"var": {"z": "zzz", "y": "yyy", "x": "xxx"}}):
        res = render_jinja_tmpl(templ, render_context)

    assert res == expected


def test_render_tojson_unsorted(render_context):
    templ = """thing: {{ var|tojson(sort_keys=False) }}"""
    expected = """thing: {"z": "zzz", "x": "xxx", "y": "yyy"}"""

    # Values must be added to the dict in the expected order. This is
    # only necessary for older Pythons that don't remember dict order.
    d = OrderedDict()
    d["z"] = "zzz"
    d["x"] = "xxx"
    d["y"] = "yyy"

    with patch.dict(render_context, {"var": d}):
        res = render_jinja_tmpl(templ, render_context)

    assert res == expected


def test_render_cve_2021_25283(render_context):
    tmpl = """{{ [].__class__ }}"""
    render_context["var"] = "OK"
    with pytest.raises(SaltRenderError):
        res = render_jinja_tmpl(tmpl, render_context)
