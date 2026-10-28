"""
Ensure execution module functions with positional-only and keyword-only
parameters are handled correctly.
"""

import pytest

pytestmark = [
    pytest.mark.slow_test,
]


@pytest.fixture(scope="module", autouse=True)
def arg_kinds_module(salt_master, salt_minion):
    contents = """
    def regular(first, second=2, third=3):
        return {"first": first, "second": second, "third": third}


    def kwonly(first, *, second, third="three"):
        return {"first": first, "second": second, "third": third}


    def kwonly_defaults(a, b=1, *, c):
        return {"a": a, "b": b, "c": c}


    def posonly(first, /, second="two"):
        return {"first": first, "second": second}


    def posonly_default(first, second="two", /, third="three"):
        return {"first": first, "second": second, "third": third}


    def posonly_kwargs(a=1, /, **kwargs):
        return {"a": a, "kwargs": {k: v for k, v in kwargs.items() if not k.startswith("__")}}


    def all_together(pos1, /, kwpos2, kwpos3="3", *args, kwreq, kwopt="opt", kwopt2="h", **kwargs):
        assert "__pub_fun" in kwargs, "no __pub_fun"
        assert "__pub_jid" in kwargs, "no __pub_jid"
        assert "__pub_pid" in kwargs, "no __pub_pid"
        assert "__pub_tgt" in kwargs, "no __pub_tgt"
        return {"pos1": pos1, "kwpos2": kwpos2, "kwpos3": kwpos3, "args": args, "kwreq": kwreq, "kwopt": kwopt, "kwopt2": kwopt2, "kwargs": {k: v for k, v in kwargs.items() if not k.startswith("__")}}
    """
    salt_call_cli = salt_minion.salt_call_cli()
    with salt_master.state_tree.base.temp_file("_modules/arg_kinds.py", contents):
        ret = salt_call_cli.run("saltutil.sync_modules")
        assert ret.returncode == 0
        yield
    ret = salt_call_cli.run("saltutil.sync_modules")
    assert ret.returncode == 0


def test_kwonly(salt_call_cli):
    ret = salt_call_cli.run("arg_kinds.kwonly", "one", "second=owt")
    assert ret.returncode == 0, ret
    assert ret.data == {"first": "one", "second": "owt", "third": "three"}


def test_kwonly_positional_rejected(salt_call_cli):
    ret = salt_call_cli.run("arg_kinds.kwonly", "one", "two", "four")
    assert ret.returncode > 0
    assert "takes 1 positional argument" in str(ret.data or ret.stderr)


def test_kwonly_defaults_are_applied_correctly(salt_call_cli):
    ret = salt_call_cli.run("arg_kinds.kwonly_defaults", "A", b="B")
    assert ret.returncode > 0
    assert "missing 1 required keyword-only" in str(ret.data or ret.stderr)


def test_posonly(salt_call_cli):
    ret = salt_call_cli.run("arg_kinds.posonly", "one")
    assert ret.returncode == 0
    assert ret.data == {"first": "one", "second": "two"}


def test_posonly_passed_by_name_rejected(salt_call_cli):
    ret = salt_call_cli.run("arg_kinds.posonly", "first=one")
    assert ret.returncode != 0
    assert "keyword arguments are not valid" in str(ret.data or ret.stderr)


def test_posonly_default(salt_call_cli):
    ret = salt_call_cli.run("arg_kinds.posonly_default", "one", third="eerht")
    assert ret.returncode == 0
    assert ret.data == {"first": "one", "second": "two", "third": "eerht"}


def test_posonly_with_kwargs(salt_call_cli):
    """
    Python allows ``def f(a, /, **kwargs)`` being called with ``f("first_a", a="other_a")``.
    Ensure we handle that case.
    """
    ret = salt_call_cli.run("arg_kinds.posonly_kwargs", "A", a="foo")
    assert ret.returncode == 0
    assert ret.data == {"a": "A", "kwargs": {"a": "foo"}}


def test_all_together(salt_call_cli):
    ret = salt_call_cli.run(
        "arg_kinds.all_together",
        "a",
        "b",
        "c",
        "d",
        "e",
        kwopt="g",
        kwreq="f",
        pos1="i",
        quux="j",
    )
    assert ret.returncode == 0
    assert ret.data == {
        "pos1": "a",
        "kwpos2": "b",
        "kwpos3": "c",
        "args": ["d", "e"],
        "kwreq": "f",
        "kwopt": "g",
        "kwopt2": "h",
        "kwargs": {"pos1": "i", "quux": "j"},
    }
