import pytest
from salt.exceptions import CommandExecutionError


@pytest.fixture(scope="module", autouse=True)
def install_npm(sminion):
    try:
        sminion.functions.state.single("pkg.installed", name="npm")
        # Just name the thing we're looking for
        sminion.functions.npm  # pylint: disable=pointless-statement
    except (CommandExecutionError, AttributeError) as e:
        pytest.skip("Unable to install npm - " + str(e))


@pytest.mark.slow_test
@pytest.mark.destructive_test
@pytest.mark.requires_network
def test_removed_installed_cycle(states, modules):
    project_version = "pm2@5.1.0"
    success = modules.npm.uninstall("pm2")
    assert success, "Unable to uninstall pm2 in prep for tests"

    ret = states.npm.installed(name=project_version)
    assert ret.result is True, "Failed to states.npm.installed {} - {}".format(
        project_version, ret.comment
    )

    ret = states.npm.removed(name=project_version)
    assert ret.result is True, "Failed to states.npm.removed {} - {}".format(
        project_version, ret.comment
    )
