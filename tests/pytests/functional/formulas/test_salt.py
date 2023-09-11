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


@pytest.mark.skip_on_windows
@pytest.mark.destructive_test
# These installation issues need to be resolved in the Salt formula, and then
# we can update the tag in here and remove the skips
@pytest.mark.skipif(
    'grains["osfullname"] in ("AlmaLinux", "Amazon Linux")',
    reason="No salt packages available for this distrubition",
)
@pytest.mark.skipif(
    'grains["os"] == "CentOS"',
    reason="No salt packages available for this distrubition",
)
@pytest.mark.skipif(
    'grains["os_family"] == "Arch"',
    reason="Outdated archlinux-keyring package will cause failed package installs",
)
def test_salt_formula(modules):
    # Master Formula
    ret = modules.state.sls("salt.master")
    for staterun in ret:
        assert not staterun.result.failed

    # Minion Formula
    ret = modules.state.sls("salt.minion")
    for staterun in ret:
        assert not staterun.result.failed
