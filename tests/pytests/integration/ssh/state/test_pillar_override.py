"""
Ensure pillar overrides are merged recursively, that wrapper
modules are in sync with the pillar dict in the rendering environment
and that the pillars are available on the target.
"""

import json

import pytest

import salt.utils.dictupdate

pytestmark = [
    pytest.mark.skip_on_windows(reason="salt-ssh not available on Windows"),
    pytest.mark.usefixtures("pillar_tree_nested"),
    pytest.mark.slow_test,
]


def test_pillar_is_only_rendered_once_without_overrides(salt_ssh_cli, caplog):
    ret = salt_ssh_cli.run("state.apply", "test")
    assert ret.returncode == 0
    assert isinstance(ret.data, dict)
    assert ret.data
    assert ret.data[next(iter(ret.data))]["result"] is True
    assert caplog.text.count("hithere: pillar was rendered") == 1


def test_pillar_is_rerendered_with_overrides(salt_ssh_cli, caplog):
    ret = salt_ssh_cli.run("state.apply", "test", pillar={"foo": "bar"})
    assert ret.returncode == 0
    assert isinstance(ret.data, dict)
    assert ret.data
    assert ret.data[next(iter(ret.data))]["result"] is True
    assert caplog.text.count("hithere: pillar was rendered") == 2


@pytest.fixture(scope="module", autouse=True)
def _show_pillar_state(base_env_state_tree_root_dir):
    top_file = """
    base:
      'localhost':
        - showpillar
      '127.0.0.1':
        - showpillar
    """
    show_pillar_sls = """
    deep_thought:
      test.show_notification:
        - text: '{{ {
            "raw": {
              "the_meaning": pillar.get("the_meaning"),
              "btw": pillar.get("btw")},
            "wrapped": {
              "the_meaning": salt["pillar.get"]("the_meaning"),
              "btw": salt["pillar.get"]("btw")}}
            | json }}'

    target_check:
      test.check_pillar:
        - present:
          - the_meaning:of:foo
          - btw
          - the_meaning:of:bar
          - the_meaning:for
        - listing:
          - the_meaning:of:life
    """
    top_tempfile = pytest.helpers.temp_file(
        "top.sls", top_file, base_env_state_tree_root_dir
    )
    show_tempfile = pytest.helpers.temp_file(
        "showpillar.sls", show_pillar_sls, base_env_state_tree_root_dir
    )
    with top_tempfile, show_tempfile:
        yield


@pytest.fixture
def base():
    return {"the_meaning": {"of": {"life": 42, "bar": "tender"}, "for": "what"}}


@pytest.fixture
def override(base):
    poverride = {
        "the_meaning": {"of": {"life": [2.71], "foo": "lish"}},
        "btw": "turtles",
    }
    expected = salt.utils.dictupdate.merge(base, poverride)
    return expected, poverride


def test_state_sls(salt_ssh_cli, override):
    expected, override = override
    ret = salt_ssh_cli.run("state.sls", "showpillar", pillar=override)
    _assert_basic(ret)
    assert len(ret.data) == 2
    for sid, sret in ret.data.items():
        if "show" in sid:
            _assert_pillar(sret["comment"], expected)
        else:
            assert sret["result"] is True


@pytest.mark.parametrize("sid", ("deep_thought", "target_check"))
def test_state_sls_id(salt_ssh_cli, sid, override):
    expected, override = override
    ret = salt_ssh_cli.run("state.sls_id", sid, "showpillar", pillar=override)
    _assert_basic(ret)
    state_res = ret.data[next(iter(ret.data))]
    if sid == "deep_thought":
        _assert_pillar(state_res["comment"], expected)
    else:
        assert state_res["result"] is True


def test_state_highstate(salt_ssh_cli, override):
    expected, override = override
    ret = salt_ssh_cli.run("state.highstate", pillar=override, whitelist=["showpillar"])
    _assert_basic(ret)
    assert len(ret.data) == 2
    for sid, sret in ret.data.items():
        if "show" in sid:
            _assert_pillar(sret["comment"], expected)
        else:
            assert sret["result"] is True


def test_state_show_sls(salt_ssh_cli, override):
    expected, override = override
    ret = salt_ssh_cli.run("state.show_sls", "showpillar", pillar=override)
    _assert_basic(ret)
    pillar = ret.data["deep_thought"]["test"]
    pillar = next(x["text"] for x in pillar if isinstance(x, dict))
    _assert_pillar(pillar, expected)


def test_state_show_low_sls(salt_ssh_cli, override):
    expected, override = override
    ret = salt_ssh_cli.run("state.show_low_sls", "showpillar", pillar=override)
    _assert_basic(ret, list)
    pillar = ret.data[0]["text"]
    _assert_pillar(pillar, expected)


def test_state_single(salt_ssh_cli, override):
    expected, override = override
    ret = salt_ssh_cli.run(
        "state.single",
        "test.check_pillar",
        "foo",
        present=[
            "the_meaning:of:foo",
            "btw",
            "the_meaning:of:bar",
            "the_meaning:for",
        ],
        listing=["the_meaning:of:life"],
        pillar=override,
    )
    _assert_basic(ret, dict)
    state_res = ret.data[next(iter(ret.data))]
    assert state_res["result"] is True


def test_state_top(salt_ssh_cli, override):
    expected, override = override
    ret = salt_ssh_cli.run("state.top", "top.sls", pillar=override)
    _assert_basic(ret)
    assert len(ret.data) == 2
    for sid, sret in ret.data.items():
        if "show" in sid:
            _assert_pillar(sret["comment"], expected)
        else:
            assert sret["result"] is True


def _assert_pillar(pillar, expected):
    if not isinstance(pillar, dict):
        pillar = json.loads(pillar)
    assert pillar["raw"] == expected
    assert pillar["wrapped"] == expected


def _assert_basic(ret, typ=dict):
    assert ret.returncode == 0
    assert isinstance(ret.data, typ)
    assert ret.data
