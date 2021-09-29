"""
Tests for salt.utils.jinja
"""

import copy
import os
import tempfile

import pytest
import salt.config
import salt.loader

# dateutils is needed so that the strftime jinja filter is loaded
import salt.utils.dateutils  # pylint: disable=unused-import
import salt.utils.files
import salt.utils.json
import salt.utils.stringutils
import salt.utils.yaml
from jinja2 import Environment, exceptions
from salt.utils.jinja import SaltCacheLoader
from tests.support.mock import Mock, patch

try:
    import timelib  # pylint: disable=W0611

    HAS_TIMELIB = True
except ImportError:
    HAS_TIMELIB = False

BLINESEP = salt.utils.stringutils.to_bytes(os.linesep)


@pytest.fixture
def minion_opts(tmpdir):
    _opts = salt.config.DEFAULT_MINION_OPTS.copy()
    _opts.update(
        {
            "file_buffer_size": 1048576,
            "cachedir": tmpdir,
            "file_roots": {"test": [tmpdir.join("templates").strpath]},
            "pillar_roots": {"test": [tmpdir.join("templates").strpath]},
            "extension_modules": os.path.join(
                os.path.dirname(os.path.abspath(__file__)), "extmods"
            ),
        }
    )
    return _opts


@pytest.fixture
def template_dir(tmpdir):
    templates_dir = tmpdir.mkdir("templates").mkdir("files").mkdir("test")
    return str(templates_dir)


@pytest.fixture
def get_loader(mock_file_client, minion_opts):
    def run_command(opts=None, saltenv="base", **kwargs):
        """
        Now that we instantiate the client in the __init__, we need to mock it
        """
        if opts is None:
            opts = minion_opts
        with patch.object(SaltCacheLoader, "file_client", mock_file_client):
            loader = SaltCacheLoader(opts, saltenv)
        # Create a mock file client and attach it to the loader
        return loader

    return run_command


def get_test_saltenv(get_loader):
    """
    Setup a simple jinja test environment
    """
    loader = get_loader(saltenv="test")
    jinja = Environment(loader=loader)
    return loader._file_client, jinja


def test_searchpath(minion_opts, get_loader):
    """
    The searchpath is based on the cachedir option and the saltenv parameter
    """
    tmp = tempfile.gettempdir()
    opts = copy.deepcopy(minion_opts)
    opts.update({"cachedir": tmp})
    loader = get_loader(opts=minion_opts, saltenv="test")
    assert loader.searchpath == [os.path.join(tmp, "files", "test")]


def test_mockclient(minion_opts, template_dir, get_loader):
    """
    A MockFileClient is used that records all file requests normally sent
    to the master.
    """
    loader = get_loader(opts=minion_opts, saltenv="test")
    res = loader.get_source(None, "hello_simple")
    assert len(res) == 3
    # res[0] on Windows is unicode and use os.linesep so it works cross OS
    assert str(res[0]) == "world" + os.linesep
    tmpl_dir = os.path.join(template_dir, "hello_simple")
    assert res[1] == tmpl_dir
    assert res[2](), "Template up to date?"
    assert loader._file_client.requests
    assert loader._file_client.requests[0]["path"] == "salt://hello_simple"


def test_import(get_loader):
    """
    You can import and use macros from other files
    """
    fc, jinja = get_test_saltenv(get_loader)
    result = jinja.get_template("hello_import").render()
    assert result == "Hey world !a b !"
    assert len(fc.requests) == 2
    assert fc.requests[0]["path"] == "salt://hello_import"
    assert fc.requests[1]["path"] == "salt://macro"


def test_relative_import(get_loader):
    """
    You can import using relative paths
    issue-13889
    """
    fc, jinja = get_test_saltenv(get_loader)
    tmpl = jinja.get_template(os.path.join("relative", "rhello"))
    result = tmpl.render()
    assert result == "Hey world !a b !"
    assert len(fc.requests) == 3
    assert fc.requests[0]["path"] == os.path.join("salt://relative", "rhello")
    assert fc.requests[1]["path"] == os.path.join("salt://relative", "rmacro")
    assert fc.requests[2]["path"] == "salt://macro"
    # This must fail when rendered: attempts to import from outside file root
    template = jinja.get_template("relative/rescape")
    pytest.raises(exceptions.TemplateNotFound, template.render)


def test_include(get_loader):
    """
    You can also include a template that imports and uses macros
    """
    fc, jinja = get_test_saltenv(get_loader)
    result = jinja.get_template("hello_include").render()
    assert result == "Hey world !a b !"
    assert len(fc.requests) == 3
    assert fc.requests[0]["path"] == "salt://hello_include"
    assert fc.requests[1]["path"] == "salt://hello_import"
    assert fc.requests[2]["path"] == "salt://macro"


def test_include_context(get_loader):
    """
    Context variables are passes to the included template by default.
    """
    _, jinja = get_test_saltenv(get_loader)
    result = jinja.get_template("hello_include").render(a="Hi", b="Salt")
    assert result == "Hey world !Hi Salt !"


def test_cached_file_client(get_loader, minion_opts):
    """
    Multiple instantiations of SaltCacheLoader use the cached file client
    """
    with patch("salt.transport.client.ReqChannel.factory", Mock()):
        loader_a = SaltCacheLoader(minion_opts)
        loader_b = SaltCacheLoader(minion_opts)
    assert loader_a._file_client is loader_b._file_client


def test_file_client_kwarg(mock_file_client):
    """
    A file client can be passed to SaltCacheLoader overriding the any
    cached file client
    """
    loader = SaltCacheLoader(minion_opts, _file_client=mock_file_client)
    assert loader._file_client is mock_file_client


def test_cache_loader_shutdown(mock_file_client):
    """
    The shudown method can be called without raising an exception when the
    file_client does not have a destroy method
    """
    assert not hasattr(mock_file_client, "destroy")
    loader = SaltCacheLoader(minion_opts, _file_client=mock_file_client)
    assert loader._file_client is mock_file_client
    # Shutdown method should not raise any exceptions
    loader.shutdown()
