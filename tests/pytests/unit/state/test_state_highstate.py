"""
    :codeauthor: Nicole Thomas <nicole@saltstack.com>
"""

import logging

import pytest  # pylint: disable=unused-import
import salt.state

log = logging.getLogger(__name__)


@pytest.fixture
def root_dir(tmp_path):
    return tmp_path / "root_dir"


@pytest.fixture
def state_tree_dir(root_dir):
    return root_dir / "state_tree"


@pytest.fixture
def cache_dir(root_dir):
    return root_dir / "cache_dir"


@pytest.fixture
def highstate(temp_salt_minion, temp_salt_master, root_dir, state_tree_dir, cache_dir):
    # for dpath in (root_dir, state_tree_dir, cache_dir):
    #    if not os.path.isdir(dpath):
    #        os.makedirs(dpath)

    opts = temp_salt_minion.config.copy()
    opts["root_dir"] = str(root_dir)
    opts["state_events"] = False
    opts["id"] = "match"
    opts["file_client"] = "local"
    opts["file_roots"] = dict(base=[str(state_tree_dir)])
    opts["cachedir"] = str(cache_dir)
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


def test_top_matches_with_list(highstate):
    top = {"env": {"match": ["state1", "state2"], "nomatch": ["state3"]}}
    matches = highstate.top_matches(top)
    assert matches == {"env": ["state1", "state2"]}


def test_top_matches_with_string(highstate):
    top = {"env": {"match": "state1", "nomatch": "state2"}}
    matches = highstate.top_matches(top)
    assert matches == {"env": ["state1"]}


def test_matches_whitelist(highstate):
    matches = {"env": ["state1", "state2", "state3"]}
    matches = highstate.matches_whitelist(matches, ["state2"])
    assert matches == {"env": ["state2"]}


def test_matches_whitelist_with_string(highstate):
    matches = {"env": ["state1", "state2", "state3"]}
    matches = highstate.matches_whitelist(matches, "state2,state3")
    assert matches == {"env": ["state2", "state3"]}


def test_compile_state_usage(highstate, state_tree_dir):
    top = pytest.helpers.temp_file("top.sls", "base: {'*': [foo]}", str(state_tree_dir))
    used_state = pytest.helpers.temp_file(
        "foo.sls", "foo: test.nop", str(state_tree_dir)
    )
    unused_state = pytest.helpers.temp_file(
        "bar.sls", "bar: test.nop", str(state_tree_dir)
    )

    with top, used_state, unused_state:
        state_usage_dict = highstate.compile_state_usage()

        assert state_usage_dict["base"]["count_unused"] == 2
        assert state_usage_dict["base"]["count_used"] == 1
        assert state_usage_dict["base"]["count_all"] == 3
        assert state_usage_dict["base"]["used"] == ["foo"]
        assert state_usage_dict["base"]["unused"] == ["bar", "top"]


def test_find_sls_ids_with_exclude(highstate, state_tree_dir):
    """
    See https://github.com/saltstack/salt/issues/47182
    """
    top_sls = """
    base:
      '*':
        - issue-47182.stateA
        - issue-47182.stateB
        """

    slsfile1 = """
    slsfile1-nop:
        test.nop
        """

    slsfile2 = """
    slsfile2-nop:
      test.nop
        """

    stateB = """
    include:
      - issue-47182.slsfile1
      - issue-47182.slsfile2

    some-state:
      test.nop:
        - require:
          - sls: issue-47182.slsfile1
        - require_in:
          - sls: issue-47182.slsfile2
        """

    stateA_init = """
    include:
      - issue-47182.stateA.newer
        """

    stateA_newer = """
    exclude:
      - sls: issue-47182.stateA

    somestuff:
      cmd.run:
        - name: echo This supersedes the stuff previously done in issue-47182.stateA
        """

    sls_dir = str(state_tree_dir / "issue-47182")
    stateA_sls_dir = str(state_tree_dir / "issue-47182" / "stateA")

    with pytest.helpers.temp_file("top.sls", top_sls, str(state_tree_dir)):
        with pytest.helpers.temp_file(
            "slsfile1.sls", slsfile1, sls_dir
        ), pytest.helpers.temp_file(
            "slsfile1.sls", slsfile1, sls_dir
        ), pytest.helpers.temp_file(
            "stateB.sls", stateB, sls_dir
        ), pytest.helpers.temp_file(
            "init.sls", stateA_init, stateA_sls_dir
        ), pytest.helpers.temp_file(
            "newer.sls", stateA_newer, stateA_sls_dir
        ):
            # Manually compile the high data. We don't have to worry about all of
            # the normal error checking we do here since we know that all the SLS
            # files exist and there is no whitelist/blacklist being used.
            top = highstate.get_top()  # pylint: disable=assignment-from-none
            matches = highstate.top_matches(top)
            high, _ = highstate.render_highstate(matches)
            ret = salt.state.find_sls_ids("issue-47182.stateA.newer", high)
            assert ret == [("somestuff", "cmd")]
