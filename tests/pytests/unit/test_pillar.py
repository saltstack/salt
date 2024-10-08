"""
    :codeauthor: Pedro Algarvio (pedro@algarvio.me)
    :codeauthor: Alexandru Bleotu (alexandru.bleotu@morganstanley.com)

    tests.unit.pillar_test
    ~~~~~~~~~~~~~~~~~~~~~~
"""

import logging
import os
import shutil
import tempfile
import textwrap

import pytest

import salt.config
import salt.exceptions
import salt.fileclient
import salt.utils.stringutils
from salt.utils.files import fopen
from tests.support.mock import MagicMock, patch
from tests.support.runtests import RUNTIME_VARS

log = logging.getLogger(__name__)


@pytest.fixture
def grains():
    return {}


@pytest.fixture
def tmp_pki(tmp_path):
    return str(tmp_path)


class MockFileclient:
    def __init__(self, cache_file=None, get_state=None, list_states=None):
        if cache_file is not None:
            self.cache_file = lambda *x, **y: cache_file
        if get_state is not None:
            self.get_state = lambda sls, env: get_state[sls]
        if list_states is not None:
            self.list_states = lambda *x, **y: list_states

    # pylint: disable=unused-argument,no-method-argument,method-hidden
    def cache_file(self, *args, **kwargs):
        raise NotImplementedError()

    def get_state(self, *args, **kwargs):
        raise NotImplementedError()

    def list_states(self, *args, **kwargs):
        raise NotImplementedError()

    # pylint: enable=unused-argument,no-method-argument,method-hidden


def _setup_test_topfile_sls_pillar_match(tmp_path):
    # Write a simple topfile and two pillar state files
    top_file = tempfile.NamedTemporaryFile(dir=str(tmp_path), delete=False)
    s = """
base:
  'phase:alpha':
    - match: pillar
    - generic
"""
    top_file.write(salt.utils.stringutils.to_bytes(s))
    top_file.flush()
    generic_file = tempfile.NamedTemporaryFile(dir=str(tmp_path), delete=False)
    generic_file.write(
        b"""
generic:
  key1: value1
"""
    )
    generic_file.flush()
    return {
        "top": {"path": "", "dest": top_file.name},
        "generic": {"path": "", "dest": generic_file.name},
    }


def test_pillarenv_from_saltenv():
    with patch("salt.pillar.compile_template") as compile_template:
        opts = {
            "optimization_order": [0, 1, 2],
            "renderer": "json",
            "renderer_blacklist": [],
            "renderer_whitelist": [],
            "state_top": "",
            "pillar_roots": {"dev": [], "base": []},
            "file_roots": {"dev": [], "base": []},
            "extension_modules": "",
            "pillarenv_from_saltenv": True,
            "fileserver_backend": "",
            "cachedir": "",
        }
        grains = {
            "os": "Ubuntu",
        }
        pillar = salt.pillar.Pillar(opts, grains, "mocked-minion", "dev")
        assert pillar.opts["saltenv"] == "dev"
        assert pillar.opts["pillarenv"] == "dev"


def _setup_test_topfile_sls(tmp_path, nodegroup_order, glob_order):
    # Write a simple topfile and two pillar state files
    top_file = tempfile.NamedTemporaryFile(dir=str(tmp_path), delete=False)
    s = """
base:
  group:
    - match: nodegroup
    - order: {nodegroup_order}
    - ssh
    - generic
  '*':
    - generic
  minion:
    - order: {glob_order}
    - ssh.minion
    - generic.minion
""".format(
        nodegroup_order=nodegroup_order, glob_order=glob_order
    )
    top_file.write(salt.utils.stringutils.to_bytes(s))
    top_file.flush()
    ssh_file = tempfile.NamedTemporaryFile(dir=str(tmp_path), delete=False)
    ssh_file.write(
        b"""
ssh:
  foo
"""
    )
    ssh_file.flush()
    ssh_minion_file = tempfile.NamedTemporaryFile(dir=str(tmp_path), delete=False)
    ssh_minion_file.write(
        b"""
ssh:
  bar
"""
    )
    ssh_minion_file.flush()
    generic_file = tempfile.NamedTemporaryFile(dir=str(tmp_path), delete=False)
    generic_file.write(
        b"""
generic:
  key1:
    - value1
    - value2
  key2:
    sub_key1: []
"""
    )
    generic_file.flush()
    generic_minion_file = tempfile.NamedTemporaryFile(dir=str(tmp_path), delete=False)
    generic_minion_file.write(
        b"""
generic:
  key1:
    - value3
  key2:
    sub_key2: []
"""
    )
    generic_minion_file.flush()

    return {
        "top": {"path": "", "dest": top_file.name},
        "ssh": {"path": "", "dest": ssh_file.name},
        "ssh.minion": {"path": "", "dest": ssh_minion_file.name},
        "generic": {"path": "", "dest": generic_file.name},
        "generic.minion": {"path": "", "dest": generic_minion_file.name},
    }


def _setup_test_include_sls(tempdir):
    top_file = tempfile.NamedTemporaryFile(dir=tempdir, delete=False)
    top_file.write(
        b"""
base:
  '*':
    - order: 1
    - test.sub2
  minion:
   - order: 2
   - test
"""
    )
    top_file.flush()
    init_sls = tempfile.NamedTemporaryFile(dir=tempdir, delete=False)
    init_sls.write(
        b"""
include:
  - test.sub1
  - test.sub_wildcard*
  - .test.sub_with_init_dot
  - test/sub/with/slashes
"""
    )
    init_sls.flush()
    sub1_sls = tempfile.NamedTemporaryFile(dir=tempdir, delete=False)
    sub1_sls.write(
        b"""
foo1:
  bar1
"""
    )
    sub1_sls.flush()
    sub2_sls = tempfile.NamedTemporaryFile(dir=tempdir, delete=False)
    sub2_sls.write(
        b"""
foo2:
  bar2
"""
    )
    sub2_sls.flush()

    sub_wildcard_1_sls = tempfile.NamedTemporaryFile(dir=tempdir, delete=False)
    sub_wildcard_1_sls.write(
        b"""
foo_wildcard:
  bar_wildcard
"""
    )
    sub_wildcard_1_sls.flush()

    sub_with_init_dot_sls = tempfile.NamedTemporaryFile(dir=tempdir, delete=False)
    sub_with_init_dot_sls.write(
        b"""
sub_init_dot:
  sub_with_init_dot_worked
"""
    )
    sub_with_init_dot_sls.flush()

    sub_with_slashes_sls = tempfile.NamedTemporaryFile(dir=tempdir, delete=False)
    sub_with_slashes_sls.write(
        b"""
sub_with_slashes:
  sub_slashes_worked
"""
    )
    sub_with_slashes_sls.flush()

    return {
        "top": {"path": "", "dest": top_file.name},
        "test": {"path": "", "dest": init_sls.name},
        "test.sub1": {"path": "", "dest": sub1_sls.name},
        "test.sub2": {"path": "", "dest": sub2_sls.name},
        "test.sub_wildcard_1": {"path": "", "dest": sub_wildcard_1_sls.name},
        "test.sub_with_init_dot": {"path": "", "dest": sub_with_init_dot_sls.name},
        "test.sub.with.slashes": {"path": "", "dest": sub_with_slashes_sls.name},
    }


def test_ext_pillar_no_extra_minion_data_val_dict():
    opts = {
        "optimization_order": [0, 1, 2],
        "renderer": "json",
        "renderer_blacklist": [],
        "renderer_whitelist": [],
        "state_top": "",
        "pillar_roots": {"dev": [], "base": []},
        "file_roots": {"dev": [], "base": []},
        "extension_modules": "",
        "pillarenv_from_saltenv": True,
        "fileserver_backend": "",
        "cachedir": "",
    }
    mock_ext_pillar_func = MagicMock()
    with patch(
        "salt.loader.pillars",
        MagicMock(return_value={"fake_ext_pillar": mock_ext_pillar_func}),
    ):
        pillar = salt.pillar.Pillar(opts, {}, "mocked-minion", "dev")
    # ext pillar function doesn't have the extra_minion_data arg
    with patch(
        "salt.utils.args.get_function_argspec",
        MagicMock(return_value=MagicMock(args=[])),
    ):
        pillar._external_pillar_data("fake_pillar", {"arg": "foo"}, "fake_ext_pillar")
    mock_ext_pillar_func.assert_called_once_with(
        "mocked-minion", "fake_pillar", arg="foo"
    )
    # ext pillar function has the extra_minion_data arg
    mock_ext_pillar_func.reset_mock()
    with patch(
        "salt.utils.args.get_function_argspec",
        MagicMock(return_value=MagicMock(args=["extra_minion_data"])),
    ):
        pillar._external_pillar_data("fake_pillar", {"arg": "foo"}, "fake_ext_pillar")
    mock_ext_pillar_func.assert_called_once_with(
        "mocked-minion", "fake_pillar", arg="foo"
    )


def test_ext_pillar_no_extra_minion_data_val_list():
    opts = {
        "optimization_order": [0, 1, 2],
        "renderer": "json",
        "renderer_blacklist": [],
        "renderer_whitelist": [],
        "state_top": "",
        "pillar_roots": {"dev": [], "base": []},
        "file_roots": {"dev": [], "base": []},
        "extension_modules": "",
        "pillarenv_from_saltenv": True,
        "fileserver_backend": "",
        "cachedir": "",
    }
    mock_ext_pillar_func = MagicMock()
    with patch(
        "salt.loader.pillars",
        MagicMock(return_value={"fake_ext_pillar": mock_ext_pillar_func}),
    ):
        pillar = salt.pillar.Pillar(opts, {}, "mocked-minion", "dev")
    # ext pillar function doesn't have the extra_minion_data arg
    with patch(
        "salt.utils.args.get_function_argspec",
        MagicMock(return_value=MagicMock(args=[])),
    ):
        pillar._external_pillar_data("fake_pillar", ["foo"], "fake_ext_pillar")
    mock_ext_pillar_func.assert_called_once_with("mocked-minion", "fake_pillar", "foo")
    # ext pillar function has the extra_minion_data arg
    mock_ext_pillar_func.reset_mock()
    with patch(
        "salt.utils.args.get_function_argspec",
        MagicMock(return_value=MagicMock(args=["extra_minion_data"])),
    ):
        pillar._external_pillar_data("fake_pillar", ["foo"], "fake_ext_pillar")
    mock_ext_pillar_func.assert_called_once_with("mocked-minion", "fake_pillar", "foo")


def test_ext_pillar_no_extra_minion_data_val_elem():
    opts = {
        "optimization_order": [0, 1, 2],
        "renderer": "json",
        "renderer_blacklist": [],
        "renderer_whitelist": [],
        "state_top": "",
        "pillar_roots": {"dev": [], "base": []},
        "file_roots": {"dev": [], "base": []},
        "extension_modules": "",
        "pillarenv_from_saltenv": True,
        "fileserver_backend": "",
        "cachedir": "",
    }
    mock_ext_pillar_func = MagicMock()
    with patch(
        "salt.loader.pillars",
        MagicMock(return_value={"fake_ext_pillar": mock_ext_pillar_func}),
    ):
        pillar = salt.pillar.Pillar(opts, {}, "mocked-minion", "dev")
    # ext pillar function doesn't have the extra_minion_data arg
    with patch(
        "salt.utils.args.get_function_argspec",
        MagicMock(return_value=MagicMock(args=[])),
    ):
        pillar._external_pillar_data("fake_pillar", "fake_val", "fake_ext_pillar")
    mock_ext_pillar_func.assert_called_once_with(
        "mocked-minion", "fake_pillar", "fake_val"
    )
    # ext pillar function has the extra_minion_data arg
    mock_ext_pillar_func.reset_mock()
    with patch(
        "salt.utils.args.get_function_argspec",
        MagicMock(return_value=MagicMock(args=["extra_minion_data"])),
    ):
        pillar._external_pillar_data("fake_pillar", "fake_val", "fake_ext_pillar")
    mock_ext_pillar_func.assert_called_once_with(
        "mocked-minion", "fake_pillar", "fake_val"
    )


def test_ext_pillar_with_extra_minion_data_val_dict():
    opts = {
        "optimization_order": [0, 1, 2],
        "renderer": "json",
        "renderer_blacklist": [],
        "renderer_whitelist": [],
        "state_top": "",
        "pillar_roots": {"dev": [], "base": []},
        "file_roots": {"dev": [], "base": []},
        "extension_modules": "",
        "pillarenv_from_saltenv": True,
        "fileserver_backend": "",
        "cachedir": "",
    }
    mock_ext_pillar_func = MagicMock()
    with patch(
        "salt.loader.pillars",
        MagicMock(return_value={"fake_ext_pillar": mock_ext_pillar_func}),
    ):
        pillar = salt.pillar.Pillar(
            opts, {}, "mocked-minion", "dev", extra_minion_data={"fake_key": "foo"}
        )
    # ext pillar function doesn't have the extra_minion_data arg
    with patch(
        "salt.utils.args.get_function_argspec",
        MagicMock(return_value=MagicMock(args=[])),
    ):
        pillar._external_pillar_data("fake_pillar", {"arg": "foo"}, "fake_ext_pillar")
    mock_ext_pillar_func.assert_called_once_with(
        "mocked-minion", "fake_pillar", arg="foo"
    )
    # ext pillar function has the extra_minion_data arg
    mock_ext_pillar_func.reset_mock()
    with patch(
        "salt.utils.args.get_function_argspec",
        MagicMock(return_value=MagicMock(args=["extra_minion_data"])),
    ):
        pillar._external_pillar_data("fake_pillar", {"arg": "foo"}, "fake_ext_pillar")
    mock_ext_pillar_func.assert_called_once_with(
        "mocked-minion",
        "fake_pillar",
        arg="foo",
        extra_minion_data={"fake_key": "foo"},
    )


def test_ext_pillar_with_extra_minion_data_val_list():
    opts = {
        "optimization_order": [0, 1, 2],
        "renderer": "json",
        "renderer_blacklist": [],
        "renderer_whitelist": [],
        "state_top": "",
        "pillar_roots": {"dev": [], "base": []},
        "file_roots": {"dev": [], "base": []},
        "extension_modules": "",
        "pillarenv_from_saltenv": True,
        "fileserver_backend": "",
        "cachedir": "",
    }
    mock_ext_pillar_func = MagicMock()
    with patch(
        "salt.loader.pillars",
        MagicMock(return_value={"fake_ext_pillar": mock_ext_pillar_func}),
    ):
        pillar = salt.pillar.Pillar(
            opts, {}, "mocked-minion", "dev", extra_minion_data={"fake_key": "foo"}
        )
    # ext pillar function doesn't have the extra_minion_data arg
    with patch(
        "salt.utils.args.get_function_argspec",
        MagicMock(return_value=MagicMock(args=[])),
    ):
        pillar._external_pillar_data("fake_pillar", ["bar"], "fake_ext_pillar")
    mock_ext_pillar_func.assert_called_once_with("mocked-minion", "fake_pillar", "bar")
    # ext pillar function has the extra_minion_data arg
    mock_ext_pillar_func.reset_mock()
    with patch(
        "salt.utils.args.get_function_argspec",
        MagicMock(return_value=MagicMock(args=["extra_minion_data"])),
    ):
        pillar._external_pillar_data("fake_pillar", ["bar"], "fake_ext_pillar")
    mock_ext_pillar_func.assert_called_once_with(
        "mocked-minion", "fake_pillar", "bar", extra_minion_data={"fake_key": "foo"}
    )


def test_ext_pillar_with_extra_minion_data_val_elem():
    opts = {
        "optimization_order": [0, 1, 2],
        "renderer": "json",
        "renderer_blacklist": [],
        "renderer_whitelist": [],
        "state_top": "",
        "pillar_roots": {"dev": [], "base": []},
        "file_roots": {"dev": [], "base": []},
        "extension_modules": "",
        "pillarenv_from_saltenv": True,
        "fileserver_backend": "",
        "cachedir": "",
    }
    mock_ext_pillar_func = MagicMock()
    with patch(
        "salt.loader.pillars",
        MagicMock(return_value={"fake_ext_pillar": mock_ext_pillar_func}),
    ):
        pillar = salt.pillar.Pillar(
            opts, {}, "mocked-minion", "dev", extra_minion_data={"fake_key": "foo"}
        )
    # ext pillar function doesn't have the extra_minion_data arg
    with patch(
        "salt.utils.args.get_function_argspec",
        MagicMock(return_value=MagicMock(args=[])),
    ):
        pillar._external_pillar_data("fake_pillar", "bar", "fake_ext_pillar")
    mock_ext_pillar_func.assert_called_once_with("mocked-minion", "fake_pillar", "bar")
    # ext pillar function has the extra_minion_data arg
    mock_ext_pillar_func.reset_mock()
    with patch(
        "salt.utils.args.get_function_argspec",
        MagicMock(return_value=MagicMock(args=["extra_minion_data"])),
    ):
        pillar._external_pillar_data("fake_pillar", "bar", "fake_ext_pillar")
    mock_ext_pillar_func.assert_called_once_with(
        "mocked-minion", "fake_pillar", "bar", extra_minion_data={"fake_key": "foo"}
    )


def test_ext_pillar_first(tmp_path):
    """
    test when using ext_pillar and ext_pillar_first
    """
    opts = {
        "optimization_order": [0, 1, 2],
        "renderer": "yaml",
        "renderer_blacklist": [],
        "renderer_whitelist": [],
        "state_top": "",
        "pillar_roots": [],
        "extension_modules": "",
        "saltenv": "base",
        "file_roots": [],
        "ext_pillar_first": True,
        "fileserver_backend": "",
        "cachedir": "",
    }
    grains = {
        "os": "Ubuntu",
        "os_family": "Debian",
        "oscodename": "raring",
        "osfullname": "Ubuntu",
        "osrelease": "13.04",
        "kernel": "Linux",
    }

    sls_files = _setup_test_topfile_sls_pillar_match(
        str(tmp_path),
    )
    fc_mock = MockFileclient(
        cache_file=sls_files["top"]["dest"],
        list_states=["top", "ssh", "ssh.minion", "generic", "generic.minion"],
        get_state=sls_files,
    )
    with patch.object(
        salt.fileclient, "get_file_client", MagicMock(return_value=fc_mock)
    ), patch(
        "salt.pillar.Pillar.ext_pillar",
        MagicMock(
            return_value=(
                {"id": "minion", "phase": "alpha", "role": "database"},
                [],
            )
        ),
    ):
        pillar = salt.pillar.Pillar(opts, grains, "mocked-minion", "base")
        assert pillar.compile_pillar()["generic"]["key1"] == "value1"


@patch("salt.fileclient.Client.list_states")
def test_malformed_pillar_sls(mock_list_states):
    with patch("salt.pillar.compile_template") as compile_template:
        opts = {
            "optimization_order": [0, 1, 2],
            "renderer": "json",
            "renderer_blacklist": [],
            "renderer_whitelist": [],
            "state_top": "",
            "pillar_roots": [],
            "file_roots": [],
            "extension_modules": "",
            "fileserver_backend": "",
            "cachedir": "",
        }
        grains = {
            "os": "Ubuntu",
            "os_family": "Debian",
            "oscodename": "raring",
            "osfullname": "Ubuntu",
            "osrelease": "13.04",
            "kernel": "Linux",
        }

        mock_list_states.return_value = ["foo", "blah"]
        pillar = salt.pillar.Pillar(opts, grains, "mocked-minion", "base")
        # Mock getting the proper template files
        pillar.client.get_state = MagicMock(
            return_value={
                "dest": "/path/to/pillar/files/foo.sls",
                "source": "salt://foo.sls",
            }
        )

        # Template compilation returned a string
        compile_template.return_value = "BAHHH"
        assert pillar.render_pillar({"base": ["foo.sls"]}) == (
            {},
            ["SLS 'foo.sls' does not render to a dictionary"],
        )

        # Template compilation returned a list
        compile_template.return_value = ["BAHHH"]
        assert pillar.render_pillar({"base": ["foo.sls"]}) == (
            {},
            ["SLS 'foo.sls' does not render to a dictionary"],
        )

        # Template compilation returned a dictionary, which is what's expected
        compile_template.return_value = {"foo": "bar"}
        assert pillar.render_pillar({"base": ["foo.sls"]}) == ({"foo": "bar"}, [])

        # Test improper includes
        compile_template.side_effect = [
            {"foo": "bar", "include": "blah"},
            {"foo2": "bar2"},
        ]
        assert pillar.render_pillar({"base": ["foo.sls"]}) == (
            {"foo": "bar", "include": "blah"},
            ["Include Declaration in SLS 'foo.sls' is not formed as a list"],
        )

        # Test includes as a list, which is what's expected
        compile_template.side_effect = [
            {"foo": "bar", "include": ["blah"]},
            {"foo2": "bar2"},
        ]
        assert pillar.render_pillar({"base": ["foo.sls"]}) == (
            {"foo": "bar", "foo2": "bar2"},
            [],
        )

        # Test includes as a list overriding data
        compile_template.side_effect = [
            {"foo": "bar", "include": ["blah"]},
            {"foo": "bar2"},
        ]
        assert pillar.render_pillar({"base": ["foo.sls"]}) == ({"foo": "bar"}, [])

        # Test includes using empty key directive
        compile_template.side_effect = [
            {"foo": "bar", "include": [{"blah": {"key": ""}}]},
            {"foo": "bar2"},
        ]
        assert pillar.render_pillar({"base": ["foo.sls"]}) == ({"foo": "bar"}, [])

        # Test includes using simple non-nested key
        compile_template.side_effect = [
            {"foo": "bar", "include": [{"blah": {"key": "nested"}}]},
            {"foo": "bar2"},
        ]
        assert pillar.render_pillar({"base": ["foo.sls"]}) == (
            {"foo": "bar", "nested": {"foo": "bar2"}},
            [],
        )

        # Test includes using nested key
        compile_template.side_effect = [
            {"foo": "bar", "include": [{"blah": {"key": "nested:level"}}]},
            {"foo": "bar2"},
        ]
        assert pillar.render_pillar({"base": ["foo.sls"]}) == (
            {"foo": "bar", "nested": {"level": {"foo": "bar2"}}},
            [],
        )


def test_includes_override_sls():
    opts = {
        "optimization_order": [0, 1, 2],
        "renderer": "json",
        "renderer_blacklist": [],
        "renderer_whitelist": [],
        "state_top": "",
        "pillar_roots": {},
        "file_roots": {},
        "extension_modules": "",
        "fileserver_backend": "roots",
        "cachedir": "",
    }
    grains = {
        "os": "Ubuntu",
        "os_family": "Debian",
        "oscodename": "raring",
        "osfullname": "Ubuntu",
        "osrelease": "13.04",
        "kernel": "Linux",
    }
    with patch("salt.pillar.compile_template") as compile_template, patch.object(
        salt.pillar.Pillar,
        "_Pillar__gather_avail",
        MagicMock(return_value={"base": ["blah", "foo"]}),
    ):

        # Test with option set to True
        opts["pillar_includes_override_sls"] = True
        pillar = salt.pillar.Pillar(opts, grains, "mocked-minion", "base")
        # Mock getting the proper template files
        pillar.client.get_state = MagicMock(
            return_value={
                "dest": "/path/to/pillar/files/foo.sls",
                "source": "salt://foo.sls",
            }
        )

        compile_template.side_effect = [
            {"foo": "bar", "include": ["blah"]},
            {"foo": "bar2"},
        ]
        assert pillar.render_pillar({"base": ["foo.sls"]}) == ({"foo": "bar2"}, [])

        # Test with option set to False
        opts["pillar_includes_override_sls"] = False
        pillar = salt.pillar.Pillar(opts, grains, "mocked-minion", "base")
        # Mock getting the proper template files
        pillar.client.get_state = MagicMock(
            return_value={
                "dest": "/path/to/pillar/files/foo.sls",
                "source": "salt://foo.sls",
            }
        )

        compile_template.side_effect = [
            {"foo": "bar", "include": ["blah"]},
            {"foo": "bar2"},
        ]
        assert pillar.render_pillar({"base": ["foo.sls"]}) == ({"foo": "bar"}, [])


def test_topfile_order():
    opts = {
        "optimization_order": [0, 1, 2],
        "renderer": "yaml",
        "renderer_blacklist": [],
        "renderer_whitelist": [],
        "state_top": "",
        "pillar_roots": [],
        "extension_modules": "",
        "saltenv": "base",
        "file_roots": [],
        "fileserver_backend": "roots",
        "cachedir": "",
    }
    grains = {
        "os": "Ubuntu",
        "os_family": "Debian",
        "oscodename": "raring",
        "osfullname": "Ubuntu",
        "osrelease": "13.04",
        "kernel": "Linux",
    }

    def _run_test(nodegroup_order, glob_order, expected):
        tempdir = tempfile.mkdtemp(dir=RUNTIME_VARS.TMP)
        try:
            sls_files = _setup_test_topfile_sls(tempdir, nodegroup_order, glob_order)
            fc_mock = MockFileclient(
                cache_file=sls_files["top"]["dest"],
                list_states=[
                    "top",
                    "ssh",
                    "ssh.minion",
                    "generic",
                    "generic.minion",
                ],
                get_state=sls_files,
            )
            with patch.object(
                salt.fileclient, "get_file_client", MagicMock(return_value=fc_mock)
            ):
                pillar = salt.pillar.Pillar(opts, grains, "mocked-minion", "base")
                # Make sure that confirm_top.confirm_top returns True
                pillar.matchers["confirm_top.confirm_top"] = lambda *x, **y: True
                assert pillar.compile_pillar()["ssh"] == expected
        finally:
            shutil.rmtree(tempdir, ignore_errors=True)

    # test case where glob match happens second and therefore takes
    # precedence over nodegroup match.
    _run_test(nodegroup_order=1, glob_order=2, expected="bar")
    # test case where nodegroup match happens second and therefore takes
    # precedence over glob match.
    _run_test(nodegroup_order=2, glob_order=1, expected="foo")


def test_relative_include(tmp_path):
    join = os.path.join
    with fopen(join(str(tmp_path), "top.sls"), "w") as f:
        print(
            textwrap.dedent(
                """
                base:
                  '*':
                    - includer
                    - simple_includer
                    - includes.with.more.depth
            """
            ),
            file=f,
        )
    includer_dir = str(tmp_path / "includer")
    os.makedirs(includer_dir)
    with fopen(join(includer_dir, "init.sls"), "w") as f:
        print(
            textwrap.dedent(
                """
                include:
                  - .this
                  - includer.that
            """
            ),
            file=f,
        )
    with fopen(join(includer_dir, "this.sls"), "w") as f:
        print(
            textwrap.dedent(
                """
                this:
                    is all good
            """
            ),
            file=f,
        )
    with fopen(join(includer_dir, "that.sls"), "w") as f:
        print(
            textwrap.dedent(
                """
                that:
                    is also all good
            """
            ),
            file=f,
        )

    with fopen(str(tmp_path / "simple_includer.sls"), "w") as simpleincluder:
        print(
            textwrap.dedent(
                """
                include:
                  - .simple
                  - super_simple
            """
            ),
            file=simpleincluder,
        )
    with fopen(str(tmp_path / "simple.sls"), "w") as f:
        print(
            textwrap.dedent(
                """
                simple:
                  simon
            """
            ),
            file=f,
        )
    with fopen(str(tmp_path / "super_simple.sls"), "w") as f:
        print(
            textwrap.dedent(
                """
                super simple:
                  a caveman
            """
            ),
            file=f,
        )

    depth_dir = tmp_path / "includes" / "with" / "more"
    os.makedirs(str(depth_dir))
    with fopen(str(depth_dir / "depth.sls"), "w") as f:
        print(
            textwrap.dedent(
                """
                include:
                  - .ramble
                  - includes.with.more.doors

                mordor:
                    has dark depths
            """
            ),
            file=f,
        )

    with fopen(str(depth_dir / "ramble.sls"), "w") as f:
        print(
            textwrap.dedent(
                """
                found:
                    my precious
            """
            ),
            file=f,
        )

    with fopen(str(depth_dir / "doors.sls"), "w") as f:
        print(
            textwrap.dedent(
                """
                mojo:
                    bad risin'
            """
            ),
            file=f,
        )
    opts = {
        "optimization_order": [0, 1, 2],
        "renderer": "yaml",
        "renderer_blacklist": [],
        "renderer_whitelist": [],
        "state_top": "top.sls",
        "pillar_roots": {"base": [str(tmp_path)]},
        "extension_modules": "",
        "saltenv": "base",
        "file_roots": [],
        "file_ignore_regex": None,
        "file_ignore_glob": None,
        "fileserver_backend": "roots",
        "cachedir": "",
    }
    grains = {
        "os": "Ubuntu",
        "os_family": "Debian",
        "oscodename": "raring",
        "osfullname": "Ubuntu",
        "osrelease": "13.04",
        "kernel": "Linux",
    }
    pillar = salt.pillar.Pillar(opts, grains, "minion", "base")
    # Make sure that confirm_top.confirm_top returns True
    pillar.matchers["confirm_top.confirm_top"] = lambda *x, **y: True

    # Act
    compiled_pillar = pillar.compile_pillar()

    # Assert
    assert compiled_pillar["this"] == "is all good"
    assert compiled_pillar["that"] == "is also all good"
    assert compiled_pillar["simple"] == "simon"
    assert compiled_pillar["super simple"] == "a caveman"
    assert compiled_pillar["mordor"] == "has dark depths"
    assert compiled_pillar["found"] == "my precious"
    assert compiled_pillar["mojo"] == "bad risin'"


def test_missing_include(tmp_path):
    opts = {
        "optimization_order": [0, 1, 2],
        "renderer": "yaml",
        "renderer_blacklist": [],
        "renderer_whitelist": [],
        "state_top": "top.sls",
        "pillar_roots": {"base": [str(tmp_path)]},
        "extension_modules": "",
        "saltenv": "base",
        "file_roots": [],
        "file_ignore_regex": None,
        "file_ignore_glob": None,
        "fileserver_backend": "roots",
        "cachedir": "",
    }
    grains = {
        "os": "Ubuntu",
        "os_family": "Debian",
        "oscodename": "raring",
        "osfullname": "Ubuntu",
        "osrelease": "13.04",
        "kernel": "Linux",
    }

    with fopen(str(tmp_path / "top.sls"), "w") as f:
        print(
            textwrap.dedent(
                """
                base:
                  '*':
                    - simple_include
            """
            ),
            file=f,
        )
    include_dir = tmp_path / "simple_include"
    os.makedirs(include_dir)
    with fopen(str(include_dir / "init.sls"), "w") as f:
        print(
            textwrap.dedent(
                """
                include:
                  - simple_include.missing_include
                simple_include: is ok
                """
            ),
            file=f,
        )

    pillar = salt.pillar.Pillar(opts, grains, "minion", "base")
    # Make sure that confirm_top.confirm_top returns True
    pillar.matchers["confirm_top.confirm_top"] = lambda *x, **y: True

    # Act
    compiled_pillar = pillar.compile_pillar()

    # Assert
    assert compiled_pillar["simple_include"] == "is ok"
    assert "_errors" in compiled_pillar
    assert "simple_include.missing_include" in compiled_pillar["_errors"][0]


def test_get_opts_in_pillar_override_call(minion_opts, grains):
    mock_get_extra_minion_data = MagicMock(return_value={})
    with patch(
        "salt.pillar.RemotePillarMixin.get_ext_pillar_extra_minion_data",
        mock_get_extra_minion_data,
    ):

        salt.pillar.RemotePillar(minion_opts, grains, "mocked-minion", "dev")
    call_opts = dict(minion_opts, saltenv="dev")
    mock_get_extra_minion_data.assert_called_once_with(call_opts)


def test_multiple_keys_in_opts_added_to_pillar(grains, tmp_pki):
    opts = {
        "pki_dir": tmp_pki,
        "id": "minion",
        "master_uri": "tcp://127.0.0.1:4505",
        "__role": "minion",
        "keysize": 2048,
        "renderer": "json",
        "path_to_add": "fake_data",
        "path_to_add2": {"fake_data2": ["fake_data3", "fake_data4"]},
        "pass_to_ext_pillars": ["path_to_add", "path_to_add2"],
    }
    pillar = salt.pillar.RemotePillar(opts, grains, "mocked-minion", "dev")
    assert pillar.extra_minion_data == {
        "path_to_add": "fake_data",
        "path_to_add2": {"fake_data2": ["fake_data3", "fake_data4"]},
    }


def test_subkey_in_opts_added_to_pillar(minion_opts, grains):
    opts = dict(
        minion_opts,
        path_to_add2={
            "fake_data5": "fake_data6",
            "fake_data2": ["fake_data3", "fake_data4"],
        },
        pass_to_ext_pillars=["path_to_add2:fake_data5"],
    )
    pillar = salt.pillar.RemotePillar(opts, grains, "mocked-minion", "dev")
    assert pillar.extra_minion_data == {"path_to_add2": {"fake_data5": "fake_data6"}}


def test_non_existent_leaf_opt_in_add_to_pillar(minion_opts, grains):
    pillar = salt.pillar.RemotePillar(minion_opts, grains, "mocked-minion", "dev")
    assert pillar.pillar_override == {}


def test_non_existent_intermediate_opt_in_add_to_pillar(minion_opts, grains):
    pillar = salt.pillar.RemotePillar(minion_opts, grains, "mocked-minion", "dev")
    assert pillar.pillar_override == {}


def test_malformed_add_to_pillar(minion_opts, grains):
    opts = dict(minion_opts, pass_to_ext_pillars=MagicMock())
    with pytest.raises(salt.exceptions.SaltClientError) as excinfo:
        salt.pillar.RemotePillar(opts, grains, "mocked-minion", "dev")
        assert (
            excinfo.exception.strerror == "'pass_to_ext_pillars' config is malformed."
        )


def test_pillar_file_client_master_remote(tmp_pki, grains):
    """
    Test condition where local file_client and use_master_when_local option
    returns a remote file client.
    """
    mocked_minion = MagicMock()
    opts = {
        "pki_dir": tmp_pki,
        "id": "minion",
        "master_uri": "tcp://127.0.0.1:4505",
        "__role": "minion",
        "keysize": 2048,
        "file_client": "local",
        "use_master_when_local": True,
        "pillar_cache": None,
    }
    pillar = salt.pillar.get_pillar(opts, grains, mocked_minion)
    assert type(pillar) == salt.pillar.RemotePillar
    assert type(pillar) != salt.pillar.PillarCache


def test_pillar_send_extra_minion_data_from_config(tmp_pki, grains):
    opts = {
        "pki_dir": tmp_pki,
        "id": "minion",
        "master_uri": "tcp://127.0.0.1:4505",
        "__role": "minion",
        "keysize": 2048,
        "renderer": "json",
        "pillarenv": "fake_pillar_env",
        "path_to_add": "fake_data",
        "path_to_add2": {
            "fake_data5": "fake_data6",
            "fake_data2": ["fake_data3", "fake_data4"],
        },
        "pass_to_ext_pillars": ["path_to_add"],
    }
    mock_channel = MagicMock(
        crypted_transfer_decode_dictentry=MagicMock(return_value={})
    )
    with patch(
        "salt.channel.client.AsyncReqChannel.factory",
        MagicMock(return_value=mock_channel),
    ):
        pillar = salt.pillar.RemotePillar(opts, grains, "mocked_minion", "fake_env")

    ret = pillar.compile_pillar()
    mock_channel.crypted_transfer_decode_dictentry.assert_called_once_with(
        {
            "cmd": "_pillar",
            "ver": "2",
            "id": "mocked_minion",
            "grains": {},
            "saltenv": "fake_env",
            "pillarenv": "fake_pillar_env",
            "pillar_override": {},
            "extra_minion_data": {"path_to_add": "fake_data"},
        },
        dictkey="pillar",
    )


def test_include(tmp_path):
    opts = {
        "optimization_order": [0, 1, 2],
        "renderer": "yaml",
        "renderer_blacklist": [],
        "renderer_whitelist": [],
        "state_top": "",
        "pillar_roots": [],
        "extension_modules": "",
        "saltenv": "base",
        "file_roots": [],
        "fileserver_backend": "roots",
        "cachedir": "",
    }
    grains = {
        "os": "Ubuntu",
        "os_family": "Debian",
        "oscodename": "raring",
        "osfullname": "Ubuntu",
        "osrelease": "13.04",
        "kernel": "Linux",
    }
    sls_files = _setup_test_include_sls(str(tmp_path))
    fc_mock = MockFileclient(
        cache_file=sls_files["top"]["dest"],
        get_state=sls_files,
        list_states=[
            "top",
            "test.init",
            "test.sub1",
            "test.sub2",
            "test.sub_wildcard_1",
            "test.sub_with_init_dot",
            "test.sub.with.slashes",
        ],
    )
    with patch.object(
        salt.fileclient, "get_file_client", MagicMock(return_value=fc_mock)
    ):
        pillar = salt.pillar.Pillar(opts, grains, "minion", "base")
        # Make sure that confirm_top.confirm_top returns True
        pillar.matchers["confirm_top.confirm_top"] = lambda *x, **y: True
        compiled_pillar = pillar.compile_pillar()
        assert compiled_pillar["foo_wildcard"] == "bar_wildcard"
        assert compiled_pillar["foo1"] == "bar1"
        assert compiled_pillar["foo2"] == "bar2"
        assert compiled_pillar["sub_with_slashes"] == "sub_slashes_worked"
        assert compiled_pillar["sub_init_dot"] == "sub_with_init_dot_worked"


def test_compile_pillar_memory_cache(master_opts):
    master_opts.update({"pillar_cache_backend": "memory", "pillar_cache_ttl": 3600})

    pillar = salt.pillar.PillarCache(
        master_opts,
        grains,
        "mocked_minion",
        "fake_env",
        pillarenv="base",
    )

    with patch(
        "salt.pillar.PillarCache.fetch_pillar",
        side_effect=[{"foo": "bar"}, {"foo": "baz"}],
    ):
        # Run once for pillarenv base
        ret = pillar.compile_pillar()
        expected_cache = {"base": {"foo": "bar"}}
        assert "mocked_minion" in pillar.cache
        assert pillar.cache["mocked_minion"] == expected_cache

        # Run a second time for pillarenv base
        ret = pillar.compile_pillar()
        expected_cache = {"base": {"foo": "bar"}}
        assert "mocked_minion" in pillar.cache
        assert pillar.cache["mocked_minion"] == expected_cache

        # Change the pillarenv
        pillar.pillarenv = "dev"

        # Run once for pillarenv dev
        ret = pillar.compile_pillar()
        expected_cache = {"base": {"foo": "bar"}, "dev": {"foo": "baz"}}
        assert "mocked_minion" in pillar.cache
        assert pillar.cache["mocked_minion"] == expected_cache

        # Run a second time for pillarenv dev
        ret = pillar.compile_pillar()
        expected_cache = {"base": {"foo": "bar"}, "dev": {"foo": "baz"}}
        assert "mocked_minion" in pillar.cache
        assert pillar.cache["mocked_minion"] == expected_cache


def test_compile_pillar_disk_cache(master_opts, grains):
    master_opts.update({"pillar_cache_backend": "disk", "pillar_cache_ttl": 3600})

    pillar = salt.pillar.PillarCache(
        master_opts,
        grains,
        "mocked_minion",
        "fake_env",
        pillarenv="base",
    )

    with patch("salt.utils.cache.CacheDisk._write", MagicMock()):
        with patch(
            "salt.pillar.PillarCache.fetch_pillar",
            side_effect=[{"foo": "bar"}, {"foo": "baz"}],
        ):
            # Run once for pillarenv base
            ret = pillar.compile_pillar()
            expected_cache = {"mocked_minion": {"base": {"foo": "bar"}}}
            assert pillar.cache._dict == expected_cache

            # Run a second time for pillarenv base
            ret = pillar.compile_pillar()
            expected_cache = {"mocked_minion": {"base": {"foo": "bar"}}}
            assert pillar.cache._dict == expected_cache

            # Change the pillarenv
            pillar.pillarenv = "dev"

            # Run once for pillarenv dev
            ret = pillar.compile_pillar()
            expected_cache = {
                "mocked_minion": {"base": {"foo": "bar"}, "dev": {"foo": "baz"}}
            }
            assert pillar.cache._dict == expected_cache

            # Run a second time for pillarenv dev
            ret = pillar.compile_pillar()
            expected_cache = {
                "mocked_minion": {"base": {"foo": "bar"}, "dev": {"foo": "baz"}}
            }
            assert pillar.cache._dict == expected_cache


def test_remote_pillar_bad_return(grains, tmp_pki):
    opts = {
        "pki_dir": tmp_pki,
        "id": "minion",
        "master_uri": "tcp://127.0.0.1:4505",
        "__role": "minion",
        "keysize": 2048,
        "saltenv": "base",
        "pillarenv": "base",
    }
    pillar = salt.pillar.RemotePillar(opts, grains, "mocked-minion", "dev")

    async def crypted_transfer_mock():
        return ""

    pillar.channel.crypted_transfer_decode_dictentry = crypted_transfer_mock
    with pytest.raises(salt.exceptions.SaltClientError):
        pillar.compile_pillar()


async def test_async_remote_pillar_bad_return(grains, tmp_pki):
    opts = {
        "pki_dir": tmp_pki,
        "id": "minion",
        "master_uri": "tcp://127.0.0.1:4505",
        "__role": "minion",
        "keysize": 2048,
        "saltenv": "base",
        "pillarenv": "base",
    }
    pillar = salt.pillar.AsyncRemotePillar(opts, grains, "mocked-minion", "dev")

    async def crypted_transfer_mock():
        return ""

    pillar.channel.crypted_transfer_decode_dictentry = crypted_transfer_mock
    with pytest.raises(salt.exceptions.SaltClientError):
        await pillar.compile_pillar()
