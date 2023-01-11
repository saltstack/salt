import subprocess
import time

import pytest
from pytestshellutils.exceptions import FactoryNotStarted

from salt.utils.platform import is_freebsd

pytestmark = [
    pytest.mark.destructive_test,
    pytest.mark.skipif(is_freebsd(), reason="Daemons tests are flaky on FreeBSD"),
]


def test_salt_master_as_daemon(salt_master_factory):
    max_grep_tries = 5
    for cli_option in ("-d", "--daemon"):
        try:
            with salt_master_factory.started(
                cli_option, start_timeout=120, max_start_attempts=1
            ):
                pass
        except FactoryNotStarted:
            pass
        finally:
            assert salt_master_factory.impl._terminal_result.stdout == ""
            # TODO currently setproctitle.getproctitle warns on some platforms.
            # It's fine, actually, for that warning to show up, until the
            # correct versions are configured for those platforms. When they
            # are, the 'if not all(...):' line should be removed and just the
            # assertion that `stderr == ""` should be left.
            if not any(
                (
                    all(
                        text in salt_master_factory.impl._terminal_result.stderr
                        for text in ("PY_SSIZE_T_CLEAN", "salt/utils/process.py:54")
                    ),
                    all(
                        text in salt_master_factory.impl._terminal_result.stderr
                        for text in (
                            "salt/utils/jinja.py:736",
                            "contextfunction",
                            "pass_context",
                        )
                    ),
                )
            ):
                assert salt_master_factory.impl._terminal_result.stderr == ""
            assert salt_master_factory.impl._terminal_result.returncode == 0

            # We are going to kill the possible child processes based on the entire cmdline
            # We know this is unique to these processes because of the unique name of the config files, for example
            cmdline = salt_master_factory.cmdline(cli_option)
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


def test_salt_minion_as_daemon(salt_minion_factory):
    max_grep_tries = 5
    for cli_option in ("-d", "--daemon"):
        try:
            with salt_minion_factory.started(
                cli_option, start_timeout=120, max_start_attempts=1
            ):
                pass
        except FactoryNotStarted:
            pass
        finally:
            assert salt_minion_factory.impl._terminal_result.stdout == ""
            # TODO currently setproctitle.getproctitle warns on some platforms.
            # It's fine, actually, for that warning to show up, until the
            # correct versions are configured for those platforms. When they
            # are, the 'if not all(...):' line should be removed and just the
            # assertion that `stderr == ""` should be left.
            if not any(
                (
                    all(
                        text in salt_minion_factory.impl._terminal_result.stderr
                        for text in ("PY_SSIZE_T_CLEAN", "salt/utils/process.py:54")
                    ),
                    all(
                        text in salt_minion_factory.impl._terminal_result.stderr
                        for text in (
                            "salt/utils/jinja.py:736",
                            "contextfunction",
                            "pass_context",
                        )
                    ),
                )
            ):
                assert salt_minion_factory.impl._terminal_result.stderr == ""
            assert salt_minion_factory.impl._terminal_result.returncode == 0

            # We are going to kill the possible child processes based on the entire cmdline
            # We know this is unique to these processes because of the unique name of the config files, for example
            cmdline = salt_minion_factory.cmdline(cli_option)
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
