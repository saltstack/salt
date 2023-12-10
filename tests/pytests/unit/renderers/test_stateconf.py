import io
import os
import os.path

import attr
import pytest

import salt.config
import salt.loader
from salt.exceptions import SaltRenderError

REQUISITES = ["require", "require_in", "use", "use_in", "watch", "watch_in"]


@attr.s
class Renderer:
    tmp_path = attr.ib()

    def __call__(
        self, content, sls="", saltenv="base", argline="-G yaml . jinja", **kws
    ):
        root_dir = self.tmp_path
        state_tree_dir = self.tmp_path / "state_tree"
        cache_dir = self.tmp_path / "cachedir"
        state_tree_dir.mkdir()
        cache_dir.mkdir()
        config = salt.config.minion_config(None)
        config["root_dir"] = str(root_dir)
        config["state_events"] = False
        config["id"] = "match"
        config["file_client"] = "local"
        config["file_roots"] = dict(base=[str(state_tree_dir)])
        config["cachedir"] = str(cache_dir)
        config["test"] = False
        _renderers = salt.loader.render(config, {"config.get": lambda a, b: False})
        return _renderers["stateconf"](
            io.StringIO(content),
            saltenv=saltenv,
            sls=sls,
            argline=argline,
            renderers=salt.loader.render(config, {}),
            **kws
        )


@pytest.fixture
def renderer(tmp_path):
    return Renderer(tmp_path)


def test_state_config(renderer):
    result = renderer(
        """
.sls_params:
  stateconf.set:
    - name1: value1
    - name2: value2

.extra:
  stateconf:
    - set
    - name: value

# --- end of state config ---

test:
  cmd.run:
    - name: echo name1={{sls_params.name1}} name2={{sls_params.name2}} {{extra.name}}
    - cwd: /
""",
        sls="test",
    )
    assert len(result) == 3
    assert "test::sls_params" in result and "test" in result
    assert "test::extra" in result
    assert (
        result["test"]["cmd.run"][0]["name"] == "echo name1=value1 name2=value2 value"
    )


def test_sls_dir(renderer):
    result = renderer(
        """
test:
  cmd.run:
    - name: echo sls_dir={{sls_dir}}
    - cwd: /
""",
        sls="path.to.sls",
    )
    assert result["test"]["cmd.run"][0]["name"] == "echo sls_dir=path{}to".format(
        os.sep
    )


def test_states_declared_with_shorthand_no_args(renderer):
    result = renderer(
        """
test:
  cmd.run:
    - name: echo testing
    - cwd: /
test1:
  pkg.installed
test2:
  user.present
"""
    )
    assert len(result) == 3
    for args in (result["test1"]["pkg.installed"], result["test2"]["user.present"]):
        assert isinstance(args, list)
        assert len(args) == 0
    assert result["test"]["cmd.run"][0]["name"] == "echo testing"


def test_adding_state_name_arg_for_dot_state_id(renderer):
    result = renderer(
        """
.test:
  pkg.installed:
    - cwd: /
.test2:
  pkg.installed:
    - name: vim
""",
        sls="test",
    )
    assert result["test::test"]["pkg.installed"][0]["name"] == "test"
    assert result["test::test2"]["pkg.installed"][0]["name"] == "vim"


def test_state_prefix(renderer):
    result = renderer(
        """
.test:
  cmd.run:
    - name: echo renamed
    - cwd: /

state_id:
  cmd:
    - run
    - name: echo not renamed
    - cwd: /
""",
        sls="test",
    )
    assert len(result) == 2
    assert "test::test" in result
    assert "state_id" in result


@pytest.mark.parametrize("req", REQUISITES)
def test_dot_state_id_in_requisites(req, renderer):
    result = renderer(
        """
.test:
  cmd.run:
    - name: echo renamed
    - cwd: /

state_id:
  cmd.run:
    - name: echo not renamed
    - cwd: /
    - {}:
      - cmd: .test

""".format(
            req
        ),
        sls="test",
    )
    assert len(result) == 2
    assert "test::test" in result
    assert "state_id" in result
    assert result["state_id"]["cmd.run"][2][req][0]["cmd"] == "test::test"


@pytest.mark.parametrize("req", REQUISITES)
def test_relative_include_with_requisites(req, renderer):
    result = renderer(
        """
include:
  - some.helper
  - .utils

state_id:
  cmd.run:
    - name: echo test
    - cwd: /
    - {}:
      - cmd: .utils::some_state
""".format(
            req
        ),
        sls="test.work",
    )
    assert result["include"][1] == {"base": "test.utils"}
    assert result["state_id"]["cmd.run"][2][req][0]["cmd"] == "test.utils::some_state"


def test_relative_include_and_extend(renderer):
    result = renderer(
        """
include:
  - some.helper
  - .utils

extend:
  .utils::some_state:
    cmd.run:
      - name: echo overridden
    """,
        sls="test.work",
    )
    assert "test.utils::some_state" in result["extend"]


@pytest.mark.parametrize("req", REQUISITES)
def test_multilevel_relative_include_with_requisites(req, renderer):
    result = renderer(
        """
include:
  - .shared
  - ..utils
  - ...helper

state_id:
  cmd.run:
    - name: echo test
    - cwd: /
    - {}:
      - cmd: ..utils::some_state
""".format(
            req
        ),
        sls="test.nested.work",
    )
    assert result["include"][0] == {"base": "test.nested.shared"}
    assert result["include"][1] == {"base": "test.utils"}
    assert result["include"][2] == {"base": "helper"}
    assert result["state_id"]["cmd.run"][2][req][0]["cmd"] == "test.utils::some_state"


def test_multilevel_relative_include_beyond_top_level(renderer):
    pytest.raises(
        SaltRenderError,
        renderer,
        """
include:
  - ...shared
""",
        sls="test.work",
    )


def test_start_state_generation(renderer):
    result = renderer(
        """
A:
  cmd.run:
    - name: echo hello
    - cwd: /
B:
  cmd.run:
    - name: echo world
    - cwd: /
""",
        sls="test",
        argline="-so yaml . jinja",
    )
    assert len(result) == 4
    assert result["test::start"]["stateconf.set"][0]["require_in"][0]["cmd"] == "A"


def test_goal_state_generation(renderer):
    result = renderer(
        """
{% for sid in "ABCDE": %}
{{sid}}:
  cmd.run:
    - name: echo this is {{sid}}
    - cwd: /
{% endfor %}

""",
        sls="test.goalstate",
        argline="yaml . jinja",
    )
    assert len(result) == len("ABCDE") + 1

    reqs = result["test.goalstate::goal"]["stateconf.set"][0]["require"]
    assert {next(iter(i.values())) for i in reqs} == set("ABCDE")


def test_implicit_require_with_goal_state(renderer):
    result = renderer(
        """
{% for sid in "ABCDE": %}
{{sid}}:
  cmd.run:
    - name: echo this is {{sid}}
    - cwd: /
{% endfor %}

F:
  cmd.run:
    - name: echo this is F
    - cwd: /
    - require:
      - cmd: A
      - cmd: B

G:
  cmd.run:
    - name: echo this is G
    - cwd: /
    - require:
      - cmd: D
      - cmd: F
""",
        sls="test",
        argline="-o yaml . jinja",
    )

    sids = "ABCDEFG"[::-1]
    for i, sid in enumerate(sids):
        if i < len(sids) - 1:
            assert result[sid]["cmd.run"][2]["require"][0]["cmd"] == sids[i + 1]

    F_args = result["F"]["cmd.run"]
    assert len(F_args) == 3
    F_req = F_args[2]["require"]
    assert len(F_req) == 3
    assert F_req[1]["cmd"] == "A"
    assert F_req[2]["cmd"] == "B"

    G_args = result["G"]["cmd.run"]
    assert len(G_args) == 3
    G_req = G_args[2]["require"]
    assert len(G_req) == 3
    assert G_req[1]["cmd"] == "D"
    assert G_req[2]["cmd"] == "F"

    goal_args = result["test::goal"]["stateconf.set"]
    assert len(goal_args) == 1
    assert [next(iter(i.values())) for i in goal_args[0]["require"]] == list("ABCDEFG")


def test_slsdir(renderer):
    result = renderer(
        """
formula/woot.sls:
  cmd.run:
    - name: echo {{ slspath }}
    - cwd: /
""",
        sls="formula.woot",
        argline="yaml . jinja",
    )

    r = result["formula/woot.sls"]["cmd.run"][0]["name"]
    assert r == "echo formula/woot"
