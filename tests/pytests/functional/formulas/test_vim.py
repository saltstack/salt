"""
Tests using vim formula
"""

import types

import pytest

pytestmark = [
    pytest.mark.skip_on_windows,
    pytest.mark.destructive_test,
    pytest.mark.timeout_unless_on_windows(240),
]


@pytest.fixture(scope="module")
def formula(grains):
    if grains["oscodename"] == "Photon":
        pytest.skip(reason="vim package not available for this distribution")
    return types.SimpleNamespace(name="vim-formula", tag="0.15.5")


def test_vim_formula(modules):
    ret = modules.state.sls("vim")
    assert not ret.errors
    assert ret.failed is False
    for staterun in ret:
        assert staterun.result is True
