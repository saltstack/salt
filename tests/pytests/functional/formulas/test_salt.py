"""
Tests using salt formula
"""

import pytest


@pytest.fixture(scope="module")
def _formula(saltstack_formula):
    with saltstack_formula(name="salt-formula", tag="1.12.0") as formula:
        yield formula


@pytest.fixture(scope="module")
def modules(loaders, _formula):
    return loaders.modules


@pytest.mark.destructive_test
def test_salt_formula(modules):
    # Master Formula
    ret = modules.state.sls("salt.master")
    for staterun in ret:
        assert not staterun.result.failed

    # Minion Formula
    ret = modules.state.sls("salt.minion")
    for staterun in ret:
        assert not staterun.result.failed
