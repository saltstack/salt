"""
Tests for the cron state
"""

import logging
import subprocess

import pytest
import salt.utils.platform

log = logging.getLogger(__name__)


@pytest.fixture
def cron_account():
    with pytest.helpers.create_account() as system_account:
        try:
            yield system_account
        finally:
            command = ["crontab", "-u", system_account.username, "-r"]
            if salt.utils.platform.is_freebsd():
                command.append("-f")
            subprocess.run(command, check=False)


@pytest.mark.slow_test
@pytest.mark.skip_on_windows
@pytest.mark.skip_if_not_root
@pytest.mark.skip_if_binaries_missing("crontab")
def test_managed(cron_account, salt_cli, salt_minion, base_env_state_tree_root_dir):
    """
    file.managed
    """
    cron_contents = (
        "# Lines below here are managed by Salt, do not edit\n@hourly touch"
        " /tmp/test-file\n"
    )
    expected = (
        "--- \n+++ \n@@ -1 +1,2 @@\n-\n+# Lines below here are managed by Salt, do not"
        " edit\n+@hourly touch /tmp/test-file\n"
    )
    with pytest.helpers.temp_file(
        "issue-46881/cron", cron_contents, base_env_state_tree_root_dir
    ):
        ret = salt_cli.run(
            "state.single",
            "cron.file",
            name="salt://issue-46881/cron",
            user=cron_account.username,
            minion_tgt=salt_minion.id,
        )
    assert ret.exitcode == 0, ret
    state = ret.json["cron_|-salt://issue-46881/cron_|-salt://issue-46881/cron_|-file"]
    assert "changes" in state
    assert "diff" in state["changes"]
    assert state["changes"]["diff"] == expected
