import contextlib
import copy
import os

import pytest

import salt.config
import salt.utils.reactor
import salt.utils.user
from salt.runners import state as state_runner
from tests.support.mock import Mock, patch

REACTOR_SLS = """
run_orch:
  runner.state.orchestrate:
    - args:
      - mods: nested
"""

NESTED_SLS = """
nested_user:
  salt.runner:
    - name: config.get
    - key: user
"""


@pytest.fixture
def configure_loader_modules():
    return {state_runner: {"__opts__": {}, "__jid_event__": Mock()}}


def test_orchestrate_single_passes_pillar():
    """
    test state.orchestrate_single passes given pillar to state.single
    """
    mock_master_minion = Mock()
    mock_state_single = Mock()
    mock_master_minion.functions = {"state.single": mock_state_single}
    mock_master_minion.opts = {"id": "dummy"}
    test_pillar = {"test_entry": "exists"}
    with patch("salt.minion.MasterMinion", Mock(return_value=mock_master_minion)):
        state_runner.orchestrate_single(
            fun="pillar.get", name="test_entry", pillar=test_pillar
        )
        assert mock_state_single.call_args.kwargs["pillar"] == test_pillar


def test_orchestrate_single_does_not_pass_none_pillar():
    """
    test state.orchestrate_single does not pass pillar=None to state.single
    """
    mock_master_minion = Mock()
    mock_state_single = Mock()
    mock_master_minion.functions = {"state.single": mock_state_single}
    mock_master_minion.opts = {"id": "dummy"}
    with patch("salt.minion.MasterMinion", Mock(return_value=mock_master_minion)):
        state_runner.orchestrate_single(
            fun="pillar.get", name="test_entry", pillar=None
        )
        assert "pillar" not in mock_state_single.call_args.kwargs


def _orchestrate():
    mock_master_minion = Mock()
    mock_master_minion.functions = {"state.sls": Mock(return_value={})}
    mock_master_minion.opts = {"id": "dummy"}
    with patch.dict(state_runner.__opts__, {"user": "salt"}), patch.object(
        state_runner,
        "__utils__",
        {"state.check_result": Mock(return_value=True)},
        create=True,
    ), patch("salt.minion.MasterMinion", Mock(return_value=mock_master_minion)):
        state_runner.orchestrate("orch.test", orchestration_jid="123")
        assert state_runner.__opts__["user"] == "salt"
    return mock_master_minion.functions["state.sls"].call_args.kwargs


def test_orchestrate_passes_user_without_changing_opts():
    """
    The user that started the orchestration goes to the state run as
    ``orchestration_user``; ``__opts__['user']`` stays the master's configured
    user (#70251).
    """
    with patch.object(state_runner, "__user__", "alice", create=True):
        kwargs = _orchestrate()
    assert kwargs["orchestration_user"] == "alice"
    assert kwargs["orchestration_jid"] == "123"


def test_orchestrate_without_user_global():
    assert _orchestrate()["orchestration_user"] is None


class _Event:
    """
    Stands in for the master event bus and records the events fired on it.
    """

    def __init__(self, fired):
        self.fired = fired

    def fire_event(self, data, tag, timeout=None):
        self.fired.append((tag, copy.deepcopy(data)))
        return True

    def destroy(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class _InlinePool:
    """
    Stands in for the reactor's thread pool and runs each job right away.
    """

    def __init__(self, *args, **kwargs):
        pass

    def fire_async(self, func, args=None, kwargs=None):
        func(*(args or ()), **(kwargs or {}))
        return True


@pytest.fixture
def reactor_opts(master_opts, tmp_path):
    state_tree = tmp_path / "state_tree"
    state_tree.mkdir()
    (state_tree / "nested.sls").write_text(NESTED_SLS)
    pillar_tree = tmp_path / "pillar_tree"
    pillar_tree.mkdir()
    reactor_sls = tmp_path / "reactor.sls"
    reactor_sls.write_text(REACTOR_SLS)
    # RunnerClient.low writes the job's proc file here
    os.mkdir(os.path.join(master_opts["cachedir"], "proc"))
    master_opts.update(
        {
            "id": "master",
            # The account running the test, so saltutil.runner does not try
            # to drop privileges.
            "user": salt.utils.user.get_user(),
            "file_roots": {"base": [str(state_tree)]},
            "pillar_roots": {"base": [str(pillar_tree)]},
            "extension_modules": str(tmp_path / "extmods"),
            "reactor": [{"salt/run/*/new": [str(reactor_sls)]}],
            "quiet": True,
        }
    )
    with patch.object(salt.utils.reactor.ReactWrap, "client_cache", None):
        yield master_opts


def _react(opts, role=None):
    """
    React to one salt/run/<jid>/new event the way the reactor does. If
    ``role`` is given, every MasterMinion built while the reaction runs,
    including the one that state.orchestrate runs state.sls in, gets it as
    its ``__role``. Return the Reactor and the events that were fired.
    """
    fired = []
    mminion_config = salt.config.mminion_config

    def _event(*args, **kwargs):
        return _Event(fired)

    def _mminion_config(*args, **kwargs):
        mminion_opts = mminion_config(*args, **kwargs)
        mminion_opts["__role"] = role
        return mminion_opts

    mminion_role = contextlib.nullcontext()
    if role is not None:
        mminion_role = patch.object(salt.config, "mminion_config", _mminion_config)

    trigger = "salt/run/20261101000000000000/new"
    with patch("salt.utils.event.get_event", _event), patch(
        "salt.utils.event.get_master_event", _event
    ), patch("salt.utils.process.ThreadPool", _InlinePool):
        reactor = salt.utils.reactor.Reactor(opts)
        wrap = salt.utils.reactor.ReactWrap(opts)
        try:
            chunks = reactor.reactions(
                trigger,
                {"fun": "runner.test.arg", "user": "root"},
                reactor.list_reactors(trigger),
            )
            with mminion_role:
                for chunk in chunks:
                    wrap.run(chunk)
        finally:
            for client in wrap.client_cache.values():
                client.destroy()
            reactor.minion.destroy()
    succeeded = {
        data["fun"] for tag, data in fired if tag.endswith("/ret") and data["success"]
    }
    assert succeeded == {"runner.state.orchestrate", "runner.config.get"}, fired
    return reactor, fired


def _nested_events(fired):
    return [data for tag, data in fired if data.get("fun") == "runner.config.get"]


@pytest.mark.skip_on_windows(reason="Reactors unavailable on Windows")
def test_orchestrate_from_reactor_attributes_nested_runner(reactor_opts):
    """
    A runner started by a salt.runner state in an orchestration that the
    reactor started reports user ``Reactor``, so the reactor skips its events
    instead of reacting to them again. The master's user option is left alone
    (#70251).
    """
    configured_user = reactor_opts["user"]
    reactor, fired = _react(reactor_opts)
    new, ret = _nested_events(fired)
    assert new["user"] == ret["user"] == "Reactor"
    assert ret["return"] == configured_user
    # Reactor.run skips the events fired by ReactWrap.event_user
    reacted = [
        tag
        for tag, data in fired
        if data.get("user") != salt.utils.reactor.ReactWrap.event_user
        and reactor.list_reactors(tag)
    ]
    assert reacted == []


@pytest.mark.skip_on_windows(reason="Reactors unavailable on Windows")
def test_orchestrate_from_reactor_not_master_side(reactor_opts):
    """
    state.sls only takes the user from state.orchestrate when it runs
    master-side. When it does not, as with a reactor engine running in a
    minion, the nested runner job reports the configured user instead of
    ``Reactor``. Such a reactor does not see the job's events, which are
    fired on a master event bus, not on the minion bus it listens on.
    """
    configured_user = reactor_opts["user"]
    _, fired = _react(reactor_opts, role="minion")
    new, ret = _nested_events(fired)
    assert new["user"] == ret["user"] == configured_user
