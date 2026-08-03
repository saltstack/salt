"""
Ensure state module functions with positional-only and keyword-only
parameters are handled correctly.

Also ensure module.run works with these param kinds.
"""

import pytest

from tests.pytests.integration.modules.test_arg_kinds import (  # pylint: disable=unused-import
    arg_kinds_module,
)

pytestmark = [
    pytest.mark.slow_test,
]


@pytest.fixture(scope="module", autouse=True)
def arg_kinds_state(salt_master, salt_minion):
    contents = """
    def kwonly(name, first, *, second, third="three"):
        return {"name": name, "result": True, "comment": "", "changes": {"first": first, "second": second, "third": third}}


    def kwonly_defaults(name, a, b=1, *, c):
        return {"name": name, "result": True, "comment": "", "changes": {"a": a, "b": b, "c": c}}


    def posonly(name, first, /, second, third="three"):
        return {"name": name, "result": True, "comment": "", "changes": {"first": first, "second": second, "third": third}}


    def posonly_default(name, first, second="two", /, third="three"):
        return {"name": name, "result": True, "comment": "", "changes": {"first": first, "second": second, "third": third}}


    def posonly_kwargs(name, a=1, /, **kwargs):
        return {"name": name, "result": True, "comment": "", "changes": {"a": a, "kwargs": {k: v for k, v in kwargs.items() if not k.startswith("__")}}}
    """
    salt_call_cli = salt_minion.salt_call_cli()
    with salt_master.state_tree.base.temp_file("_states/arg_kinds.py", contents):
        ret = salt_call_cli.run("saltutil.sync_states")
        assert ret.returncode == 0
        assert "states.arg_kinds" in ret.data
        yield
    ret = salt_call_cli.run("saltutil.sync_states")
    assert ret.returncode == 0


def test_kwonly(salt_call_cli, salt_master):
    contents = """
    foo:
      arg_kinds.kwonly:
        - first: one
        - second: two
    """
    with salt_master.state_tree.base.temp_file("kwonly.sls", contents):
        ret = salt_call_cli.run("state.apply", "kwonly")
    assert ret.returncode == 0, ret
    assert ret.data[next(iter(ret.data))]["changes"] == {
        "first": "one",
        "second": "two",
        "third": "three",
    }


def test_kwonly_defaults(salt_call_cli, salt_master):
    contents = """
    foo:
      arg_kinds.kwonly_defaults:
        - a: a
        - c: c
    """
    with salt_master.state_tree.base.temp_file("kwonly_defaults.sls", contents):
        ret = salt_call_cli.run("state.apply", "kwonly_defaults")
    assert ret.returncode == 0, ret
    assert ret.data[next(iter(ret.data))]["changes"] == {
        "a": "a",
        "b": 1,
        "c": "c",
    }


def test_kwonly_defaults_required_kwonly_missing(salt_call_cli, salt_master):
    contents = """
    foo:
      arg_kinds.kwonly_defaults:
        - a: one
        - b: two
    """
    with salt_master.state_tree.base.temp_file("kwonly_defaults_miss.sls", contents):
        ret = salt_call_cli.run("state.apply", "kwonly_defaults_miss")
    assert ret.returncode != 0, ret
    assert any(
        "missing 1 required keyword-only" in stream
        for stream in (ret.stdout, ret.stderr)
    )


def test_posonly(salt_call_cli, salt_master):
    contents = """
    foo:
      arg_kinds.posonly:
        - first: one
        - second: owt
    """
    with salt_master.state_tree.base.temp_file("posonly.sls", contents):
        ret = salt_call_cli.run("state.apply", "posonly")
    assert ret.returncode == 0, ret
    assert ret.data[next(iter(ret.data))]["changes"] == {
        "first": "one",
        "second": "owt",
        "third": "three",
    }


def test_posonly_with_kwargs(salt_call_cli, salt_master):
    """
    Python allows ``def f(a, /, **kwargs)`` being called with ``f("first_a", a="other_a")``.
    Ensure we handle that case somehow in states, where posargs don't exist:
    Since the high data is compiled into low chunk dicts, we can only drop
    the kwarg and ensure the posarg is passed.
    """
    contents = """
    foo:
      arg_kinds.posonly_kwargs:
        - a: a
        - a: foo
    """
    with salt_master.state_tree.base.temp_file("posonly_kwargs.sls", contents):
        ret = salt_call_cli.run("state.apply", "posonly_kwargs")
    assert ret.returncode == 0
    assert ret.data[next(iter(ret.data))]["changes"] == {
        "a": "foo",
        "kwargs": {},
    }


def test_module_run_positional_params(salt_call_cli, salt_master):
    """
    Ensure module.run works when passing positional params to args with defaults.
    """
    contents = """
    foo:
      module.run:
        - arg_kinds.regular:
            - 10
            - 20
            - 30
    """
    with salt_master.state_tree.base.temp_file("pos_param_mr.sls", contents):
        ret = salt_call_cli.run("state.apply", "pos_param_mr")
    assert ret.returncode == 0
    assert ret.data[next(iter(ret.data))]["changes"]["arg_kinds.regular"] == {
        "first": 10,
        "second": 20,
        "third": 30,
    }


def test_module_run_with_posonly(salt_call_cli, salt_master):
    """
    Ensure posonly args specified as posargs work.
    """
    contents = """
    foo:
      module.run:
        - arg_kinds.posonly:
            - foo
    """
    with salt_master.state_tree.base.temp_file("posonly_mr.sls", contents):
        ret = salt_call_cli.run("state.apply", "posonly_mr")
    assert ret.returncode == 0
    assert ret.data[next(iter(ret.data))]["changes"]["arg_kinds.posonly"] == {
        "first": "foo",
        "second": "two",
    }


def test_module_run_with_posonly_and_kwargs_containing_same_name(
    salt_call_cli, salt_master
):
    """
    Python allows ``def f(a, /, **kwargs)`` being called with ``f("first_a", a="other_a")``.
    Ensure we handle that case.
    """
    contents = """
    foo:
      module.run:
        - arg_kinds.posonly_kwargs:
          - foo
          - a: bar
    """
    with salt_master.state_tree.base.temp_file("posonly_kwargs_mr.sls", contents):
        ret = salt_call_cli.run("state.apply", "posonly_kwargs_mr")
    assert ret.returncode == 0
    assert ret.data[next(iter(ret.data))]["changes"]["arg_kinds.posonly_kwargs"] == {
        "a": "foo",
        "kwargs": {"a": "bar"},
    }


def test_module_run_with_required_kwonly_missing(salt_call_cli, salt_master):
    """
    Ensure defaults are mapped correctly when a required kwarg-only param
    follows a regular one with a default.
    """
    contents = """
    foo:
      module.run:
        - arg_kinds.kwonly_defaults:
          - a: A
          - b: B
    """
    with salt_master.state_tree.base.temp_file("kwonly_defaults_mr.sls", contents):
        ret = salt_call_cli.run("state.apply", "kwonly_defaults_mr")
    assert ret.returncode > 0
    assert "missing 1 required" in ret.data[next(iter(ret.data))]["comment"]
