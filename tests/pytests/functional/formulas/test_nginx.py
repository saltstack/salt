"""
Tests using nginx formula
"""

import types

import pytest

from tests.pytests.functional.states.test_service import _check_systemctl

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
    return types.SimpleNamespace(name="nginx-formula", tag="2.8.1")


@pytest.mark.skipif(_check_systemctl(), reason="systemctl degraded")
def test_formula(modules):
    ret = modules.state.sls("nginx")
    assert not ret.errors
    assert ret.failed is False
    for staterun in ret:
        assert staterun.result is True
