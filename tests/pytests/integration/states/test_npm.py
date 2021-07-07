import pytest


@pytest.fixture(scope="package", autouse=True)
def install_npm(salt_cli, salt_minion):
    result = salt_cli.run("pkg.install", "npm", minion_tgt=salt_minion.id)
    if result.exitcode != 0:
        pytest.skip("npm could not be installed")


@pytest.mark.slow_test
@pytest.mark.destructive_test
@pytest.mark.requires_network
def test_removed_installed_cycle(salt_cli, salt_minion, base_env_state_tree_root_dir):
    project_version = "pm2@5.1.0"
    result = salt_cli.run("npm.uninstall", "pm2", minion_tgt=salt_minion.id)
    assert result.exitcode == 0, "Unable to remove pm2 in prep for tests"

    result = salt_cli.run(
        "state.single",
        "npm.installed",
        name=project_version,
        minion_tgt=salt_minion.id,
    )
    assert result.exitcode == 0, "Failed to install " + project_version

    result = salt_cli.run(
        "state.single", "npm.removed", name=project_version, minion_tgt=salt_minion.id,
    )
    assert result.exitcode == 0, "Failed to remove " + project_version
