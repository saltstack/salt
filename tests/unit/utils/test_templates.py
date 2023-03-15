"""
Unit tests for salt.utils.templates.py
"""
import logging
import os
import sys
from collections import OrderedDict
from pathlib import PurePath, PurePosixPath

import pytest

import salt.utils.files
import salt.utils.templates
from tests.support.helpers import with_tempdir
from tests.support.mock import patch
from tests.support.unit import TestCase

try:
    import Cheetah as _

    HAS_CHEETAH = True
except ImportError:
    HAS_CHEETAH = False

log = logging.getLogger(__name__)


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

    def test_render_jinja_tojson_sorted(self):
        templ = """thing: {{ var|tojson(sort_keys=True) }}"""
        expected = """thing: {"x": "xxx", "y": "yyy", "z": "zzz"}"""

        with patch.dict(self.context, {"var": {"z": "zzz", "y": "yyy", "x": "xxx"}}):
            res = salt.utils.templates.render_jinja_tmpl(templ, self.context)

        assert res == expected

    def test_render_jinja_tojson_unsorted(self):
        templ = """thing: {{ var|tojson(sort_keys=False) }}"""
        expected = """thing: {"z": "zzz", "x": "xxx", "y": "yyy"}"""

        # Values must be added to the dict in the expected order. This is
        # only necessary for older Pythons that don't remember dict order.
        d = OrderedDict()
        d["z"] = "zzz"
        d["x"] = "xxx"
        d["y"] = "yyy"

        with patch.dict(self.context, {"var": d}):
            res = salt.utils.templates.render_jinja_tmpl(templ, self.context)

        assert res == expected

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
    @pytest.mark.skipif(
        sys.version_info > (3,),
        reason="The wempy module is currently unsupported under Python3",
    )
    def test_render_wempy_sanity(self):
        tmpl = """OK"""
        res = salt.utils.templates.render_wempy_tmpl(tmpl, dict(self.context))
        self.assertEqual(res, "OK")

    @pytest.mark.skipif(
        sys.version_info > (3,),
        reason="The wempy module is currently unsupported under Python3",
    )
    def test_render_wempy_evaluate(self):
        tmpl = """{{="OK"}}"""
        res = salt.utils.templates.render_wempy_tmpl(tmpl, dict(self.context))
        self.assertEqual(res, "OK")

    @pytest.mark.skipif(
        sys.version_info > (3,),
        reason="The wempy module is currently unsupported under Python3",
    )
    def test_render_wempy_evaluate_multi(self):
        tmpl = """{{if 1:}}OK{{pass}}"""
        res = salt.utils.templates.render_wempy_tmpl(tmpl, dict(self.context))
        self.assertEqual(res, "OK")

    @pytest.mark.skipif(
        sys.version_info > (3,),
        reason="The wempy module is currently unsupported under Python3",
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
    @pytest.mark.skipif(not HAS_CHEETAH, reason="The Cheetah Python module is missing.")
    def test_render_cheetah_sanity(self):
        tmpl = """OK"""
        res = salt.utils.templates.render_cheetah_tmpl(tmpl, dict(self.context))
        self.assertEqual(res, "OK")

    @pytest.mark.skipif(not HAS_CHEETAH, reason="The Cheetah Python module is missing.")
    def test_render_cheetah_evaluate(self):
        tmpl = """<%="OK"%>"""
        res = salt.utils.templates.render_cheetah_tmpl(tmpl, dict(self.context))
        self.assertEqual(res, "OK")

    @pytest.mark.skipif(not HAS_CHEETAH, reason="The Cheetah Python module is missing.")
    def test_render_cheetah_evaluate_xml(self):
        tmpl = """
        <% if 1: %>
        OK
        <% pass %>
        """
        res = salt.utils.templates.render_cheetah_tmpl(tmpl, dict(self.context))
        stripped = res.strip()
        self.assertEqual(stripped, "OK")

    @pytest.mark.skipif(not HAS_CHEETAH, reason="The Cheetah Python module is missing.")
    def test_render_cheetah_evaluate_text(self):
        tmpl = """
        #if 1
        OK
        #end if
        """

        res = salt.utils.templates.render_cheetah_tmpl(tmpl, dict(self.context))
        stripped = res.strip()
        self.assertEqual(stripped, "OK")

    @pytest.mark.skipif(not HAS_CHEETAH, reason="The Cheetah Python module is missing.")
    def test_render_cheetah_variable(self):
        tmpl = """$var"""

        ctx = dict(self.context)
        ctx["var"] = "OK"
        res = salt.utils.templates.render_cheetah_tmpl(tmpl, ctx)
        self.assertEqual(res.strip(), "OK")

    def test_render_jinja_cve_2021_25283(self):
        tmpl = """{{ [].__class__ }}"""
        ctx = dict(self.context)
        ctx["var"] = "OK"
        with pytest.raises(salt.exceptions.SaltRenderError):
            res = salt.utils.templates.render_jinja_tmpl(tmpl, ctx)


class MockRender:
    def __call__(self, tplstr, context, tmplpath=None):
        self.tplstr = tplstr
        self.context = context
        self.tmplpath = tmplpath
        return tplstr


class WrapRenderTestCase(TestCase):
    def assertDictContainsAll(self, actual, **expected):
        """Make sure dictionary contains at least all expected values"""
        actual = {key: actual[key] for key in expected if key in actual}
        self.assertEqual(expected, actual)

    def _test_generated_sls_context(self, tmplpath, sls, **expected):
        """Generic SLS Context Test"""
        # DeNormalize tmplpath
        tmplpath = str(PurePath(PurePosixPath(tmplpath)))
        if tmplpath.startswith("\\"):
            tmplpath = "C:{}".format(tmplpath)
        expected["tplpath"] = tmplpath
        actual = salt.utils.templates.generate_sls_context(tmplpath, sls)
        self.assertDictContainsAll(actual, **expected)

    @patch("salt.utils.templates.generate_sls_context")
    @with_tempdir()
    def test_sls_context_call(self, tempdir, generate_sls_context):
        """Check that generate_sls_context is called with proper parameters"""
        sls = "foo.bar"
        tmplpath = "/tmp/foo/bar.sls"

        slsfile = os.path.join(tempdir, "foo")
        with salt.utils.files.fopen(slsfile, "w") as fp:
            fp.write("{{ slspath }}")
        context = {"opts": {}, "saltenv": "base", "sls": sls}
        render = MockRender()
        wrapped = salt.utils.templates.wrap_tmpl_func(render)
        res = wrapped(slsfile, context=context, tmplpath=tmplpath)
        generate_sls_context.assert_called_with(tmplpath, sls)

    @patch("salt.utils.templates.generate_sls_context")
    @with_tempdir()
    def test_sls_context_no_call(self, tempdir, generate_sls_context):
        """Check that generate_sls_context is not called if sls is not set"""
        sls = "foo.bar"
        tmplpath = "/tmp/foo/bar.sls"

        slsfile = os.path.join(tempdir, "foo")
        with salt.utils.files.fopen(slsfile, "w") as fp:
            fp.write("{{ slspath }}")
        context = {"opts": {}, "saltenv": "base"}
        render = MockRender()
        wrapped = salt.utils.templates.wrap_tmpl_func(render)
        res = wrapped(slsfile, context=context, tmplpath=tmplpath)
        generate_sls_context.assert_not_called()

    def test_generate_sls_context__top_level(self):
        """generate_sls_context - top_level Use case"""
        self._test_generated_sls_context(
            "/tmp/boo.sls",
            "boo",
            tplfile="boo.sls",
            tpldir=".",
            tpldot="",
            slsdotpath="",
            slscolonpath="",
            sls_path="",
            slspath="",
        )

    def test_generate_sls_context__one_level_init_implicit(self):
        """generate_sls_context - Basic one level with implicit init.sls"""
        self._test_generated_sls_context(
            "/tmp/foo/init.sls",
            "foo",
            tplfile="foo/init.sls",
            tpldir="foo",
            tpldot="foo",
            slsdotpath="foo",
            slscolonpath="foo",
            sls_path="foo",
            slspath="foo",
        )

    def test_generate_sls_context__one_level_init_explicit(self):
        """generate_sls_context - Basic one level with explicit init.sls"""
        self._test_generated_sls_context(
            "/tmp/foo/init.sls",
            "foo.init",
            tplfile="foo/init.sls",
            tpldir="foo",
            tpldot="foo",
            slsdotpath="foo",
            slscolonpath="foo",
            sls_path="foo",
            slspath="foo",
        )

    def test_generate_sls_context__one_level(self):
        """generate_sls_context - Basic one level with name"""
        self._test_generated_sls_context(
            "/tmp/foo/boo.sls",
            "foo.boo",
            tplfile="foo/boo.sls",
            tpldir="foo",
            tpldot="foo",
            slsdotpath="foo",
            slscolonpath="foo",
            sls_path="foo",
            slspath="foo",
        )

    def test_generate_sls_context__one_level_repeating(self):
        """generate_sls_context - Basic one level with name same as dir

        (Issue #56410)
        """
        self._test_generated_sls_context(
            "/tmp/foo/foo.sls",
            "foo.foo",
            tplfile="foo/foo.sls",
            tpldir="foo",
            tpldot="foo",
            slsdotpath="foo",
            slscolonpath="foo",
            sls_path="foo",
            slspath="foo",
        )

    def test_generate_sls_context__two_level_init_implicit(self):
        """generate_sls_context - Basic two level with implicit init.sls"""
        self._test_generated_sls_context(
            "/tmp/foo/bar/init.sls",
            "foo.bar",
            tplfile="foo/bar/init.sls",
            tpldir="foo/bar",
            tpldot="foo.bar",
            slsdotpath="foo.bar",
            slscolonpath="foo:bar",
            sls_path="foo_bar",
            slspath="foo/bar",
        )

    def test_generate_sls_context__two_level_init_explicit(self):
        """generate_sls_context - Basic two level with explicit init.sls"""
        self._test_generated_sls_context(
            "/tmp/foo/bar/init.sls",
            "foo.bar.init",
            tplfile="foo/bar/init.sls",
            tpldir="foo/bar",
            tpldot="foo.bar",
            slsdotpath="foo.bar",
            slscolonpath="foo:bar",
            sls_path="foo_bar",
            slspath="foo/bar",
        )

    def test_generate_sls_context__two_level(self):
        """generate_sls_context - Basic two level with name"""
        self._test_generated_sls_context(
            "/tmp/foo/bar/boo.sls",
            "foo.bar.boo",
            tplfile="foo/bar/boo.sls",
            tpldir="foo/bar",
            tpldot="foo.bar",
            slsdotpath="foo.bar",
            slscolonpath="foo:bar",
            sls_path="foo_bar",
            slspath="foo/bar",
        )

    def test_generate_sls_context__two_level_repeating(self):
        """generate_sls_context - Basic two level with name same as dir

        (Issue #56410)
        """
        self._test_generated_sls_context(
            "/tmp/foo/foo/foo.sls",
            "foo.foo.foo",
            tplfile="foo/foo/foo.sls",
            tpldir="foo/foo",
            tpldot="foo.foo",
            slsdotpath="foo.foo",
            slscolonpath="foo:foo",
            sls_path="foo_foo",
            slspath="foo/foo",
        )

    @pytest.mark.skip_on_windows
    def test_generate_sls_context__backslash_in_path(self):
        """generate_sls_context - Handle backslash in path on non-windows"""
        self._test_generated_sls_context(
            "/tmp/foo/foo\\foo.sls",
            "foo.foo\\foo",
            tplfile="foo/foo\\foo.sls",
            tpldir="foo",
            tpldot="foo",
            slsdotpath="foo",
            slscolonpath="foo",
            sls_path="foo",
            slspath="foo",
        )
