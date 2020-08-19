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

try:
    import Cheetah as _

    HAS_CHEETAH = True
except ImportError:
    HAS_CHEETAH = False

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
    @skipIf(not HAS_CHEETAH, "The Cheetah Python module is missing.")
    def test_render_cheetah_sanity(self):
        tmpl = """OK"""
        res = salt.utils.templates.render_cheetah_tmpl(tmpl, dict(self.context))
        self.assertEqual(res, "OK")

    @skipIf(not HAS_CHEETAH, "The Cheetah Python module is missing.")
    def test_render_cheetah_evaluate(self):
        tmpl = """<%="OK"%>"""
        res = salt.utils.templates.render_cheetah_tmpl(tmpl, dict(self.context))
        self.assertEqual(res, "OK")

    @skipIf(not HAS_CHEETAH, "The Cheetah Python module is missing.")
    def test_render_cheetah_evaluate_xml(self):
        tmpl = """
        <% if 1: %>
        OK
        <% pass %>
        """
        res = salt.utils.templates.render_cheetah_tmpl(tmpl, dict(self.context))
        stripped = res.strip()
        self.assertEqual(stripped, "OK")

    @skipIf(not HAS_CHEETAH, "The Cheetah Python module is missing.")
    def test_render_cheetah_evaluate_text(self):
        tmpl = """
        #if 1
        OK
        #end if
        """

        res = salt.utils.templates.render_cheetah_tmpl(tmpl, dict(self.context))
        stripped = res.strip()
        self.assertEqual(stripped, "OK")

    @skipIf(not HAS_CHEETAH, "The Cheetah Python module is missing.")
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

    def _sub_dict(self, src, ref):
        """ Create a sub-dictionary containing keys from reference"""
        return {key: src[key] for key in ref.keys() if key in src.keys()}

    def assertDictContainsAll(self, actual, **expected):
        """ Make sure dictionary contains at least all expected values"""
        actual = self._sub_dict(actual, expected)
        self.assertEqual(expected, actual)

    @with_tempdir()
    def _get_context(self, tempdir, tmplpath, sls):
        """ Get context from render """
        slsfile = os.path.join(tempdir, "foo")
        with salt.utils.files.fopen(slsfile, "w") as fp:
            fp.write("{{ slspath }}")
        context = {"opts": {}, "saltenv": "base", "sls": sls}
        render = MockRender()
        wrapped = salt.utils.templates.wrap_tmpl_func(render)
        res = wrapped(slsfile, context=context, tmplpath=tmplpath)
        return render.context

    def _test_generated_sls_context_new(self, tmplpath, sls, expected):
        """ Generic SLS Context Test"""
        #actual = salt.utils.templates.generate_sls_context(tmplpath, sls)
        #self.assertDictEqual(actual, expected)

    def _test_generated_sls_context(self, tmplpath, sls, **expected):
        """ Test SLS Context generation via rendering"""
        actual = self._get_context(tmplpath=tmplpath, sls=sls)
        self.assertDictContainsAll(actual, **expected)

    def test_generate_sls_context__top_level(self):
        """ generate_sls_context - top_level Use case"""
        self._test_generated_sls_context("/tmp/boo.sls", "boo",
                                         tplpath="/tmp/boo.sls",
                                         tplfile="boo.sls",
                                         tpldir=".",
                                         tpldot="",
                                         slsdotpath="",
                                         slscolonpath="",
                                         sls_path="",
                                         slspath="")

    def test_generate_sls_context__one_level_init_implicit(self):
        """ generate_sls_context - Basic one level with impliocit init.sls """
        self._test_generated_sls_context("/tmp/foo/init.sls", "foo",
                                         tplpath="/tmp/foo/init.sls",
                                         tplfile="foo/init.sls",
                                         tpldir="foo",
                                         tpldot="foo",
                                         slsdotpath="foo",
                                         slscolonpath="foo",
                                         sls_path="foo",
                                         slspath="foo")

    def test_generate_sls_context__one_level_init_explicit(self):
        """ generate_sls_context - Basic one level with explicit init.sls """
        self._test_generated_sls_context("/tmp/foo/init.sls", "foo.init",
                                         tplpath="/tmp/foo/init.sls",
                                         tplfile="foo/init.sls",
                                         tpldir="foo",
                                         tpldot="foo",
                                         slsdotpath="foo",
                                         slscolonpath="foo",
                                         sls_path="foo",
                                         slspath="foo")

    def test_generate_sls_context__one_level(self):
        """ generate_sls_context - Basic one level with name"""
        self._test_generated_sls_context("/tmp/foo/boo.sls", "foo.boo",
                                         tplpath="/tmp/foo/boo.sls",
                                         tplfile="foo/boo.sls",
                                         tpldir="foo",
                                         tpldot="foo",
                                         slsdotpath="foo",
                                         slscolonpath="foo",
                                         sls_path="foo",
                                         slspath="foo")

    def test_generate_sls_context__one_level_repeating(self):
        """ generate_sls_context - Basic one level with name same as dir

        (Issue #56410)
        """
        self._test_generated_sls_context("/tmp/foo/foo.sls", "foo.foo",
                                         tplpath="/tmp/foo/foo.sls",
                                         tplfile="foo/foo.sls",
                                         tpldir="foo",
                                         tpldot="foo",
                                         slsdotpath="foo",
                                         slscolonpath="foo",
                                         sls_path="foo",
                                         slspath="foo")

    def test_generate_sls_context__two_level_init_implicit(self):
        """ generate_sls_context - Basic two level with implicit init.sls """
        self._test_generated_sls_context("/tmp/foo/bar/init.sls", "foo.bar",
                                         tplpath="/tmp/foo/bar/init.sls",
                                         tplfile="foo/bar/init.sls",
                                         tpldir="foo/bar",
                                         tpldot="foo.bar",
                                         slsdotpath="foo.bar",
                                         slscolonpath="foo:bar",
                                         sls_path="foo_bar",
                                         slspath="foo/bar")

    def test_generate_sls_context__two_level_init_explicit(self):
        """ generate_sls_context - Basic two level with explicit init.sls """
        self._test_generated_sls_context("/tmp/foo/bar/init.sls", "foo.bar.init",
                                         tplpath="/tmp/foo/bar/init.sls",
                                         tplfile="foo/bar/init.sls",
                                         tpldir="foo/bar",
                                         tpldot="foo.bar",
                                         slsdotpath="foo.bar",
                                         slscolonpath="foo:bar",
                                         sls_path="foo_bar",
                                         slspath="foo/bar")

    def test_generate_sls_context__two_level(self):
        """ generate_sls_context - Basic two level with name"""
        self._test_generated_sls_context("/tmp/foo/bar/boo.sls", "foo.bar.boo",
                                         tplpath="/tmp/foo/bar/boo.sls",
                                         tplfile="foo/bar/boo.sls",
                                         tpldir="foo/bar",
                                         tpldot="foo.bar",
                                         slsdotpath="foo.bar",
                                         slscolonpath="foo:bar",
                                         sls_path="foo_bar",
                                         slspath="foo/bar")

    def test_generate_sls_context__two_level_repeating(self):
        """ generate_sls_context - Basic two level with name same as dir

        (Issue #56410)
        """
        self._test_generated_sls_context("/tmp/foo/foo/foo.sls", "foo.foo.foo",
                                         tplpath="/tmp/foo/foo/foo.sls",
                                         tplfile="foo/foo/foo.sls",
                                         tpldir="foo/foo",
                                         tpldot="foo.foo",
                                         slsdotpath="foo.foo",
                                         slscolonpath="foo:foo",
                                         sls_path="foo_foo",
                                         slspath="foo/foo",)

    def test_generate_sls_context__two_level_repeating2(self):
        """ generate_sls_context - Basic two level with name same as dir

        (Issue #56410)
        """
        self._test_generated_sls_context("/tmp/foo/foo/foo_bar.sls",
                                         "foo.foo.foo_bar",
                                         tplpath="/tmp/foo/foo/foo_bar.sls",
                                         tplfile="foo/foo/foo_bar.sls",
                                         tpldir="foo/foo",
                                         tpldot="foo.foo",
                                         slsdotpath="foo.foo",
                                         slscolonpath="foo:foo",
                                         sls_path="foo_foo",
                                         slspath="foo/foo")
