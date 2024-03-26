"""
Unit tests for salt.utils.templates.py
"""

import logging
from pathlib import PurePath, PurePosixPath

import pytest

from salt.utils.templates import wrap_tmpl_func, generate_sls_context
from tests.support.mock import patch


log = logging.getLogger(__name__)


class MockRender:
    def __call__(self, tplstr, context, tmplpath=None):
        self.tplstr = tplstr
        self.context = context
        self.tmplpath = tmplpath
        return tplstr


def _test_generated_sls_context(tmplpath, sls, **expected):
    """Generic SLS Context Test"""
    # DeNormalize tmplpath
    tmplpath = str(PurePath(PurePosixPath(tmplpath)))
    if tmplpath.startswith("\\"):
        tmplpath = f"C:{tmplpath}"
    expected["tplpath"] = tmplpath
    actual = generate_sls_context(tmplpath, sls)
    assert {key: actual[key] for key in expected if key in actual} == actual


def test_sls_context_call(tmp_path):
    """Check that generate_sls_context is called with proper parameters"""
    sls = "foo.bar"
    slsfile = tmp_path / "foo" / "bar.sls"
    slsfile.parent.mkdir()
    slsfile.write_text("{{ slspath }}")
    context = {"opts": {}, "saltenv": "base", "sls": sls}
    render = MockRender()
    with patch("salt.utils.templates.generate_sls_context") as generate_sls_context:
        wrapped = wrap_tmpl_func(render)
        res = wrapped(str(slsfile), context=context, tmplpath=str(slsfile))
        generate_sls_context.assert_called_with(str(slsfile), sls)


def test_sls_context_no_call(tmp_path):
    """Check that generate_sls_context is not called if sls is not set"""
    sls = "foo.bar"
    slsfile = tmp_path / "foo" / "bar.sls"
    slsfile.parent.mkdir()
    slsfile.write_text("{{ slspath }}")
    context = {"opts": {}, "saltenv": "base"}
    render = MockRender()
    with patch("salt.utils.templates.generate_sls_context") as generate_sls_context:
        wrapped = wrap_tmpl_func(render)
        res = wrapped(str(slsfile), context=context, tmplpath=str(slsfile))
        generate_sls_context.assert_not_called()


def test_generate_sls_context__top_level():
    """generate_sls_context - top_level Use case"""
    _test_generated_sls_context(
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


def test_generate_sls_context__one_level_init_implicit():
    """generate_sls_context - Basic one level with implicit init.sls"""
    _test_generated_sls_context(
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


def test_generate_sls_context__one_level_init_explicit():
    """generate_sls_context - Basic one level with explicit init.sls"""
    _test_generated_sls_context(
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


def test_generate_sls_context__one_level():
    """generate_sls_context - Basic one level with name"""
    _test_generated_sls_context(
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


def test_generate_sls_context__one_level_repeating():
    """generate_sls_context - Basic one level with name same as dir

    (Issue #56410)
    """
    _test_generated_sls_context(
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


def test_generate_sls_context__two_level_init_implicit():
    """generate_sls_context - Basic two level with implicit init.sls"""
    _test_generated_sls_context(
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


def test_generate_sls_context__two_level_init_explicit():
    """generate_sls_context - Basic two level with explicit init.sls"""
    _test_generated_sls_context(
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


def test_generate_sls_context__two_level():
    """generate_sls_context - Basic two level with name"""
    _test_generated_sls_context(
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


def test_generate_sls_context__two_level_repeating():
    """generate_sls_context - Basic two level with name same as dir

    (Issue #56410)
    """
    _test_generated_sls_context(
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
def test_generate_sls_context__backslash_in_path():
    """generate_sls_context - Handle backslash in path on non-windows"""
    _test_generated_sls_context(
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
