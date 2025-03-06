import codecs
import glob
import logging
import os
import textwrap

import pytest

import salt.loader
import salt.template
import salt.utils.data
import salt.utils.files
import salt.utils.reactor as reactor
import salt.utils.yaml
from tests.support.mock import MagicMock, Mock, mock_open, patch

log = logging.getLogger(__name__)

REACTOR_CONFIG = """\
reactor:
  - old_runner:
    - /srv/reactor/old_runner.sls
  - old_wheel:
    - /srv/reactor/old_wheel.sls
  - old_local:
    - /srv/reactor/old_local.sls
  - old_cmd:
    - /srv/reactor/old_cmd.sls
  - old_caller:
    - /srv/reactor/old_caller.sls
  - new_runner:
    - /srv/reactor/new_runner.sls
  - new_wheel:
    - /srv/reactor/new_wheel.sls
  - new_local:
    - /srv/reactor/new_local.sls
  - new_cmd:
    - /srv/reactor/new_cmd.sls
  - new_caller:
    - /srv/reactor/new_caller.sls
"""

REACTOR_DATA = {
    "runner": {"data": {"message": "This is an error"}},
    "wheel": {"data": {"id": "foo"}},
    "local": {"data": {"pkg": "zsh", "repo": "updates"}},
    "cmd": {"data": {"pkg": "zsh", "repo": "updates"}},
    "caller": {"data": {"path": "/tmp/foo"}},
}

SLS = {
    "/srv/reactor/old_runner.sls": textwrap.dedent(
        """\
        raise_error:
          runner.error.error:
            - name: Exception
            - message: {{ data['data']['message'] }}
        """
    ),
    "/srv/reactor/old_wheel.sls": textwrap.dedent(
        """\
        remove_key:
          wheel.key.delete:
            - match: {{ data['data']['id'] }}
        """
    ),
    "/srv/reactor/old_local.sls": textwrap.dedent(
        """\
        install_zsh:
          local.state.single:
            - tgt: test
            - arg:
              - pkg.installed
              - {{ data['data']['pkg'] }}
            - kwarg:
                fromrepo: {{ data['data']['repo'] }}
        """
    ),
    "/srv/reactor/old_cmd.sls": textwrap.dedent(
        """\
        install_zsh:
          cmd.state.single:
            - tgt: test
            - arg:
              - pkg.installed
              - {{ data['data']['pkg'] }}
            - kwarg:
                fromrepo: {{ data['data']['repo'] }}
        """
    ),
    "/srv/reactor/old_caller.sls": textwrap.dedent(
        """\
        touch_file:
          caller.file.touch:
            - args:
              - {{ data['data']['path'] }}
        """
    ),
    "/srv/reactor/new_runner.sls": textwrap.dedent(
        """\
        raise_error:
          runner.error.error:
            - args:
              - name: Exception
              - message: {{ data['data']['message'] }}
        """
    ),
    "/srv/reactor/new_wheel.sls": textwrap.dedent(
        """\
        remove_key:
          wheel.key.delete:
            - args:
              - match: {{ data['data']['id'] }}
        """
    ),
    "/srv/reactor/new_local.sls": textwrap.dedent(
        """\
        install_zsh:
          local.state.single:
            - tgt: test
            - args:
              - fun: pkg.installed
              - name: {{ data['data']['pkg'] }}
              - fromrepo: {{ data['data']['repo'] }}
        """
    ),
    "/srv/reactor/new_cmd.sls": textwrap.dedent(
        """\
        install_zsh:
          cmd.state.single:
            - tgt: test
            - args:
              - fun: pkg.installed
              - name: {{ data['data']['pkg'] }}
              - fromrepo: {{ data['data']['repo'] }}
        """
    ),
    "/srv/reactor/new_caller.sls": textwrap.dedent(
        """\
        touch_file:
          caller.file.touch:
            - args:
              - name: {{ data['data']['path'] }}
        """
    ),
}

LOW_CHUNKS = {
    "old_runner": [
        {
            "state": "runner",
            "__id__": "raise_error",
            "__sls__": "/srv/reactor/old_runner.sls",
            "order": 1,
            "fun": "error.error",
            "name": "Exception",
            "message": "This is an error",
        }
    ],
    "old_wheel": [
        {
            "state": "wheel",
            "__id__": "remove_key",
            "name": "remove_key",
            "__sls__": "/srv/reactor/old_wheel.sls",
            "order": 1,
            "fun": "key.delete",
            "match": "foo",
        }
    ],
    "old_local": [
        {
            "state": "local",
            "__id__": "install_zsh",
            "name": "install_zsh",
            "__sls__": "/srv/reactor/old_local.sls",
            "order": 1,
            "tgt": "test",
            "fun": "state.single",
            "arg": ["pkg.installed", "zsh"],
            "kwarg": {"fromrepo": "updates"},
        }
    ],
    "old_cmd": [
        {
            "state": "local",
            "__id__": "install_zsh",
            "name": "install_zsh",
            "__sls__": "/srv/reactor/old_cmd.sls",
            "order": 1,
            "tgt": "test",
            "fun": "state.single",
            "arg": ["pkg.installed", "zsh"],
            "kwarg": {"fromrepo": "updates"},
        }
    ],
    "old_caller": [
        {
            "state": "caller",
            "__id__": "touch_file",
            "name": "touch_file",
            "__sls__": "/srv/reactor/old_caller.sls",
            "order": 1,
            "fun": "file.touch",
            "args": ["/tmp/foo"],
        }
    ],
    "new_runner": [
        {
            "state": "runner",
            "__id__": "raise_error",
            "name": "raise_error",
            "__sls__": "/srv/reactor/new_runner.sls",
            "order": 1,
            "fun": "error.error",
            "args": [{"name": "Exception"}, {"message": "This is an error"}],
        }
    ],
    "new_wheel": [
        {
            "state": "wheel",
            "__id__": "remove_key",
            "name": "remove_key",
            "__sls__": "/srv/reactor/new_wheel.sls",
            "order": 1,
            "fun": "key.delete",
            "args": [{"match": "foo"}],
        }
    ],
    "new_local": [
        {
            "state": "local",
            "__id__": "install_zsh",
            "name": "install_zsh",
            "__sls__": "/srv/reactor/new_local.sls",
            "order": 1,
            "tgt": "test",
            "fun": "state.single",
            "args": [
                {"fun": "pkg.installed"},
                {"name": "zsh"},
                {"fromrepo": "updates"},
            ],
        }
    ],
    "new_cmd": [
        {
            "state": "local",
            "__id__": "install_zsh",
            "name": "install_zsh",
            "__sls__": "/srv/reactor/new_cmd.sls",
            "order": 1,
            "tgt": "test",
            "fun": "state.single",
            "args": [
                {"fun": "pkg.installed"},
                {"name": "zsh"},
                {"fromrepo": "updates"},
            ],
        }
    ],
    "new_caller": [
        {
            "state": "caller",
            "__id__": "touch_file",
            "name": "touch_file",
            "__sls__": "/srv/reactor/new_caller.sls",
            "order": 1,
            "fun": "file.touch",
            "args": [{"name": "/tmp/foo"}],
        }
    ],
}

WRAPPER_CALLS = {
    "old_runner": (
        "error.error",
        {
            "__state__": "runner",
            "__id__": "raise_error",
            "__sls__": "/srv/reactor/old_runner.sls",
            "__user__": "Reactor",
            "order": 1,
            "arg": [],
            "kwarg": {"name": "Exception", "message": "This is an error"},
            "name": "Exception",
            "message": "This is an error",
        },
    ),
    "old_wheel": (
        "key.delete",
        {
            "__state__": "wheel",
            "__id__": "remove_key",
            "name": "remove_key",
            "__sls__": "/srv/reactor/old_wheel.sls",
            "order": 1,
            "__user__": "Reactor",
            "arg": ["foo"],
            "kwarg": {},
            "match": "foo",
        },
    ),
    "old_local": {
        "args": ("test", "state.single"),
        "kwargs": {
            "state": "local",
            "__id__": "install_zsh",
            "name": "install_zsh",
            "__sls__": "/srv/reactor/old_local.sls",
            "order": 1,
            "arg": ["pkg.installed", "zsh"],
            "kwarg": {"fromrepo": "updates"},
        },
    },
    "old_cmd": {
        "args": ("test", "state.single"),
        "kwargs": {
            "state": "local",
            "__id__": "install_zsh",
            "name": "install_zsh",
            "__sls__": "/srv/reactor/old_cmd.sls",
            "order": 1,
            "arg": ["pkg.installed", "zsh"],
            "kwarg": {"fromrepo": "updates"},
        },
    },
    "old_caller": {"args": ("file.touch", "/tmp/foo"), "kwargs": {}},
    "new_runner": (
        "error.error",
        {
            "__state__": "runner",
            "__id__": "raise_error",
            "name": "raise_error",
            "__sls__": "/srv/reactor/new_runner.sls",
            "__user__": "Reactor",
            "order": 1,
            "arg": (),
            "kwarg": {"name": "Exception", "message": "This is an error"},
        },
    ),
    "new_wheel": (
        "key.delete",
        {
            "__state__": "wheel",
            "__id__": "remove_key",
            "name": "remove_key",
            "__sls__": "/srv/reactor/new_wheel.sls",
            "order": 1,
            "__user__": "Reactor",
            "arg": (),
            "kwarg": {"match": "foo"},
        },
    ),
    "new_local": {
        "args": ("test", "state.single"),
        "kwargs": {
            "state": "local",
            "__id__": "install_zsh",
            "name": "install_zsh",
            "__sls__": "/srv/reactor/new_local.sls",
            "order": 1,
            "arg": (),
            "kwarg": {"fun": "pkg.installed", "name": "zsh", "fromrepo": "updates"},
        },
    },
    "new_cmd": {
        "args": ("test", "state.single"),
        "kwargs": {
            "state": "local",
            "__id__": "install_zsh",
            "name": "install_zsh",
            "__sls__": "/srv/reactor/new_cmd.sls",
            "order": 1,
            "arg": (),
            "kwarg": {"fun": "pkg.installed", "name": "zsh", "fromrepo": "updates"},
        },
    },
    "new_caller": {"args": ("file.touch",), "kwargs": {"name": "/tmp/foo"}},
}


# -----------------------------------------------------------------------------
# FIXTURES
# -----------------------------------------------------------------------------
@pytest.fixture
def react_master_opts(master_opts):
    opts = {
        # Minimal stand-in for a real master config
        "file_roots": {"base": []},
        "renderer": "jinja|yaml",
    }
    master_opts.update(opts)
    # Optionally parse the reactor config for convenience
    reactor_config = salt.utils.yaml.safe_load(REACTOR_CONFIG)
    master_opts.update(reactor_config)
    return master_opts


@pytest.fixture
def test_reactor(react_master_opts):
    """
    Create a Reactor instance for testing
    """
    return reactor.Reactor(react_master_opts)


@pytest.fixture
def reaction_map(react_master_opts):
    """
    Reaction map from the configured reactor
    """
    return salt.utils.data.repack_dictlist(react_master_opts["reactor"])


@pytest.fixture
def render_pipe(react_master_opts):
    """
    Render pipeline
    """
    renderers = salt.loader.render(react_master_opts, {})
    return [(renderers[x], "") for x in ("jinja", "yaml")]


# -----------------------------------------------------------------------------
# TESTS for Reactor building the low chunks
# -----------------------------------------------------------------------------
@pytest.mark.parametrize("schema", ["old", "new"])
@pytest.mark.parametrize("rtype", list(REACTOR_DATA.keys()))
def test_reactor_reactions(schema, rtype, test_reactor, render_pipe):
    """
    Ensure correct reactions are built from the configured SLS files and tag data.
    """
    tag = f"{schema}_{rtype}"
    reactors_list = test_reactor.list_reactors(tag)

    # Patch out globbing since these SLS files don't actually exist on disk
    with patch.object(glob, "glob", MagicMock(side_effect=lambda x: [x])):
        with patch.object(os.path, "isfile", MagicMock(return_value=True)):
            with patch.object(
                salt.utils.files, "is_empty", MagicMock(return_value=False)
            ):
                with patch.object(
                    codecs, "open", mock_open(read_data=SLS[reactors_list[0]])
                ):
                    with patch.object(
                        salt.template,
                        "template_shebang",
                        MagicMock(return_value=render_pipe),
                    ):
                        reactions = test_reactor.reactions(
                            tag, REACTOR_DATA[rtype], reactors_list
                        )
    assert reactions == LOW_CHUNKS[tag], f"Reactions did not match for tag: {tag}"


def test_list_reactors(test_reactor, reaction_map):
    """
    Ensure list_reactors() returns the correct list of reactor SLS files for each tag.
    """
    for schema in ("old", "new"):
        for rtype in REACTOR_DATA:
            tag = f"{schema}_{rtype}"
            assert test_reactor.list_reactors(tag) == reaction_map[tag]


# -----------------------------------------------------------------------------
# FIXTURE for Reactor Wrap
# -----------------------------------------------------------------------------
@pytest.fixture
def react_wrap(react_master_opts):
    """
    Create a ReactWrap instance
    """
    return reactor.ReactWrap(react_master_opts)


# -----------------------------------------------------------------------------
# TESTS for ReactWrap
# -----------------------------------------------------------------------------
@pytest.mark.parametrize("schema", ["old", "new"])
def test_runner(schema, react_wrap):
    """
    Test runner reactions using both the old and new config schema
    """
    tag = f"{schema}_runner"
    chunk = LOW_CHUNKS[tag][0]
    thread_pool = Mock()
    thread_pool.fire_async = Mock()
    with patch.object(react_wrap, "pool", thread_pool):
        react_wrap.run(chunk)
    thread_pool.fire_async.assert_called_with(
        react_wrap.client_cache["runner"].low,
        args=WRAPPER_CALLS[tag],
    )


@pytest.mark.parametrize("schema", ["old", "new"])
def test_wheel(schema, react_wrap):
    """
    Test wheel reactions using both the old and new config schema
    """
    tag = f"{schema}_wheel"
    chunk = LOW_CHUNKS[tag][0]
    thread_pool = Mock()
    thread_pool.fire_async = Mock()
    with patch.object(react_wrap, "pool", thread_pool):
        react_wrap.run(chunk)
    thread_pool.fire_async.assert_called_with(
        react_wrap.client_cache["wheel"].low,
        args=WRAPPER_CALLS[tag],
    )


@pytest.mark.parametrize("schema", ["old", "new"])
def test_local(schema, react_wrap):
    """
    Test local reactions using both the old and new config schema
    """
    tag = f"{schema}_local"
    chunk = LOW_CHUNKS[tag][0]
    client_cache = {"local": Mock()}
    client_cache["local"].cmd_async = Mock()
    with patch.object(react_wrap, "client_cache", client_cache):
        react_wrap.run(chunk)
    client_cache["local"].cmd_async.assert_called_with(
        *WRAPPER_CALLS[tag]["args"], **WRAPPER_CALLS[tag]["kwargs"]
    )


@pytest.mark.parametrize("schema", ["old", "new"])
def test_cmd(schema, react_wrap):
    """
    Test cmd reactions (alias for 'local') using both the old and new config schema
    """
    tag = f"{schema}_cmd"
    chunk = LOW_CHUNKS[tag][0]
    client_cache = {"local": Mock()}
    client_cache["local"].cmd_async = Mock()
    with patch.object(react_wrap, "client_cache", client_cache):
        react_wrap.run(chunk)
    client_cache["local"].cmd_async.assert_called_with(
        *WRAPPER_CALLS[tag]["args"], **WRAPPER_CALLS[tag]["kwargs"]
    )


@pytest.mark.parametrize("schema", ["old", "new"])
def test_caller(schema, react_wrap):
    """
    Test caller reactions using both the old and new config schema
    """
    tag = f"{schema}_caller"
    chunk = LOW_CHUNKS[tag][0]
    client_cache = {"caller": Mock()}
    client_cache["caller"].cmd = Mock()
    with patch.object(react_wrap, "client_cache", client_cache):
        react_wrap.run(chunk)
    client_cache["caller"].cmd.assert_called_with(
        *WRAPPER_CALLS[tag]["args"], **WRAPPER_CALLS[tag]["kwargs"]
    )


@pytest.mark.parametrize("file_client", ["runner", "wheel"])
def test_client_cache_missing_key(file_client, react_wrap):
    """
    Test client_cache file_client missing, gets repopulated
    """
    client_cache = {}
    tag = f"new_{file_client}"
    chunk = LOW_CHUNKS[tag][0]
    with patch.object(react_wrap, "client_cache", client_cache):
        if f"{file_client}" == "runner":
            react_wrap.runner(chunk)
        elif f"{file_client}" == "wheel":
            react_wrap.wheel(chunk)
        else:
            # catch need for new check
            assert f"{file_client}" == "bad parameterization"

        file_client_key = None
        for key in react_wrap.client_cache.keys():
            if key == f"{file_client}":
                file_client_key = key

        assert file_client_key == f"{file_client}"
