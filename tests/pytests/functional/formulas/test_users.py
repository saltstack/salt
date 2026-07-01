"""
Tests using users formula
"""

import types

import pytest

pytestmark = [
    pytest.mark.skip_on_windows,
    pytest.mark.destructive_test,
    pytest.mark.timeout_unless_on_windows(240),
    pytest.mark.skipif(
        'grains["os_family"] == "Suse"',
        reason="Zypperpkg module removed as a part of great module migration",
    ),
]


@pytest.fixture(scope="module")
def formula():
    return types.SimpleNamespace(name="users-formula", tag="0.48.8")


def test_users_sudo_formula(modules):
    ret = modules.state.sls("users.sudo")
    assert not ret.errors
    assert ret.failed is False
    for staterun in ret:
        assert staterun.result is True


def test_users_bashrc_formula(modules):
    ret = modules.state.sls("users.bashrc")
    assert not ret.errors
    assert ret.failed is False
    for staterun in ret:
        assert staterun.result is True
