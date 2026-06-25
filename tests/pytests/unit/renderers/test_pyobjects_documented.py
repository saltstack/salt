"""
Render the pyobjects examples shown in the renderer documentation.

Covers issues:

- 61828: ``Module.run`` cannot accept a dotted function name as a literal
  keyword argument; the docs now show a ``**kwargs`` workaround that the
  test below renders end-to-end.
"""

import logging
from collections import OrderedDict

import pytest

import salt.renderers.pyobjects as pyobjects
from tests.support.mock import MagicMock

log = logging.getLogger(__name__)


@pytest.fixture()
def configure_loader_modules(minion_opts):
    minion_opts["file_client"] = "local"
    minion_opts["id"] = "doctest-minion"
    pillar = MagicMock(return_value={})
    return {
        pyobjects: {
            "__opts__": minion_opts,
            "__pillar__": pillar,
            "__salt__": {
                "config.get": MagicMock(),
                "grains.get": MagicMock(),
                "mine.get": MagicMock(),
                "pillar.get": MagicMock(),
            },
        },
    }


def _template(lines):
    class Template:
        def readlines():  # pylint: disable=no-method-argument
            return list(lines)

    return Template


@pytest.mark.slow_test
def test_documented_basic_file_managed():
    """
    Verbatim from the first pyobjects example.
    """
    template = _template(
        [
            "#!pyobjects",
            "File.managed('/tmp/foo', user='root', group='root', mode='1777')",
        ]
    )
    ret = pyobjects.render(template, sls="pyobj.basic")
    assert ret == OrderedDict(
        [
            (
                "/tmp/foo",
                {
                    "file.managed": [
                        {"group": "root"},
                        {"mode": "1777"},
                        {"user": "root"},
                    ]
                },
            )
        ]
    )


@pytest.mark.slow_test
def test_documented_module_run_kwargs_workaround():
    """
    The issue 61828 fix in the docs shows that calls of the form
    ``Module.run('name', shadow.lock_password=user)`` are a syntax error
    because keyword names cannot contain a dot.  The recommended fix is
    to pass a kwargs dictionary via ``**``.
    """
    template = _template(
        [
            "#!pyobjects",
            "kw = {'shadow.lock_password': ['susan']}",
            "Module.run('pyobject_shadow', **kw)",
        ]
    )
    ret = pyobjects.render(template, sls="pyobj.module_run")
    # The Registry serializes Module.run with the function name as a key.
    assert "pyobject_shadow" in ret
    state = ret["pyobject_shadow"]
    assert "module.run" in state
    flat = {
        k: v
        for entry in state["module.run"]
        if isinstance(entry, dict)
        for k, v in entry.items()
    }
    assert flat.get("shadow.lock_password") == ["susan"]
