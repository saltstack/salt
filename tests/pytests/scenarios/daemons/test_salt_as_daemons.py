import subprocess

import pytest
from pytestshellutils.exceptions import FactoryNotStarted

pytestmark = [
    pytest.mark.destructive_test,
]


def test_salt_master_as_daemon(salt_master_factory):
    for cli_option in ("-d", "--daemon"):
        try:
            with salt_master_factory.started(
                cli_option, start_timeout=120, max_start_attempts=1
            ):
                pass
        except FactoryNotStarted:
            pass
        finally:
            # We are going to kill the possible child processes based on the entire cmdline
            # We know this is unique to these processes because of the unique name of the config files, for example
            cmdline = salt_master_factory.cmdline(cli_option)
            pkill_proc = subprocess.Popen(
                ["pkill", "-f", " ".join(cmdline)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            ).communicate()
            assert pkill_proc[1] == b""

        assert salt_master_factory.impl._terminal_result.stdout == ""
        assert salt_master_factory.impl._terminal_result.stderr == ""
        assert salt_master_factory.impl._terminal_result.returncode == 0


def test_salt_minion_as_daemon(salt_minion_factory):
    for cli_option in ("-d", "--daemon"):
        try:
            with salt_minion_factory.started(
                cli_option, start_timeout=120, max_start_attempts=1
            ):
                pass
        except FactoryNotStarted:
            pass
        finally:
            # We are going to kill the possible child processes based on the entire cmdline
            # We know this is unique to these processes because of the unique name of the config files, for example
            cmdline = salt_minion_factory.cmdline(cli_option)
            pkill_proc = subprocess.Popen(
                ["pkill", "-f", " ".join(cmdline)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            ).communicate()
            assert pkill_proc[1] == b""

        assert salt_minion_factory.impl._terminal_result.stdout == ""
        assert salt_minion_factory.impl._terminal_result.stderr == ""
        assert salt_minion_factory.impl._terminal_result.returncode == 0
