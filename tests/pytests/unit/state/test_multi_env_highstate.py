"""
    :codeauthor: Nicole Thomas <nicole@saltstack.com>
"""

import logging
import os

import pytest  # pylint: disable=unused-import

import salt.exceptions
import salt.state
import salt.utils.files
import salt.utils.platform

log = logging.getLogger(__name__)


@pytest.fixture
def root_dir(tmp_path):
    return str(tmp_path / "root_dir")


@pytest.fixture
def base_state_tree_dir(root_dir):
    return os.path.join(root_dir, "base_state_tree")


@pytest.fixture
def other_state_tree_dir(root_dir):
    return os.path.join(root_dir, "other_state_tree")


@pytest.fixture
def cache_dir(root_dir):
    return os.path.join(root_dir, "cachedir")


@pytest.fixture
def highstate(
    temp_salt_minion,
    temp_salt_master,
    root_dir,
    base_state_tree_dir,
    other_state_tree_dir,
    cache_dir,
):
    for dpath in (
        root_dir,
        base_state_tree_dir,
        other_state_tree_dir,
        cache_dir,
    ):
        if not os.path.isdir(dpath):
            os.makedirs(dpath)

    test_sls = """
    test state:
      test.succeed_without_changes:
        - name: test
        """

    with pytest.helpers.temp_file("test.sls", test_sls, other_state_tree_dir):

        opts = temp_salt_minion.config.copy()
        opts["root_dir"] = root_dir
        opts["state_events"] = False
        opts["id"] = "match"
        opts["file_client"] = "local"
        opts["file_roots"] = dict(
            base=[base_state_tree_dir],
            other=[other_state_tree_dir],
            __env__=[base_state_tree_dir],
        )
        opts["cachedir"] = cache_dir
        opts["test"] = False

        opts.update(
            {
                "transport": "zeromq",
                "auth_tries": 1,
                "auth_timeout": 5,
                "master_ip": "127.0.0.1",
                "master_port": temp_salt_master.config["ret_port"],
                "master_uri": "tcp://127.0.0.1:{}".format(
                    temp_salt_master.config["ret_port"]
                ),
            }
        )

        _highstate = salt.state.HighState(opts)
        _highstate.push_active()

        yield _highstate


def test_lazy_avail_states_base(highstate, base_state_tree_dir, tmp_path):
    top_sls = """
    base:
      '*':
        - core
        """

    core_state = """
    {}/testfile:
      file:
        - managed
        - source: salt://testfile
        - makedirs: true
        """.format(
        str(tmp_path)
    )

    with pytest.helpers.temp_file(
        "top.sls", top_sls, base_state_tree_dir
    ), pytest.helpers.temp_file("core.sls", core_state, base_state_tree_dir):
        # list_states not called yet
        assert not highstate.avail._filled
        assert highstate.avail._avail == {"base": None}
        # After getting 'base' env available states
        highstate.avail["base"]  # pylint: disable=pointless-statement
        assert not highstate.avail._filled
        assert highstate.avail._avail == {"base": ["core", "top"]}


def test_lazy_avail_states_other(highstate, base_state_tree_dir, tmp_path):
    top_sls = """
    base:
      '*':
        - core
        """

    core_state = """
    {}/testfile:
      file:
        - managed
        - source: salt://testfile
        - makedirs: true
        """.format(
        str(tmp_path)
    )

    with pytest.helpers.temp_file(
        "top.sls", top_sls, base_state_tree_dir
    ), pytest.helpers.temp_file("core.sls", core_state, base_state_tree_dir):
        # list_states not called yet
        assert not highstate.avail._filled
        assert highstate.avail._avail == {"base": None}
        # After getting 'other' env available states
        highstate.avail["other"]  # pylint: disable=pointless-statement
        assert highstate.avail._filled
        assert highstate.avail._avail == {
            "base": None,
            "__env__": None,
            "other": ["test"],
        }


def test_lazy_avail_states_multi(highstate, base_state_tree_dir, tmp_path):
    top_sls = """
    base:
      '*':
        - core
        """

    core_state = """
    {}/testfile:
      file:
        - managed
        - source: salt://testfile
        - makedirs: true
        """.format(
        str(tmp_path)
    )

    with pytest.helpers.temp_file(
        "top.sls", top_sls, base_state_tree_dir
    ), pytest.helpers.temp_file("core.sls", core_state, base_state_tree_dir):
        # list_states not called yet
        assert not highstate.avail._filled
        assert highstate.avail._avail == {"base": None}
        # After getting 'base' env available states
        highstate.avail["base"]  # pylint: disable=pointless-statement
        assert not highstate.avail._filled
        assert highstate.avail._avail == {"base": ["core", "top"]}
        # After getting 'other' env available states
        highstate.avail["other"]  # pylint: disable=pointless-statement
        assert highstate.avail._filled
        assert highstate.avail._avail == {
            "base": ["core", "top"],
            "__env__": None,
            "other": ["test"],
        }


def test_lazy_avail_states_dynamic(highstate, base_state_tree_dir, tmp_path):
    top_sls = """
    {{ saltenv }}:
      '*':
        - core
        """

    core_state = """
    include:
      - includeme

    {}/testfile:
      file:
        - managed
        - source: salt://testfile
        - makedirs: true
        """.format(
        str(tmp_path)
    )

    includeme_state = """
    included state:
      test.succeed_without_changes:
        - name: test
    """

    with pytest.helpers.temp_file(
        "top.sls", top_sls, base_state_tree_dir
    ), pytest.helpers.temp_file(
        "core.sls", core_state, base_state_tree_dir
    ), pytest.helpers.temp_file(
        "includeme.sls", includeme_state, base_state_tree_dir
    ):
        # list_states not called yet
        assert not highstate.avail._filled
        assert highstate.avail._avail == {"base": None}
        # After getting 'base' env available states
        highstate.avail["base"]  # pylint: disable=pointless-statement
        assert not highstate.avail._filled
        assert highstate.avail._avail == {"base": ["core", "includeme", "top"]}
        # After getting 'dynamic' env available states
        highstate.avail["dynamic"]  # pylint: disable=pointless-statement
        assert highstate.avail._filled
        assert highstate.avail._avail == {
            "__env__": None,
            "base": ["core", "includeme", "top"],
            "dynamic": ["core", "includeme", "top"],
            "other": None,
        }
