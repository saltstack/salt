"""
``state.sls`` gives state modules the user that started an orchestration as
``__user__`` by setting it in the State's ``inject_globals``, without changing
``opts['user']`` (#63148, #70251). These tests check that a ``__user__`` set
there reaches every chunk of the run, whichever way the chunk is called.
"""

import textwrap

import pytest

import salt.state
from tests.support.mock import patch

pytestmark = [
    pytest.mark.core_test,
]


CAPTURE_STATE = textwrap.dedent(
    """
    def _ret(name, comment):
        # result None in test mode, so that prereq sees a pending change
        result = None if __opts__["test"] else True
        return {"name": name, "result": result, "changes": {"user": __user__}, "comment": comment}


    def run(name, **kwargs):
        return _ret(name, __user__)


    def nochange(name, **kwargs):
        return {"name": name, "result": True, "changes": {}, "comment": __user__}


    def fail(name, **kwargs):
        return {"name": name, "result": False, "changes": {}, "comment": __user__}


    def mod_watch(name, **kwargs):
        return _ret(name, "watch:" + __user__)
    """
)


@pytest.fixture
def state_obj(minion_opts, tmp_path):
    states_dir = tmp_path / "extmods" / "states"
    states_dir.mkdir(parents=True)
    (states_dir / "capture.py").write_text(CAPTURE_STATE)
    minion_opts["extension_modules"] = str(tmp_path / "extmods")
    minion_opts["user"] = "salt"
    with patch("salt.state.State._gather_pillar"):
        yield salt.state.State(minion_opts)


def _comments(ret):
    return {data["__id__"]: data["comment"] for data in ret.values()}


def _high(**states):
    high = {}
    for id_, args in states.items():
        high[id_] = {
            "capture": args,
            "__env__": "base",
            "__sls__": "orch",
        }
    return high


def test_user_defaults_to_opts_user(state_obj):
    ret = state_obj.call_high(_high(a=["run"]))
    assert _comments(ret) == {"a": "salt"}


def test_orchestration_user_is_dunder_user(state_obj):
    state_obj.inject_globals["__user__"] = "alice"
    ret = state_obj.call_high(_high(a=["run"]))
    assert _comments(ret) == {"a": "alice"}
    # The configured user is left alone.
    assert state_obj.opts["user"] == "salt"


def test_orchestration_user_with_requisites(state_obj):
    """
    Every chunk of the run sees the same user, including those run through
    watch (mod_watch), listen (mod_watch at the end of the run), onchanges,
    onfail and prereq.
    """
    state_obj.inject_globals["__user__"] = "alice"
    high = _high(
        a=["run"],
        b=["nochange"],
        watcher=["nochange", {"watch": [{"capture": "a"}]}],
        listener=["run", {"listen": [{"capture": "a"}]}],
        onchanged=["run", {"onchanges": [{"capture": "a"}]}],
        f=["fail"],
        onfailed=["run", {"onfail": [{"capture": "f"}]}],
        p=["run"],
        prereqd=["run", {"prereq": [{"capture": "p"}]}],
    )
    ret = state_obj.call_high(high)
    comments = _comments(ret)
    assert comments["a"] == "alice"
    assert comments["b"] == "alice"
    assert comments["watcher"] == "watch:alice"
    assert comments["onchanged"] == "alice"
    assert comments["f"] == "alice"
    assert comments["onfailed"] == "alice"
    assert comments["p"] == "alice"
    assert comments["prereqd"] == "alice"
    listen = [data["comment"] for tag, data in ret.items() if tag.endswith("mod_watch")]
    assert listen == ["watch:alice"]


@pytest.mark.skip_on_spawning_platform(
    reason="Skipped until parallel states can be fixed on spawning platforms."
)
def test_orchestration_user_in_parallel_state(state_obj):
    state_obj.inject_globals["__user__"] = "alice"
    state_obj.jid = "123"
    ret = state_obj.call_high(
        _high(p1=["run", {"parallel": True}], p2=["run", {"parallel": True}])
    )
    state_obj.jid = None
    assert _comments(ret) == {"p1": "alice", "p2": "alice"}


def test_parallel_spawn_gets_user_from_inject_globals(state_obj):
    """
    On spawning platforms the child rebuilds the State from ``_init_kwargs``
    and only gets the per-call globals, so ``__user__`` must already be in the
    globals handed to ``call_parallel``.
    """
    state_obj.inject_globals["__user__"] = "alice"
    seen = {}

    def _fake_call_parallel(cdata, low, inject_globals):
        seen.update(inject_globals)
        return {"name": low["name"], "result": True, "changes": {}, "comment": ""}

    with patch.object(state_obj, "call_parallel", _fake_call_parallel):
        state_obj.call_high(_high(p1=["run", {"parallel": True}]))
    assert seen["__user__"] == "alice"
