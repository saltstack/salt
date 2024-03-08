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
    loaders.opts["file_roots"]["base"].append(
        str(_formula.state_tree_path / f"{_formula.name}-{_formula.tag}")
    )
    return loaders.modules


@pytest.fixture(scope="module")
def minion_config_defaults():
    return {
        "pillar": {
            "salt": {
                "py_ver": "salt/py3",
            }
        }
    }


@pytest.mark.skip_on_windows
@pytest.mark.destructive_test
# These installation issues need to be resolved in the Salt formula, and then
# we can update the tag in here and remove the skips
@pytest.mark.skipif(
    'grains["os_family"] == "Arch"',
    reason="Outdated archlinux-keyring package will cause failed package installs",
)
@pytest.mark.skipif(
    'grains["os_family"] == "RedHat" and grains["osmajorrelease"] == 9',
    reason="salt-formula points to incorrect GPG URL",
)
@pytest.mark.skipif(
    'grains["osfinger"] == "Debian-10"',
    reason="salt-formula uses wrong URL for Debian 10",
)
@pytest.mark.skipif(
    'grains["osfinger"] == "Leap-15"',
    reason="salt-formula points to missing Leap-15 metadata",
)
@pytest.mark.skipif(
    'grains["oscodename"] == "Photon"',
    reason="Photon OS not supported by salt-formula",
)
def test_salt_formula(modules):
    # Repo Formula
    ret = modules.state.sls("salt.pkgrepo")
    assert not ret.errors
    assert ret.failed is False
    for staterun in ret:
        assert staterun.result is True

    # Master Formula
    ret = modules.state.sls("salt.master")
    assert not ret.errors
    assert ret.failed is False
    for staterun in ret:
        assert staterun.result is True

    # Minion Formula
    ret = modules.state.sls("salt.minion")
    assert not ret.errors
    assert ret.failed is False
    for staterun in ret:
        assert staterun.result is True
