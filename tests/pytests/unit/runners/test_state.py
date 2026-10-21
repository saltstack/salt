import pytest

from salt.runners import state as state_runner
from tests.support.mock import Mock, patch


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
