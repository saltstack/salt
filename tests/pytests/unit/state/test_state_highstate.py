"""
    :codeauthor: Nicole Thomas <nicole@saltstack.com>
"""

import logging
import textwrap

import pytest  # pylint: disable=unused-import

import salt.state
from salt.utils.odict import DefaultOrderedDict, OrderedDict

log = logging.getLogger(__name__)


pytestmark = [
    pytest.mark.core_test,
]


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


def test_compile_state_usage_empty_topfile(highstate, state_tree_dir):
    """
    See https://github.com/saltstack/salt/issues/61614.

    The failure was triggered by having a saltenv that contained states but was
    not referenced in any topfile. A simple test case is an empty topfile in
    the base saltenv.
    """
    top = pytest.helpers.temp_file("top.sls", "", str(state_tree_dir))
    unused_state = pytest.helpers.temp_file(
        "foo.sls", "foo: test.nop", str(state_tree_dir)
    )

    with top, unused_state:
        state_usage_dict = highstate.compile_state_usage()

        assert state_usage_dict["base"]["count_unused"] == 2
        assert state_usage_dict["base"]["count_used"] == 0
        assert state_usage_dict["base"]["count_all"] == 2
        assert state_usage_dict["base"]["used"] == []
        assert state_usage_dict["base"]["unused"] == ["foo", "top"]


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
            "slsfile2.sls", slsfile2, sls_dir
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


def test_dont_extend_in_excluded_sls_file(highstate, state_tree_dir):
    """
    See https://github.com/saltstack/salt/issues/62082#issuecomment-1245461333
    """
    top_sls = textwrap.dedent(
        """\
        base:
          '*':
            - test1
            - exclude
        """
    )
    exclude_sls = textwrap.dedent(
        """\
       exclude:
         - sls: test2
       """
    )
    test1_sls = textwrap.dedent(
        """\
       include:
         - test2

       test1:
         cmd.run:
           - name: echo test1
       """
    )
    test2_sls = textwrap.dedent(
        """\
        extend:
          test1:
            cmd.run:
              - name: echo "override test1 in test2"

        test2-id:
          cmd.run:
            - name: echo test2
        """
    )
    sls_dir = str(state_tree_dir)
    with pytest.helpers.temp_file(
        "top.sls", top_sls, sls_dir
    ), pytest.helpers.temp_file(
        "test1.sls", test1_sls, sls_dir
    ), pytest.helpers.temp_file(
        "test2.sls", test2_sls, sls_dir
    ), pytest.helpers.temp_file(
        "exclude.sls", exclude_sls, sls_dir
    ):
        # manually compile the high data, error checking is not needed in this
        # test case.
        top = highstate.get_top()
        matches = highstate.top_matches(top)
        high, _ = highstate.render_highstate(matches)

        # high is mutated by call_high and the different "pipeline steps"
        assert high == OrderedDict(
            [
                (
                    "__extend__",
                    [
                        {
                            "test1": OrderedDict(
                                [
                                    ("__sls__", "test2"),
                                    ("__env__", "base"),
                                    (
                                        "cmd",
                                        [
                                            OrderedDict(
                                                [
                                                    (
                                                        "name",
                                                        'echo "override test1 in test2"',
                                                    )
                                                ]
                                            ),
                                            "run",
                                        ],
                                    ),
                                ]
                            )
                        }
                    ],
                ),
                (
                    "test1",
                    OrderedDict(
                        [
                            (
                                "cmd",
                                [
                                    OrderedDict([("name", "echo test1")]),
                                    "run",
                                    {"order": 10001},
                                ],
                            ),
                            ("__sls__", "test1"),
                            ("__env__", "base"),
                        ]
                    ),
                ),
                (
                    "test2-id",
                    OrderedDict(
                        [
                            (
                                "cmd",
                                [
                                    OrderedDict([("name", "echo test2")]),
                                    "run",
                                    {"order": 10000},
                                ],
                            ),
                            ("__sls__", "test2"),
                            ("__env__", "base"),
                            ("__sls_included_from__", ["test1"]),
                        ]
                    ),
                ),
                ("__exclude__", [OrderedDict([("sls", "test2")])]),
            ]
        )
        highstate.state.call_high(high)
        # assert that the extend declaration was not applied
        assert high == OrderedDict(
            [
                (
                    "test1",
                    OrderedDict(
                        [
                            (
                                "cmd",
                                [
                                    OrderedDict([("name", "echo test1")]),
                                    "run",
                                    {"order": 10001},
                                ],
                            ),
                            ("__sls__", "test1"),
                            ("__env__", "base"),
                        ]
                    ),
                )
            ]
        )


def test_verify_tops(highstate):
    """
    test basic functionality of verify_tops
    """
    tops = DefaultOrderedDict(OrderedDict)
    tops["base"] = OrderedDict([("*", ["test", "test2"])])
    matches = highstate.verify_tops(tops)
    # [] means there where no errors when verifying tops
    assert matches == []


def test_verify_tops_not_dict(highstate):
    """
    test verify_tops when top data is not a dict
    """
    matches = highstate.verify_tops(["base", "test", "test2"])
    assert matches == ["Top data was not formed as a dict"]


def test_verify_tops_env_empty(highstate):
    """
    test verify_tops when the environment is empty
    """
    tops = DefaultOrderedDict(OrderedDict)
    tops[""] = OrderedDict([("*", ["test", "test2"])])
    matches = highstate.verify_tops(tops)
    assert matches == ["Empty saltenv statement in top file"]


def test_verify_tops_sls_not_list(highstate):
    """
    test verify_tops when the sls files are not a list
    """
    tops = DefaultOrderedDict(OrderedDict)
    tops["base"] = OrderedDict([("*", "test test2")])
    matches = highstate.verify_tops(tops)
    # [] means there where no errors when verifying tops
    assert matches == ["Malformed topfile (state declarations not formed as a list)"]


def test_verify_tops_match(highstate):
    """
    test basic functionality of verify_tops when using a matcher
    like `match: glob`.
    """
    tops = DefaultOrderedDict(OrderedDict)
    tops["base"] = OrderedDict(
        [("*", [OrderedDict([("match", "glob")]), "test", "test2"])]
    )
    matches = highstate.verify_tops(tops)
    # [] means there where no errors when verifying tops
    assert matches == []


def test_verify_tops_match_none(highstate):
    """
    test basic functionality of verify_tops when using a matcher
    when it is empty, like `match: ""`.
    """
    tops = DefaultOrderedDict(OrderedDict)
    tops["base"] = OrderedDict([("*", [OrderedDict([("match", "")]), "test", "test2"])])
    matches = highstate.verify_tops(tops)
    assert "Improperly formatted top file matcher in saltenv" in matches[0]
