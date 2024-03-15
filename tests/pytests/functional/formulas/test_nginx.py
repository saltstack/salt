"""
Tests using nginx formula
"""

import pytest

pytestmark = [
    pytest.mark.timeout_unless_on_windows(120),
]


@pytest.fixture(scope="module")
def _formula(saltstack_formula):
    with saltstack_formula(name="nginx-formula", tag="2.8.1") as formula:
        yield formula


@pytest.fixture(scope="module")
def modules(loaders, _formula):
    loaders.opts["file_roots"]["base"].append(
        str(_formula.state_tree_path / f"{_formula.name}-{_formula.tag}")
    )
    return loaders.modules


@pytest.mark.skip_on_windows
@pytest.mark.destructive_test
def test_formula(modules):
    ret = modules.state.sls("nginx")
    assert not ret.errors
    assert not ret.failed
    for staterun in ret:
        assert staterun.result is True
