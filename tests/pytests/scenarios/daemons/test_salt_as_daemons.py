import subprocess

import pytest
from pytestshellutils.exceptions import FactoryNotStarted
from pytestshellutils.utils.processes import terminate_process

pytestmark = [
    pytest.mark.destructive_test,
    pytest.mark.skip_on_freebsd(reason="Daemons tests are flaky on FreeBSD"),
]


def terminate_daemon(factory):
    # We are going to kill the possible child processes based on the unique config directory
    # We know this is unique to these processes because of the unique name of the config files
    config_dir = factory.config_dir
    pgrep_proc = subprocess.Popen(
        ["pgrep", "-f", str(config_dir)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stdout, _ = pgrep_proc.communicate()
    pids = [int(pid) for pid in stdout.decode().strip().split()]
    for pid in pids:
        try:
            terminate_process(pid, kill_children=True)
        except (OSError, RuntimeError):
            pass


@pytest.mark.parametrize("cli_daemon_flag", ["-d", "--daemon"])
def test_salt_master_as_daemon(salt_master_factory, cli_daemon_flag):
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
        terminate_daemon(salt_master_factory)


@pytest.mark.parametrize("cli_daemon_flag", ["-d", "--daemon"])
def test_salt_minion_as_daemon(salt_minion_factory, cli_daemon_flag):
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
        terminate_daemon(salt_minion_factory)
