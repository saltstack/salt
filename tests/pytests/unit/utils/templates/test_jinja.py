"""
Tests for salt.utils.templates
"""

import logging
import re
from collections import OrderedDict

import pytest

from salt.exceptions import SaltRenderError
from salt.loader.context import LoaderContext
from salt.utils.templates import generate_sls_context, render_jinja_tmpl
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


def test_render_undefined_raises_render_error(render_context):
    """An undefined variable under StrictUndefined raises SaltRenderError."""
    with pytest.raises(SaltRenderError) as excinfo:
        render_jinja_tmpl("{{ undefined_var }}", render_context)
    assert str(excinfo.value).startswith("Jinja variable 'undefined_var' is undefined")


def test_render_undefined_reports_line_number(render_context):
    """The undefined-variable error reports the line of the offending variable."""
    tmpl = "first\nsecond\n{{ missing }}"
    with pytest.raises(SaltRenderError) as excinfo:
        render_jinja_tmpl(tmpl, render_context)
    exc = excinfo.value
    assert exc.line_num == 3
    assert str(exc).splitlines()[0] == "Jinja variable 'missing' is undefined; line 3"


def test_render_undefined_includes_context_marker(render_context):
    """The undefined error embeds the source line with the position marker."""
    marker = "    <======================"
    with pytest.raises(SaltRenderError) as excinfo:
        render_jinja_tmpl("{{ missing }}", render_context)
    message = str(excinfo.value)
    assert "{{ missing }}" + marker in message


def test_render_syntax_error_raises_render_error(render_context):
    """A Jinja syntax error raises SaltRenderError tagged as a syntax error."""
    with pytest.raises(SaltRenderError) as excinfo:
        render_jinja_tmpl("{% if %}", render_context)
    assert str(excinfo.value).startswith("Jinja syntax error:")


def test_render_syntax_error_reports_line_number(render_context):
    """A multi-line template's syntax error reports the offending line number."""
    tmpl = "line1\n{% if %}\nline3"
    with pytest.raises(SaltRenderError) as excinfo:
        render_jinja_tmpl(tmpl, render_context)
    assert excinfo.value.line_num == 2


def test_render_allow_undefined_returns_empty(render_context):
    """With allow_undefined set, an undefined variable renders as empty, not an error."""
    render_context["opts"]["allow_undefined"] = True
    res = render_jinja_tmpl("a{{ undefined_var }}b", render_context)
    assert res == "ab"


def test_render_tmplpath_filesystem_include(render_context, tmp_path):
    """A non-saltenv tmplpath sets up a FileSystemLoader so includes resolve."""
    included = tmp_path / "inc.txt"
    included.write_text("INCLUDED")
    res = render_jinja_tmpl(
        '{% include "inc.txt" %}',
        render_context,
        tmplpath=str(tmp_path / "main.sls"),
    )
    assert res == "INCLUDED"


def test_render_tmplpath_missing_include_raises(render_context, tmp_path):
    """A missing include through the FileSystemLoader raises SaltRenderError."""
    with pytest.raises(SaltRenderError):
        render_jinja_tmpl(
            '{% include "does_not_exist.txt" %}',
            render_context,
            tmplpath=str(tmp_path / "main.sls"),
        )


def test_generate_sls_context_sls_file():
    """A standard .sls template yields the directory-based context values."""
    ctx = generate_sls_context("/srv/salt/foo/bar.sls", "foo.bar")
    assert ctx == {
        "tplpath": "/srv/salt/foo/bar.sls",
        "tplfile": "foo/bar.sls",
        "tpldir": "foo",
        "tpldot": "foo",
        "slspath": "foo",
        "slsdotpath": "foo",
        "slscolonpath": "foo",
        "sls_path": "foo",
    }


def test_generate_sls_context_init_sls():
    """An init.sls template maps to its containing directory."""
    ctx = generate_sls_context("/srv/salt/foo/init.sls", "foo")
    assert ctx["tplfile"] == "foo/init.sls"
    assert ctx["tpldir"] == "foo"
    assert ctx["slspath"] == "foo"


def test_generate_sls_context_nested_sls():
    """A nested .sls path produces slash/dot/colon/underscore separated forms."""
    ctx = generate_sls_context("/srv/salt/a/b/c.sls", "a.b.c")
    assert ctx["tpldir"] == "a/b"
    assert ctx["tpldot"] == "a.b"
    assert ctx["slscolonpath"] == "a:b"
    assert ctx["sls_path"] == "a_b"
    assert ctx["slsdotpath"] == "a.b"


def test_generate_sls_context_top_level_sls():
    """A top-level .sls (no directory) yields '.' tpldir and empty sls paths."""
    ctx = generate_sls_context("/srv/salt/foo.sls", "foo")
    assert ctx["tpldir"] == "."
    assert ctx["tpldot"] == ""
    assert ctx["slspath"] == ""
    assert ctx["slscolonpath"] == ""
    assert ctx["sls_path"] == ""


def test_generate_sls_context_non_sls_file(caplog):
    """A template path that cannot be reconciled with the sls name logs a
    warning and keeps the full template path as tplfile (the root cannot be
    stripped, so all derived path variables carry the full path too)."""
    with caplog.at_level(logging.WARNING):
        ctx = generate_sls_context("/srv/salt/foo/bar.txt", "foo.bar")
    assert "Failed to determine proper template path" in caplog.text
    assert ctx == {
        "tplpath": "/srv/salt/foo/bar.txt",
        "tplfile": "/srv/salt/foo/bar.txt",
        "tpldir": "/srv/salt/foo",
        "tpldot": ".srv.salt.foo",
        "slspath": "/srv/salt/foo",
        "slsdotpath": ".srv.salt.foo",
        "slscolonpath": ":srv:salt:foo",
        "sls_path": "_srv_salt_foo",
    }


def test_generate_sls_context_no_tmplpath():
    """With no tmplpath, only the sls-derived path variables are returned."""
    ctx = generate_sls_context(None, "foo.bar")
    assert "tplpath" not in ctx
    assert ctx == {
        "slspath": "foo/bar",
        "slsdotpath": "foo.bar",
        "slscolonpath": "foo:bar",
        "sls_path": "foo_bar",
    }


def test_generate_sls_context_empty_sls():
    """An empty sls with a tmplpath strips the template down to its basename."""
    ctx = generate_sls_context("/srv/salt/foo/bar.sls", "")
    assert ctx["tplfile"] == "bar.sls"
    assert ctx["tpldir"] == "."
    assert ctx["slspath"] == ""
