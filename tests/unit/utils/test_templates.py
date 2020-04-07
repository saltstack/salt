# -*- coding: utf-8 -*-
"""
Unit tests for salt.utils.templates.py
"""

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

import logging
import os
import sys

import salt.utils.files

# Import Salt libs
import salt.utils.templates

# Import Salt Testing Libs
from tests.support.helpers import with_tempdir
from tests.support.unit import TestCase, skipIf

log = logging.getLogger(__name__)


### Here we go!
class RenderTestCase(TestCase):
    def setUp(self):
        # Default context for salt.utils.templates.render_*_tmpl to work
        self.context = {
            "opts": {"cachedir": "/D", "__cli": "salt"},
            "saltenv": None,
        }

    ### Tests for Jinja (whitespace-friendly)
    def test_render_jinja_sanity(self):
        tmpl = """OK"""
        res = salt.utils.templates.render_jinja_tmpl(tmpl, dict(self.context))
        self.assertEqual(res, "OK")

    def test_render_jinja_evaluate(self):
        tmpl = """{{ "OK" }}"""
        res = salt.utils.templates.render_jinja_tmpl(tmpl, dict(self.context))
        self.assertEqual(res, "OK")

    def test_render_jinja_evaluate_multi(self):
        tmpl = """{% if 1 -%}OK{%- endif %}"""
        res = salt.utils.templates.render_jinja_tmpl(tmpl, dict(self.context))
        self.assertEqual(res, "OK")

    def test_render_jinja_variable(self):
        tmpl = """{{ var }}"""

        ctx = dict(self.context)
        ctx["var"] = "OK"
        res = salt.utils.templates.render_jinja_tmpl(tmpl, ctx)
        self.assertEqual(res, "OK")

    ### Tests for mako template
    def test_render_mako_sanity(self):
        tmpl = """OK"""
        res = salt.utils.templates.render_mako_tmpl(tmpl, dict(self.context))
        self.assertEqual(res, "OK")

    def test_render_mako_evaluate(self):
        tmpl = """${ "OK" }"""
        res = salt.utils.templates.render_mako_tmpl(tmpl, dict(self.context))
        self.assertEqual(res, "OK")

    def test_render_mako_evaluate_multi(self):
        tmpl = """
        % if 1:
        OK
        % endif
        """
        res = salt.utils.templates.render_mako_tmpl(tmpl, dict(self.context))
        stripped = res.strip()
        self.assertEqual(stripped, "OK")

    def test_render_mako_variable(self):
        tmpl = """${ var }"""

        ctx = dict(self.context)
        ctx["var"] = "OK"
        res = salt.utils.templates.render_mako_tmpl(tmpl, ctx)
        self.assertEqual(res, "OK")

    ### Tests for wempy template
    @skipIf(
        sys.version_info > (3,),
        "The wempy module is currently unsupported under Python3",
    )
    def test_render_wempy_sanity(self):
        tmpl = """OK"""
        res = salt.utils.templates.render_wempy_tmpl(tmpl, dict(self.context))
        self.assertEqual(res, "OK")

    @skipIf(
        sys.version_info > (3,),
        "The wempy module is currently unsupported under Python3",
    )
    def test_render_wempy_evaluate(self):
        tmpl = """{{="OK"}}"""
        res = salt.utils.templates.render_wempy_tmpl(tmpl, dict(self.context))
        self.assertEqual(res, "OK")

    @skipIf(
        sys.version_info > (3,),
        "The wempy module is currently unsupported under Python3",
    )
    def test_render_wempy_evaluate_multi(self):
        tmpl = """{{if 1:}}OK{{pass}}"""
        res = salt.utils.templates.render_wempy_tmpl(tmpl, dict(self.context))
        self.assertEqual(res, "OK")

    @skipIf(
        sys.version_info > (3,),
        "The wempy module is currently unsupported under Python3",
    )
    def test_render_wempy_variable(self):
        tmpl = """{{=var}}"""

        ctx = dict(self.context)
        ctx["var"] = "OK"
        res = salt.utils.templates.render_wempy_tmpl(tmpl, ctx)
        self.assertEqual(res, "OK")

    ### Tests for genshi template (xml-based)
    def test_render_genshi_sanity(self):
        tmpl = """<RU>OK</RU>"""
        res = salt.utils.templates.render_genshi_tmpl(tmpl, dict(self.context))
        self.assertEqual(res, "<RU>OK</RU>")

    def test_render_genshi_evaluate(self):
        tmpl = """<RU>${ "OK" }</RU>"""
        res = salt.utils.templates.render_genshi_tmpl(tmpl, dict(self.context))
        self.assertEqual(res, "<RU>OK</RU>")

    def test_render_genshi_evaluate_condition(self):
        tmpl = """<RU xmlns:py="http://genshi.edgewall.org/" py:if="1">OK</RU>"""
        res = salt.utils.templates.render_genshi_tmpl(tmpl, dict(self.context))
        self.assertEqual(res, "<RU>OK</RU>")

    def test_render_genshi_variable(self):
        tmpl = """<RU>$var</RU>"""

        ctx = dict(self.context)
        ctx["var"] = "OK"
        res = salt.utils.templates.render_genshi_tmpl(tmpl, ctx)
        self.assertEqual(res, "<RU>OK</RU>")

    def test_render_genshi_variable_replace(self):
        tmpl = """<RU xmlns:py="http://genshi.edgewall.org/" py:content="var">not ok</RU>"""

        ctx = dict(self.context)
        ctx["var"] = "OK"
        res = salt.utils.templates.render_genshi_tmpl(tmpl, ctx)
        self.assertEqual(res, "<RU>OK</RU>")

    ### Tests for cheetah template (line-oriented and xml-friendly)
    def test_render_cheetah_sanity(self):
        tmpl = """OK"""
        res = salt.utils.templates.render_cheetah_tmpl(tmpl, dict(self.context))
        self.assertEqual(res, "OK")

    def test_render_cheetah_evaluate(self):
        tmpl = """<%="OK"%>"""
        res = salt.utils.templates.render_cheetah_tmpl(tmpl, dict(self.context))
        self.assertEqual(res, "OK")

    def test_render_cheetah_evaluate_xml(self):
        tmpl = """
        <% if 1: %>
        OK
        <% pass %>
        """
        res = salt.utils.templates.render_cheetah_tmpl(tmpl, dict(self.context))
        stripped = res.strip()
        self.assertEqual(stripped, "OK")

    def test_render_cheetah_evaluate_text(self):
        tmpl = """
        #if 1
        OK
        #end if
        """

        res = salt.utils.templates.render_cheetah_tmpl(tmpl, dict(self.context))
        stripped = res.strip()
        self.assertEqual(stripped, "OK")

    def test_render_cheetah_variable(self):
        tmpl = """$var"""

        ctx = dict(self.context)
        ctx["var"] = "OK"
        res = salt.utils.templates.render_cheetah_tmpl(tmpl, ctx)
        self.assertEqual(res.strip(), "OK")


class MockRender(object):
    def __call__(self, tplstr, context, tmplpath=None):
        self.tplstr = tplstr
        self.context = context
        self.tmplpath = tmplpath
        return tplstr


class WrapRenderTestCase(TestCase):
    @with_tempdir()
    def test_wrap_issue_56119_a(self, tempdir):
        slsfile = os.path.join(tempdir, "foo")
        with salt.utils.files.fopen(slsfile, "w") as fp:
            fp.write("{{ slspath }}")
        context = {"opts": {}, "saltenv": "base", "sls": "foo.bar"}
        render = MockRender()
        wrapped = salt.utils.templates.wrap_tmpl_func(render)
        res = wrapped(slsfile, context=context, tmplpath="/tmp/foo/bar/init.sls")
        assert render.context["slspath"] == "foo/bar", render.context["slspath"]
        assert render.context["tpldir"] == "foo/bar", render.context["tpldir"]

    @with_tempdir()
    def test_wrap_issue_56119_b(self, tempdir):
        slsfile = os.path.join(tempdir, "foo")
        with salt.utils.files.fopen(slsfile, "w") as fp:
            fp.write("{{ slspath }}")
        context = {"opts": {}, "saltenv": "base", "sls": "foo.bar.bang"}
        render = MockRender()
        wrapped = salt.utils.templates.wrap_tmpl_func(render)
        res = wrapped(slsfile, context=context, tmplpath="/tmp/foo/bar/bang.sls")
        assert render.context["slspath"] == "foo/bar", render.context["slspath"]
        assert render.context["tpldir"] == "foo/bar", render.context["tpldir"]
