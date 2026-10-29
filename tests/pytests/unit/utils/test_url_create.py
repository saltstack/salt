"""
Regression tests for salt.utils.url.create and Python 3.13+ compatibility.

Python 3.13 changed urllib.parse.urlunparse so that a relative path with the
``file`` scheme is rendered as ``file:path`` instead of the historical
``file:///path``. The legacy salt.utils.url.create implementation stripped a
literal ``file:///`` prefix; under the new behavior it silently chops the first
characters of the path, corrupting every ``salt://`` URL that salt-ssh builds
for state/file references.

See issue #68421 (duplicate of #66898).
"""

from urllib.parse import urlunparse as real_urlunparse

import pytest

import salt.utils.url


def _py313_urlunparse(components):
    """
    Emulate the Python 3.13+ urllib.parse.urlunparse behavior for relative
    paths with the ``file`` scheme.
    """
    scheme, netloc, path, params, query, fragment = components
    if scheme == "file" and not netloc and not path.startswith("/"):
        result = f"file:{path}"
        if params:
            result = f"{result};{params}"
        if query:
            result = f"{result}?{query}"
        if fragment:
            result = f"{result}#{fragment}"
        return result
    return real_urlunparse(components)


@pytest.fixture
def py313_urlunparse(monkeypatch):
    """
    Force ``salt.utils.url`` to see the Python 3.13+ behavior of
    ``urlunparse`` regardless of the interpreter running the test suite.
    """
    monkeypatch.setattr(salt.utils.url, "urlunparse", _py313_urlunparse)


def test_create_relative_path_python_3_13(py313_urlunparse):
    """
    ``salt.utils.url.create`` must round-trip a relative path under the
    Python 3.13+ ``urlunparse`` behavior. Regression test for #68421.
    """
    assert salt.utils.url.create("top.sls") == "salt://top.sls"


def test_create_relative_path_with_saltenv_python_3_13(py313_urlunparse):
    """
    ``salt.utils.url.create`` must keep the path intact when a saltenv is
    supplied under the Python 3.13+ ``urlunparse`` behavior. Regression test
    for #68421.
    """
    assert (
        salt.utils.url.create("test7.txt.jinja", "base")
        == "salt://test7.txt.jinja?saltenv=base"
    )


def test_create_nested_relative_path_python_3_13(py313_urlunparse):
    """
    Nested relative paths (the common salt-ssh ``file.managed`` source case)
    must survive the Python 3.13+ urlunparse change. Regression test for
    #68421.
    """
    assert (
        salt.utils.url.create("services/openssh/files/sshd_config.jj")
        == "salt://services/openssh/files/sshd_config.jj"
    )
