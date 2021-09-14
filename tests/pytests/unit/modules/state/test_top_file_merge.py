import sys
import textwrap

import pytest
import salt.modules.state as state
import salt.state
import salt.utils.files
import salt.utils.json
from tests.support.mock import MagicMock, patch

pytestmark = [
    pytest.mark.skipif(
        sys.version_info < (3, 6), reason="Dictionaries are not ordered under Py3.5"
    ),
]


@pytest.fixture
def configure_loader_modules(salt_minion_factory):
    return {
        state: {
            "__opts__": salt_minion_factory.config.copy(),
            "__salt__": {"saltutil.is_running": MagicMock(return_value=[])},
        },
    }


@pytest.fixture
def cachedir(tmp_path):
    path = tmp_path / "cache"
    path.mkdir()
    return path


@pytest.fixture
def fileserver_root(tmp_path):
    path = tmp_path / "fileserver-root"
    path.mkdir()
    return path


@pytest.fixture
def saltenvs():
    return ["base", "foo", "bar", "baz"]


@pytest.fixture
def saltenv_roots(fileserver_root, saltenvs):
    return {env: fileserver_root / env for env in saltenvs}


@pytest.fixture
def base_top_file(saltenv_roots):
    return str(saltenv_roots["base"] / "top.sls")


@pytest.fixture
def dunder_opts(saltenv_roots, saltenvs):
    return {
        "file_client": "local",
        "default_top": "base",
        "env_order": saltenv_roots,
        "file_roots": {
            "base": [str(saltenv_roots["base"])],
            "foo": [str(saltenv_roots["foo"])],
            "bar": [str(saltenv_roots["bar"])],
            "baz": [str(saltenv_roots["baz"])],
        },
    }


@pytest.fixture(autouse=True)
def state_tree(saltenv_roots, saltenvs):
    # Write top files for all but the "baz" environment
    for env, path in saltenv_roots.items():
        path.mkdir()
        if env == "baz":
            continue
        top_file = path / "top.sls"
        with salt.utils.files.fopen(str(top_file), "w") as fp_:
            # Add a section for every environment to each top file, with
            # the SLS target prefixed with the current saltenv.
            for env_name in saltenvs:
                fp_.write(
                    textwrap.dedent(
                        """\
                    {env_name}:
                      '*':
                        - {saltenv}_{env_name}
                    """.format(
                            env_name=env_name, saltenv=env
                        )
                    )
                )


@pytest.fixture
def limited_base_top_file(state_tree, base_top_file):
    with salt.utils.files.fopen(base_top_file, "w") as fp_:
        fp_.write(
            textwrap.dedent(
                """\
            base:
              '*':
                - base_base
            """
            )
        )


def show_top(dunder_opts, **kwargs):
    dunder_opts.update(kwargs)
    with patch.dict(state.__opts__, dunder_opts), patch.object(
        salt.state.State, "_gather_pillar", MagicMock(return_value={})
    ):
        ret = state.show_top()
        return ret


def test_merge_strategy_merge(dunder_opts):
    """
    Base overrides everything
    """
    ret = show_top(dunder_opts, top_file_merging_strategy="merge")
    assert ret == {
        "base": ["base_base"],
        "foo": ["base_foo"],
        "bar": ["base_bar"],
        "baz": ["base_baz"],
    }


@pytest.mark.usefixtures("limited_base_top_file")
def test_merge_strategy_merge_limited_base(dunder_opts, base_top_file):
    """
    Test with a "base" top file containing only a "base" section. The "baz"
    saltenv should not be in the return data because that env doesn't have
    its own top file and there will be no "baz" section in the "base" env's
    top file.

    Next, append a "baz" section to the rewritten top file and we should
    get results for that saltenv in the return data.
    """
    ret = show_top(dunder_opts, top_file_merging_strategy="merge")
    assert ret == {
        "base": ["base_base"],
        "foo": ["foo_foo"],
        "bar": ["bar_bar"],
    }

    # Add a "baz" section
    with salt.utils.files.fopen(base_top_file, "a") as fp_:
        fp_.write(
            textwrap.dedent(
                """\
            baz:
              '*':
                - base_baz
            """
            )
        )

    ret = show_top(dunder_opts, top_file_merging_strategy="merge")
    assert ret == {
        "base": ["base_base"],
        "foo": ["foo_foo"],
        "bar": ["bar_bar"],
        "baz": ["base_baz"],
    }


def test_merge_strategy_merge_state_top_saltenv_base(dunder_opts):
    """
    This tests with state_top_saltenv=base, which should pull states *only*
    from the base saltenv.
    """
    ret = show_top(
        dunder_opts, top_file_merging_strategy="merge", state_top_saltenv="base"
    )
    assert ret == {
        "base": ["base_base"],
        "foo": ["base_foo"],
        "bar": ["base_bar"],
        "baz": ["base_baz"],
    }


def test_merge_strategy_merge_state_top_saltenv_foo(dunder_opts):
    """
    This tests with state_top_saltenv=foo, which should pull states *only*
    from the foo saltenv. Since that top file is only authoritative for
    its own saltenv, *only* the foo saltenv's matches from the foo top file
    should be in the return data.
    """
    ret = show_top(
        dunder_opts, top_file_merging_strategy="merge", state_top_saltenv="foo"
    )
    assert ret == {"foo": ["foo_foo"]}


def test_merge_strategy_merge_all(dunder_opts):
    """
    Include everything in every top file
    """
    ret = show_top(dunder_opts, top_file_merging_strategy="merge_all")
    assert ret == {
        "base": ["base_base", "foo_base", "bar_base"],
        "foo": ["base_foo", "foo_foo", "bar_foo"],
        "bar": ["base_bar", "foo_bar", "bar_bar"],
        "baz": ["base_baz", "foo_baz", "bar_baz"],
    }


def test_merge_strategy_merge_all_alternate_env_order(dunder_opts):
    """
    Use an alternate env_order. This should change the order in which the
    SLS targets appear in the result.
    """
    ret = show_top(
        dunder_opts,
        top_file_merging_strategy="merge_all",
        env_order=["bar", "foo", "base"],
    )
    assert ret == {
        "base": ["bar_base", "foo_base", "base_base"],
        "foo": ["bar_foo", "foo_foo", "base_foo"],
        "bar": ["bar_bar", "foo_bar", "base_bar"],
        "baz": ["bar_baz", "foo_baz", "base_baz"],
    }


def test_merge_strategy_merge_all_state_top_saltenv_base(dunder_opts):
    """
    This tests with state_top_saltenv=base, which should pull states *only*
    from the base saltenv. Since we are using the "merge_all" strategy, all
    the states from that top file should be in the return data.
    """
    ret = show_top(
        dunder_opts, top_file_merging_strategy="merge_all", state_top_saltenv="base"
    )
    assert ret == {
        "base": ["base_base"],
        "foo": ["base_foo"],
        "bar": ["base_bar"],
        "baz": ["base_baz"],
    }


def test_merge_strategy_merge_all_state_top_saltenv_foo(dunder_opts):
    """
    This tests with state_top_saltenv=foo, which should pull states *only*
    from the foo saltenv. Since we are using the "merge_all" strategy, all
    the states from that top file should be in the return data.
    """
    ret = show_top(
        dunder_opts, top_file_merging_strategy="merge_all", state_top_saltenv="foo"
    )
    assert ret == {
        "base": ["foo_base"],
        "foo": ["foo_foo"],
        "bar": ["foo_bar"],
        "baz": ["foo_baz"],
    }


def test_merge_strategy_same(dunder_opts):
    """
    Each env should get its SLS targets from its own top file, with the
    "baz" env pulling from "base" since default_top=base and there is no
    top file in the "baz" saltenv.
    """
    ret = show_top(dunder_opts, top_file_merging_strategy="same")
    assert ret == {
        "base": ["base_base"],
        "foo": ["foo_foo"],
        "bar": ["bar_bar"],
        "baz": ["base_baz"],
    }


@pytest.mark.usefixtures("limited_base_top_file")
def test_merge_strategy_same_limited_base(dunder_opts):
    """
    Each env should get its SLS targets from its own top file, with the
    "baz" env pulling from "base" since default_top=base and there is no
    top file in the "baz" saltenv.
    """
    ret = show_top(dunder_opts, top_file_merging_strategy="same")
    assert ret == {
        "base": ["base_base"],
        "foo": ["foo_foo"],
        "bar": ["bar_bar"],
    }


def test_merge_strategy_same_default_top_foo(dunder_opts):
    """
    Each env should get its SLS targets from its own top file, with the
    "baz" env pulling from "foo" since default_top=foo and there is no top
    file in the "baz" saltenv.
    """
    ret = show_top(dunder_opts, top_file_merging_strategy="same", default_top="foo")
    assert ret == {
        "base": ["base_base"],
        "foo": ["foo_foo"],
        "bar": ["bar_bar"],
        "baz": ["foo_baz"],
    }


def test_merge_strategy_same_state_top_saltenv_base(dunder_opts):
    """
    Test the state_top_saltenv parameter to load states exclusively from
    the base saltenv, with the "same" merging strategy. This should
    result in just the base environment's states from the base top file
    being in the merged result.
    """
    ret = show_top(
        dunder_opts, top_file_merging_strategy="same", state_top_saltenv="base"
    )
    assert ret == {"base": ["base_base"]}


def test_merge_strategy_same_state_top_saltenv_foo(dunder_opts):
    """
    Test the state_top_saltenv parameter to load states exclusively from
    the foo saltenv, with the "same" merging strategy. This should
    result in just the foo environment's states from the foo top file
    being in the merged result.
    """
    ret = show_top(
        dunder_opts, top_file_merging_strategy="same", state_top_saltenv="foo"
    )
    assert ret == {"foo": ["foo_foo"]}


def test_merge_strategy_same_state_top_saltenv_baz(dunder_opts):
    """
    Test the state_top_saltenv parameter to load states exclusively from
    the baz saltenv, with the "same" merging strategy. This should
    result in an empty dictionary since there is no top file in that
    environment.
    """
    ret = show_top(
        dunder_opts, top_file_merging_strategy="same", state_top_saltenv="baz"
    )
    assert ret == {}
