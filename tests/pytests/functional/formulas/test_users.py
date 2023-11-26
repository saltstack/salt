"""
Tests using users formula
"""

import pytest


@pytest.fixture(scope="module")
def _formula(saltstack_formula):
    with saltstack_formula(name="users-formula", tag="0.48.8") as formula:
        yield formula


@pytest.fixture(scope="module")
def modules(loaders, _formula):
    loaders.opts["file_roots"]["base"].append(
        str(_formula.state_tree_path / f"{_formula.name}-{_formula.tag}")
    )
    return loaders.modules


@pytest.mark.skip_on_windows
@pytest.mark.destructive_test
def test_users_formula(modules):
    # sudo
    ret = modules.state.sls("users.sudo")
    assert not ret.errors
    assert not ret.failed
    for staterun in ret:
        assert staterun.result is True

    # bashrc
    ret = modules.state.sls("users.bashrc")
    for staterun in ret:
        assert not staterun.result.failed
    assert not ret.errors
    assert not ret.failed
    for staterun in ret:
        assert staterun.result is True
