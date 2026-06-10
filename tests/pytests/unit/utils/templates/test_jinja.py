"""
Tests for salt.utils.templates
"""

import re

from collections import OrderedDict
import pytest
from salt.exceptions import SaltRenderError
from salt.loader.context import LoaderContext
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


def test_render_unwraps_named_loader_context_opts(render_context):
    """
    Regression test for #68572.

    ``salt.modules.cp.get_template`` passes the cp module's loader-backed
    ``__opts__`` (a ``NamedLoaderContext``) through to the Jinja renderer.
    If ``render_jinja_tmpl`` leaves the wrapper in place, the
    ``SaltCacheLoader`` it constructs will instantiate a downstream file
    client / channel with the wrapper as its ``self.opts``. The channel
    runs on the tornado IO loop, where the loader contextvar is not set,
    so ``self.opts.get(...)`` raises ``AttributeError: 'NoneType' object
    has no attribute 'get'``. ``render_jinja_tmpl`` must unwrap a
    ``NamedLoaderContext`` to a plain dict before it reaches that path.
    """
    opts_dict = dict(render_context["opts"])
    wrapped = LoaderContext().named_context("__opts__", default=opts_dict)
    render_context["opts"] = wrapped
    # If the wrapper survives into the renderer, the Jinja environment
    # build-up (which calls ``opts.get(...)``) succeeds only because the
    # default is non-None here; the substantive assertion is the dict-typed
    # opts the SaltCacheLoader sees, captured below.
    seen = {}
    real_init = __import__(
        "salt.utils.jinja", fromlist=["SaltCacheLoader"]
    ).SaltCacheLoader.__init__

    def capture_init(self, opts, *args, **kwargs):
        seen["opts_type"] = type(opts)
        return real_init(self, opts, *args, **kwargs)

    from salt.utils.jinja import SaltCacheLoader

    with patch.object(SaltCacheLoader, "__init__", capture_init):
        # Use a saltenv so the SaltCacheLoader branch executes.
        render_context["saltenv"] = "base"
        # A trivial template avoids the file client running.
        render_jinja_tmpl("OK", render_context)
    # If the fix is in place the loader sees a plain dict.
    assert seen["opts_type"] is dict, seen
