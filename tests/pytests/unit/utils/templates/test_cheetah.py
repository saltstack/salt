import pytest
from salt.utils.templates import render_cheetah_tmpl

pytest.importorskip("Cheetah")


def test_render_sanity(render_context):
    tmpl = """OK"""
    res = render_cheetah_tmpl(tmpl, render_context)
    assert res == "OK"


def test_render_evaluate(render_context):
    tmpl = """<%="OK"%>"""
    res = render_cheetah_tmpl(tmpl, render_context)
    assert res == "OK"


def test_render_evaluate_xml(render_context):
    tmpl = """
    <% if 1: %>
    OK
    <% pass %>
    """
    res = render_cheetah_tmpl(tmpl, render_context)
    stripped = res.strip()
    assert stripped == "OK"


def test_render_evaluate_text(render_context):
    tmpl = """
    #if 1
    OK
    #end if
    """

    res = render_cheetah_tmpl(tmpl, render_context)
    stripped = res.strip()
    assert stripped == "OK"


def test_render_variable(render_context):
    tmpl = """$var"""

    render_context["var"] = "OK"
    res = render_cheetah_tmpl(tmpl, render_context)
    assert res.strip() == "OK"
