import subprocess
import time

import pytest
from pytestshellutils.exceptions import FactoryNotStarted

pytestmark = [
    pytest.mark.destructive_test,
    pytest.mark.skip_on_freebsd(reason="Daemons tests are flaky on FreeBSD"),
]


@pytest.mark.parametrize("cli_daemon_flag", ["-d", "--daemon"])
def test_salt_master_as_daemon(salt_master_factory, cli_daemon_flag):
    max_grep_tries = 5
    try:
        with salt_master_factory.started(
            cli_daemon_flag, start_timeout=120, max_start_attempts=1
        ):
            pass
    except FactoryNotStarted:
        pass
    finally:
        assert salt_master_factory.impl._terminal_result.stdout == ""
        assert salt_master_factory.impl._terminal_result.stderr == ""
        assert salt_master_factory.impl._terminal_result.returncode == 0

        # We are going to kill the possible child processes based on the entire cmdline
        # We know this is unique to these processes because of the unique name of the config files, for example
        cmdline = salt_master_factory.cmdline(cli_daemon_flag)
        pkill_proc = subprocess.Popen(
            ["pkill", "-f", " ".join(cmdline)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        ).communicate()
        assert pkill_proc[1] == b""
        for _ in range(max_grep_tries):
            pgrep_proc = subprocess.Popen(
                ["pgrep", "-f", " ".join(cmdline)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            ).communicate()
            if pgrep_proc[0] == b"" and pgrep_proc[1] == b"":
                break
            time.sleep(1)
        else:
            pytest.skip("Skipping this test because processes didn't kill in time.")


@pytest.mark.parametrize("cli_daemon_flag", ["-d", "--daemon"])
def test_salt_minion_as_daemon(salt_minion_factory, cli_daemon_flag):
    max_grep_tries = 5
    try:
        with salt_minion_factory.started(
            cli_daemon_flag, start_timeout=120, max_start_attempts=1
        ):
            pass
    except FactoryNotStarted:
        pass
    finally:
        assert salt_minion_factory.impl._terminal_result.stdout == ""
        assert salt_minion_factory.impl._terminal_result.stderr == ""
        assert salt_minion_factory.impl._terminal_result.returncode == 0

        # We are going to kill the possible child processes based on the entire cmdline
        # We know this is unique to these processes because of the unique name of the config files, for example
        cmdline = salt_minion_factory.cmdline(cli_daemon_flag)
        pkill_proc = subprocess.Popen(
            ["pkill", "-f", " ".join(cmdline)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        ).communicate()
        assert pkill_proc[1] == b""
        for _ in range(max_grep_tries):
            pgrep_proc = subprocess.Popen(
                ["pgrep", "-f", " ".join(cmdline)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            ).communicate()
            if pgrep_proc[0] == b"" and pgrep_proc[1] == b"":
                break
            time.sleep(1)
        else:
            pytest.skip("Skipping this test because processes didn't kill in time.")
