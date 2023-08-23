"""
Tests using nginx formula
"""
import pytest


@pytest.fixture(scope="module")
def _formula(saltstack_formula):
    with saltstack_formula(name="nginx-formula", tag="2.8.1") as formula:
        yield formula


@pytest.fixture(scope="module")
def modules(loaders, _formula):
    return loaders.modules


@pytest.mark.destructive_test
def test_formula(modules):
    ret = modules.state.sls("nginx")
    for staterun in ret:
        assert staterun.result is True
