"""
Tests using nginx formula
"""

import types

import pytest

pytestmark = [
    pytest.mark.skip_on_windows,
    pytest.mark.destructive_test,
    pytest.mark.timeout_unless_on_windows(240),
]


@pytest.fixture(scope="module")
def formula():
    return types.SimpleNamespace(name="nginx-formula", tag="2.8.1")


def test_formula(modules):
    ret = modules.state.sls("nginx")
    assert not ret.errors
    assert ret.failed is False
    for staterun in ret:
        assert staterun.result is True
