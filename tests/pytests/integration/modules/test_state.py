import logging
import subprocess

import pytest
from _pytest.outcomes import Failed
from _pytest.pytester import LineMatcher

log = logging.getLogger(__name__)


def test_logging_and_state_output_order(salt_master, salt_minion, salt_cli, tmp_path):
    """
    This tests for any regressions for this issue:
    https://github.com/saltstack/salt/issues/62005
    """
    target_path = tmp_path / "file-target.txt"
    sls_name = "file-target"
    sls_contents = """
    add_contents_pillar_sls:
      file.managed:
        - name: {}
        - contents: foo
    """.format(
        target_path
    )
    sls_tempfile = salt_master.state_tree.base.temp_file(
        f"{sls_name}.sls", sls_contents
    )
    with sls_tempfile:
        # Get the command line to use
        cmdline = salt_cli.cmdline(
            "-ldebug", "state.sls", sls_name, minion_tgt=salt_minion.id
        )
        assert cmdline
        # Use subprocess.run since we want the output of stdout(state output) and stderr(logging)
        # mixed so we can check for the order
        ret = subprocess.run(
            cmdline,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
            shell=False,
            text=True,
        )
        assert ret.stdout
        assert not ret.stderr
        log.debug("STDOUT:\n>>>>>>>>\n%s\n<<<<<<<\n", ret.stdout)
        matcher = LineMatcher(ret.stdout.splitlines())
        assert ret.returncode == 0
        assert target_path.is_file()
        # Check for proper order of state output and logging
        try:
            # This output order should not match and should trigger a _pytest.outcomes.Failed exception
            matcher.fnmatch_lines(
                [
                    f'"{salt_minion.id}":*',
                    '"file_*',
                    "*Reading configuration from*",
                ]
            )
        except Failed:
            # We caught the expected failure regarding the output matching above,
            # nonetheless, let's confirm proper output order
            matcher.fnmatch_lines(
                [
                    # Confirm we have logging going on...
                    "*Reading configuration from*",
                    # And that after logging, we have the state output
                    f'"{salt_minion.id}":*',
                    '"file_*',
                ]
            )
        else:
            pytest.fail("The state and logging output order is wrong")
