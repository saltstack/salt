"""
Render the pure-python (``#!py``) renderer examples shown in the
renderer documentation.

Covers issue 63698: the py renderer documentation needed real examples
demonstrating ``run()``, return-value structure, and access to dunders
(``__salt__``, ``__pillar__``, ``__grains__``).
"""

import textwrap

import pytest

import salt.renderers.py as py_renderer
from tests.support.mock import MagicMock


@pytest.fixture()
def configure_loader_modules(minion_opts):
    salt_dunder = {
        "test.echo": MagicMock(return_value="echoed"),
    }
    return {
        py_renderer: {
            "__opts__": minion_opts,
            "__salt__": salt_dunder,
            "__pillar__": {"apache": "httpd"},
            "__grains__": {"os_family": "RedHat"},
        },
    }


def _write_template(tmp_path, body):
    path = tmp_path / "tmpl.py"
    path.write_text(textwrap.dedent(body))
    return str(path)


@pytest.mark.slow_test
def test_documented_basic_state(tmp_path):
    """
    The simplest documented example: a ``run()`` function that returns
    a highstate dictionary.
    """
    tmplpath = _write_template(
        tmp_path,
        """\
        def run():
            return {
                'common_packages': {
                    'pkg.installed': [
                        {'pkgs': ['curl', 'vim']},
                    ],
                },
            }
        """,
    )
    # The py renderer ignores ``template`` and reads ``tmplpath``.
    ret = py_renderer.render(template=None, tmplpath=tmplpath)
    assert ret == {
        "common_packages": {
            "pkg.installed": [{"pkgs": ["curl", "vim"]}],
        },
    }


@pytest.mark.slow_test
def test_documented_pillar_and_grains_dunders(tmp_path):
    """
    The docs claim that ``__pillar__`` and ``__grains__`` are exposed
    inside the python template.  Make sure both work.
    """
    tmplpath = _write_template(
        tmp_path,
        """\
        def run():
            return {
                'install_apache': {
                    'pkg.installed': [
                        {'name': __pillar__['apache']},
                    ],
                },
                'tag_os_family': {
                    'cmd.run': [
                        {'name': 'echo ' + __grains__['os_family']},
                    ],
                },
            }
        """,
    )
    ret = py_renderer.render(template=None, tmplpath=tmplpath)
    assert ret["install_apache"]["pkg.installed"][0]["name"] == "httpd"
    assert ret["tag_os_family"]["cmd.run"][0]["name"] == "echo RedHat"


@pytest.mark.slow_test
def test_documented_salt_function_call(tmp_path):
    """
    The docs example calls ``__salt__['test.echo']`` from inside ``run()``.
    """
    tmplpath = _write_template(
        tmp_path,
        """\
        def run():
            value = __salt__['test.echo']('hello')
            return {
                'announce': {
                    'cmd.run': [
                        {'name': 'echo ' + value},
                    ],
                },
            }
        """,
    )
    ret = py_renderer.render(template=None, tmplpath=tmplpath)
    assert ret["announce"]["cmd.run"][0]["name"] == "echo echoed"
