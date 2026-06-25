"""
Unit tests for the py() renderer and render_tmpl edge paths in
salt.utils.templates.
"""

import os

import pytest

import salt.utils.files
from salt.utils.templates import py as render_py_tmpl
from salt.utils.templates import wrap_tmpl_func


class EchoRender:
    """Minimal render_str callable that returns the template string unchanged."""

    def __call__(self, tplstr, context, tmplpath=None):
        self.tplstr = tplstr
        self.context = context
        self.tmplpath = tmplpath
        return tplstr


@pytest.fixture
def render_context():
    """Minimal context satisfying render_tmpl's opts/saltenv asserts."""
    return {"opts": {"cachedir": "/D", "__cli": "salt"}, "saltenv": "base"}


def _write_py_module(tmp_path, name, body):
    """Write a python template module to disk and return its path."""
    sfn = tmp_path / name
    sfn.write_text(body)
    return str(sfn)


def test_py_missing_file_returns_empty_dict(tmp_path):
    """py() returns an empty dict when the source file does not exist."""
    missing = str(tmp_path / "does_not_exist.py")
    assert render_py_tmpl(missing) == {}


def test_py_run_string_true_returns_data_directly(tmp_path):
    """py() with string=True returns run()'s value as data without writing a file."""
    sfn = _write_py_module(
        tmp_path, "tmpl_str.py", "def run():\n    return 'hello world'\n"
    )
    result = render_py_tmpl(sfn, string=True)
    assert result == {"result": True, "data": "hello world"}


def test_py_run_string_false_writes_tempfile(tmp_path):
    """py() with string=False writes run()'s output to a temp file and returns its path."""
    sfn = _write_py_module(
        tmp_path, "tmpl_file.py", "def run():\n    return 'file contents'\n"
    )
    result = render_py_tmpl(sfn, string=False)
    assert result["result"] is True
    written = result["data"]
    assert os.path.isfile(written)
    try:
        with salt.utils.files.fopen(written, encoding="utf-8") as fh:
            assert fh.read() == "file contents"
    finally:
        os.remove(written)


def test_py_run_default_string_false_writes_tempfile(tmp_path):
    """py() defaults to string=False, writing output to a temp file."""
    sfn = _write_py_module(
        tmp_path, "tmpl_default.py", "def run():\n    return 'default mode'\n"
    )
    result = render_py_tmpl(sfn)
    assert result["result"] is True
    written = result["data"]
    assert os.path.isfile(written)
    try:
        with salt.utils.files.fopen(written, encoding="utf-8") as fh:
            assert fh.read() == "default mode"
    finally:
        os.remove(written)


def test_py_run_uses_passed_kwargs_as_module_attrs(tmp_path):
    """py() sets passed kwargs as module attributes available to run()."""
    body = "def run():\n    return color + '-' + str(count)\n"
    sfn = _write_py_module(tmp_path, "tmpl_kwargs.py", body)
    result = render_py_tmpl(sfn, string=True, color="blue", count=3)
    assert result == {"result": True, "data": "blue-3"}


def test_py_run_sets_dunder_builtins_when_saltenv_present(tmp_path):
    """py() exposes saltenv/pillar/etc as __env__/__pillar__ dunders to run()."""
    body = "def run():\n    return __env__ + ':' + __pillar__['k']\n"
    sfn = _write_py_module(tmp_path, "tmpl_dunder.py", body)
    result = render_py_tmpl(
        sfn,
        string=True,
        saltenv="base",
        salt={},
        grains={},
        pillar={"k": "v"},
        opts={},
    )
    assert result == {"result": True, "data": "base:v"}


def test_py_run_raises_returns_failure_with_traceback(tmp_path):
    """py() catches exceptions raised in run() and returns result=False plus traceback."""
    sfn = _write_py_module(
        tmp_path, "tmpl_raise.py", "def run():\n    raise ValueError('boom')\n"
    )
    result = render_py_tmpl(sfn, string=True)
    assert result["result"] is False
    assert "ValueError" in result["data"]
    assert "boom" in result["data"]


def test_py_module_without_run_returns_failure(tmp_path):
    """py() returns a failure result when the module defines no run() function."""
    sfn = _write_py_module(tmp_path, "tmpl_norun.py", "x = 1\n")
    result = render_py_tmpl(sfn, string=True)
    assert result["result"] is False
    assert "AttributeError" in result["data"]


def test_render_tmpl_from_str_to_str(render_context):
    """render_tmpl renders an in-memory string and returns the rendered data."""
    wrapped = wrap_tmpl_func(EchoRender())
    res = wrapped("template body", from_str=True, to_str=True, context=render_context)
    assert res == {"result": True, "data": "template body"}


def test_render_tmpl_from_str_writes_file(render_context):
    """render_tmpl with to_str=False writes rendered output to a temp file."""
    wrapped = wrap_tmpl_func(EchoRender())
    res = wrapped("disk body", from_str=True, context=render_context)
    assert res["result"] is True
    written = res["data"]
    assert os.path.isfile(written)
    try:
        with salt.utils.files.fopen(written, encoding="utf-8") as fh:
            assert fh.read() == "disk body"
    finally:
        os.remove(written)


def test_render_tmpl_reads_file_path(tmp_path, render_context):
    """render_tmpl reads template content from a file path when from_str is False."""
    tplfile = tmp_path / "tmpl.txt"
    tplfile.write_text("from file")
    render = EchoRender()
    wrapped = wrap_tmpl_func(render)
    res = wrapped(str(tplfile), to_str=True, context=render_context)
    assert res == {"result": True, "data": "from file"}
    assert render.tplstr == "from file"


def test_render_tmpl_file_like_input(render_context):
    """render_tmpl reads and closes a file-like template source."""
    import io

    class ClosableStringIO(io.StringIO):
        closed_flag = False

        def close(self):
            type(self).closed_flag = True
            super().close()

    src = ClosableStringIO("from file-like")
    wrapped = wrap_tmpl_func(EchoRender())
    res = wrapped(src, to_str=True, context=render_context)
    assert res == {"result": True, "data": "from file-like"}
    assert ClosableStringIO.closed_flag is True


def test_render_tmpl_empty_template(render_context):
    """render_tmpl handles an empty template string, returning empty data."""
    wrapped = wrap_tmpl_func(EchoRender())
    res = wrapped("", from_str=True, to_str=True, context=render_context)
    assert res == {"result": True, "data": ""}


def test_render_tmpl_sls_context_merged(tmp_path):
    """render_tmpl merges generate_sls_context output into the render context."""
    slsfile = tmp_path / "foo" / "bar.sls"
    slsfile.parent.mkdir()
    slsfile.write_text("body")
    context = {"opts": {}, "saltenv": "base", "sls": "foo.bar"}
    render = EchoRender()
    wrapped = wrap_tmpl_func(render)
    res = wrapped(str(slsfile), to_str=True, context=context, tmplpath=str(slsfile))
    assert res["result"] is True
    # generate_sls_context computed values get merged into the context the
    # renderer sees.
    assert render.context["slspath"] == "foo"
    assert render.context["sls_path"] == "foo"
    assert render.context["tplfile"] == "foo/bar.sls"


def test_render_tmpl_explicit_context_overrides_kwargs(render_context):
    """render_tmpl lets explicit context overwrite values passed as **kws."""
    render = EchoRender()
    wrapped = wrap_tmpl_func(render)
    context = dict(render_context)
    context["shared"] = "from_context"
    res = wrapped(
        "body",
        from_str=True,
        to_str=True,
        context=context,
        shared="from_kws",
    )
    assert res["result"] is True
    assert render.context["shared"] == "from_context"


def test_render_tmpl_bytes_input_treated_as_file_like(render_context):
    """render_tmpl treats a non-str template source as file-like, raising on bytes."""
    wrapped = wrap_tmpl_func(EchoRender())
    # bytes is not a str, so render_tmpl falls into the file-like branch and
    # calls tmplsrc.read() before the try/except guard; plain bytes has no
    # .read(), so the AttributeError propagates out of render_tmpl.
    with pytest.raises(AttributeError):
        wrapped(b"raw bytes", from_str=False, to_str=True, context=render_context)


def test_render_tmpl_file_like_bytes_decoded_by_renderer(render_context):
    """render_tmpl reads a file-like source returning bytes and hands it to the renderer."""
    import io

    src = io.BytesIO(b"byte body")
    render = EchoRender()
    wrapped = wrap_tmpl_func(render)
    res = wrapped(src, from_str=False, to_str=True, context=render_context)
    # EchoRender returns the raw bytes it received; to_str path wraps it as data.
    assert res == {"result": True, "data": b"byte body"}
    assert render.tplstr == b"byte body"
