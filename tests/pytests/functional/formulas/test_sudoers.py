"""
Tests using sudoers formula
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
    return types.SimpleNamespace(name="sudoers-formula", tag="0.25.0")


def test_sudoers_formula(modules):
    ret = modules.state.sls("sudoers")
    assert not ret.errors
    assert ret.failed is False
    for staterun in ret:
        assert staterun.result is True
