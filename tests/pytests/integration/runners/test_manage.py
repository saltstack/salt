import pytest


@pytest.fixture
def blackout_minion(salt_minion, salt_master, salt_run_cli):
    with pytest.helpers.temp_file(
        "top.sls",
        """base:\n  '*':\n    - fnord""",
        salt_master.pillar_tree.base.temp_file,
    ), pytest.helpers.temp_file(
        "fnord.sls", """minion_blackout: True""", salt_master.pillar_tree.base.paths[0]
    ):
        op = salt_run_cli.run("saltutil.sync_all")
        yield op


@pytest.fixture
def non_blackout_minion(salt_minion, salt_master, salt_call_cli):
    with pytest.helpers.temp_file(
        "top.sls",
        """base:\n  '*':\n    - fnord""",
        salt_master.pillar_tree.base.paths[0],
    ), pytest.helpers.temp_file(
        "fnord.sls", """minion_blackout: False""", salt_master.pillar_tree.base.paths[0]
    ):
        op = salt_call_cli.run("saltutil.refresh_pillar")
        # Refresh pillar appears to return too quickly. This call ensures that
        # we wait until the pillar refresh gets the correct value in there.
        op = salt_call_cli.run("pillar.get", "minion_blackout")
        yield op


def test_when_manage_versions_runs_and_the_minion_errors_out_it_should_not_(
    salt_run_cli, blackout_minion
):
    op = salt_run_cli.run("manage.versions")
    assert "Unable to parse version string" not in op.stdout


def test_when_manage_versions_runs_and_the_minion_does_not_error_it_should_have_version_info(
    salt_run_cli, non_blackout_minion
):
    op = salt_run_cli.run("manage.versions")
    result = op.stdout
    assert "Up to date" in result
