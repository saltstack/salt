import pytest
from salt.utils.templates import render_mako_tmpl

pytest.importorskip("mako")


def test_render_mako_sanity(render_context):
    tmpl = """OK"""
    res = render_mako_tmpl(tmpl, render_context)
    assert res == "OK"


def test_render_mako_evaluate(render_context):
    tmpl = """${ "OK" }"""
    res = render_mako_tmpl(tmpl, render_context)
    assert res == "OK"


def test_render_mako_evaluate_multi(render_context):
    tmpl = """
    % if 1:
    OK
    % endif
    """
    res = render_mako_tmpl(tmpl, render_context)
    stripped = res.strip()
    assert stripped == "OK"


def test_render_mako_variable(render_context):
    tmpl = """${ var }"""
    render_context["var"] = "OK"
    res = render_mako_tmpl(tmpl, render_context)
    assert res == "OK"
