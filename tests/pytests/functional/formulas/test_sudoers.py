"""
Tests using sudoers formula
"""

import pytest


@pytest.fixture(scope="module")
def _formula(saltstack_formula):
    with saltstack_formula(name="sudoers-formula", tag="0.25.0") as formula:
        yield formula


@pytest.fixture(scope="module")
def modules(loaders, _formula):
    loaders.opts["file_roots"]["base"].append(
        str(_formula.state_tree_path / f"{_formula.name}-{_formula.tag}")
    )
    return loaders.modules


@pytest.mark.skip_on_windows
@pytest.mark.destructive_test
def test_sudoers_formula(modules):
    ret = modules.state.sls("sudoers")
    assert not ret.errors
    assert ret.failed is False
    for staterun in ret:
        assert staterun.result is True
