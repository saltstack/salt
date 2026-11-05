import pytest

import salt.state

pytestmark = [
    pytest.mark.core_test,
]


class _Client:
    def __init__(self, envs):
        self._envs = envs

    def envs(self):
        return self._envs


class _HighState:
    """
    Minimal stand-in exposing only what ``BaseHighState._get_envs`` and
    ``LazyAvailStates`` use.
    """

    _get_envs = salt.state.BaseHighState._get_envs

    def __init__(self, opts, client_envs):
        self.opts = opts
        self.client = _Client(client_envs)


@pytest.fixture
def fileserver_envs():
    return ["base", "prod", "staging", "dev", "feature/myfeature"]


@pytest.fixture
def highstate(fileserver_envs):
    opts = {"env_order": ["base", "prod", "staging", "dev"]}
    return _HighState(opts, fileserver_envs)


def test_get_envs_is_limited_to_env_order_by_default(highstate):
    """
    Top file evaluation relies on ``env_order`` limiting and ordering the envs.
    """
    assert highstate._get_envs() == ["base", "prod", "staging", "dev"]


def test_get_envs_unrestricted_includes_envs_outside_env_order(highstate):
    envs = highstate._get_envs(restrict_to_env_order=False)
    assert "feature/myfeature" in envs
    assert set(envs) == {"base", "prod", "staging", "dev", "feature/myfeature"}


def test_get_envs_unrestricted_without_fileserver_envs_uses_env_order():
    hs = _HighState({"env_order": ["base", "prod"]}, [])
    assert hs._get_envs(restrict_to_env_order=False) == ["base", "prod"]


def test_lazy_avail_states_contains_env_outside_env_order(highstate):
    """
    Regression test for #70618: an environment present on the fileserver but
    absent from ``env_order`` must still be considered available.
    """
    avail = salt.state.LazyAvailStates(highstate)
    assert "feature/myfeature" in avail
    assert "prod" in avail
    assert "does/not/exist" not in avail
