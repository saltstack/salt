"""
Tests using docker formula
"""

import pytest


@pytest.fixture(scope="module")
def _formula(saltstack_formula):
    with saltstack_formula(name="docker-formula", tag="2.4.2") as formula:
        yield formula


@pytest.fixture(scope="module")
def modules(loaders, _formula):
    return loaders.modules


@pytest.mark.skip_on_windows
@pytest.mark.destructive_test
def test_docker_formula(modules):
    ret = modules.state.sls("docker")
    for staterun in ret:
        assert not staterun.result.failed
