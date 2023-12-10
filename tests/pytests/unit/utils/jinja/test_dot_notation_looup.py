"""
Tests for salt.utils.jinja
"""

import salt.loader

# dateutils is needed so that the strftime jinja filter is loaded
import salt.utils.dateutils  # pylint: disable=unused-import
import salt.utils.files
import salt.utils.json
import salt.utils.stringutils
import salt.utils.yaml
from salt.utils.jinja import SaltCacheLoader
from tests.support.mock import Mock, patch


def render(tmpl_str, minion_opts, context=None):
    functions = {
        "mocktest.ping": lambda: True,
        "mockgrains.get": lambda x: "jerry",
    }

    _render = salt.loader.render(minion_opts, functions)

    jinja = _render.get("jinja")

    return jinja(tmpl_str, context=context or {}, argline="-s").read()


def test_normlookup(minion_opts):
    """
    Sanity-check the normal dictionary-lookup syntax for our stub function
    """
    tmpl_str = """Hello, {{ salt['mocktest.ping']() }}."""

    with patch.object(SaltCacheLoader, "file_client", Mock()):
        ret = render(tmpl_str, minion_opts)
    assert ret == "Hello, True."


def test_dotlookup(minion_opts):
    """
    Check calling a stub function using awesome dot-notation
    """
    tmpl_str = """Hello, {{ salt.mocktest.ping() }}."""

    with patch.object(SaltCacheLoader, "file_client", Mock()):
        ret = render(tmpl_str, minion_opts)
    assert ret == "Hello, True."


def test_shadowed_dict_method(minion_opts):
    """
    Check calling a stub function with a name that shadows a ``dict``
    method name
    """
    tmpl_str = """Hello, {{ salt.mockgrains.get('id') }}."""

    with patch.object(SaltCacheLoader, "file_client", Mock()):
        ret = render(tmpl_str, minion_opts)
    assert ret == "Hello, jerry."
