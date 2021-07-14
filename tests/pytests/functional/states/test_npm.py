import pytest
from salt.exceptions import CommandExecutionError


@pytest.fixture(scope="module", autouse=True)
def install_npm(sminion):
    try:
        sminion.functions.pkg.install("npm")
        # Just name the thing we're looking for
        sminion.functions.npm  # pylint: disable=pointless-statement
    except (CommandExecutionError, AttributeError):
        pytest.skip("Unable to install npm")


@pytest.mark.slow_test
@pytest.mark.destructive_test
@pytest.mark.requires_network
def test_removed_installed_cycle(sminion):
    project_version = "pm2@5.1.0"
    success = sminion.functions.npm.uninstall("pm2")
    assert success, "Unable to uninstall pm2 in prep for tests"

    ret = next(
        iter(
            sminion.functions.state.single(
                "npm.installed", name=project_version
            ).values()
        )
    )
    success = ret["result"]
    assert success, "Failed to states.npm.installed " + project_version + ret["comment"]

    ret = next(
        iter(
            sminion.functions.state.single("npm.removed", name=project_version).values()
        )
    )
    success = ret["result"]
    assert success, "Failed to states.npm.removed " + project_version
