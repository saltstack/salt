"""
:codeauthor: Thayne Harbaugh (tharbaug@adobe.com)
"""

import logging
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time

import pytest
from pytestshellutils.utils.processes import ProcessResult, terminate_process

import salt.defaults.exitcodes
import salt.utils.path

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.core_test,
    pytest.mark.windows_whitelisted,
]


@pytest.fixture
def salt_minion_2(salt_master):
    """
    A running salt-minion fixture
    """
    factory = salt_master.salt_minion_daemon(
        "minion-2",
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
    )
    with factory.started(start_timeout=120):
        yield factory


def test_context_retcode_salt(salt_cli, salt_minion):
    """
    Test that a nonzero retcode set in the context dunder will cause the
    salt CLI to set a nonzero retcode.
    """
    # test.retcode will set the retcode in the context dunder
    ret = salt_cli.run("test.retcode", "0", minion_tgt=salt_minion.id)
    assert ret.returncode == 0, ret
    ret = salt_cli.run("test.retcode", "42", minion_tgt=salt_minion.id)
    assert ret.returncode == salt.defaults.exitcodes.EX_GENERIC, ret


def test_salt_error(salt_cli, salt_minion):
    """
    Test that we return the expected retcode when a minion function raises
    an exception.
    """
    ret = salt_cli.run("test.raise_exception", "TypeError", minion_tgt=salt_minion.id)
    assert ret.returncode == salt.defaults.exitcodes.EX_GENERIC, ret

    ret = salt_cli.run(
        "test.raise_exception",
        "salt.exceptions.CommandNotFoundError",
        minion_tgt=salt_minion.id,
    )
    assert ret.returncode == salt.defaults.exitcodes.EX_GENERIC, ret

    ret = salt_cli.run(
        "test.raise_exception",
        "salt.exceptions.CommandExecutionError",
        minion_tgt=salt_minion.id,
    )
    assert ret.returncode == salt.defaults.exitcodes.EX_GENERIC, ret

    ret = salt_cli.run(
        "test.raise_exception",
        "salt.exceptions.SaltInvocationError",
        minion_tgt=salt_minion.id,
    )
    assert ret.returncode == salt.defaults.exitcodes.EX_GENERIC, ret

    ret = salt_cli.run(
        "test.raise_exception",
        "OSError",
        "2",
        '"No such file or directory" /tmp/foo.txt',
        minion_tgt=salt_minion.id,
    )
    assert ret.returncode == salt.defaults.exitcodes.EX_GENERIC, ret

    ret = salt_cli.run(
        "test.echo", "{foo: bar, result: False}", minion_tgt=salt_minion.id
    )
    assert ret.returncode == salt.defaults.exitcodes.EX_GENERIC, ret

    ret = salt_cli.run(
        "test.echo", "{foo: bar, success: False}", minion_tgt=salt_minion.id
    )
    assert ret.returncode == salt.defaults.exitcodes.EX_GENERIC, ret


def test_missing_minion(salt_cli, salt_master, salt_minion):
    """
    Test that a minion which doesn't respond results in a nonzeo exit code
    """
    good = salt.utils.path.join(
        salt_master.config["pki_dir"], "minions", salt_minion.id
    )
    bad = salt.utils.path.join(salt_master.config["pki_dir"], "minions", "minion2")
    try:
        # Copy the key
        shutil.copyfile(good, bad)
        ret = salt_cli.run(
            "--timeout=5", "test.ping", minion_tgt="minion2", _timeout=120
        )
        assert ret.returncode == salt.defaults.exitcodes.EX_GENERIC, ret
    finally:
        # Now get rid of it
        try:
            os.remove(bad)
        except OSError as exc:
            if exc.errno != os.errno.ENOENT:
                log.error(
                    "Failed to remove %s, this may affect other tests: %s", bad, exc
                )


def test_exit_status_unknown_argument(salt_cli):
    """
    Ensure correct exit status when an unknown argument is passed to salt CLI.
    """
    ret = salt_cli.run(
        "--unknown-argument", minion_tgt="minion-tgt-is-mandatory-by-salt-factories"
    )
    assert ret.returncode == salt.defaults.exitcodes.EX_USAGE, ret
    assert "Usage" in ret.stderr
    assert "no such option: --unknown-argument" in ret.stderr


def test_exit_status_correct_usage(salt_cli, salt_minion):
    """
    Ensure correct exit status when salt CLI starts correctly.

    """
    ret = salt_cli.run("test.ping", minion_tgt=salt_minion.id)
    assert ret.returncode == salt.defaults.exitcodes.EX_OK, ret


@pytest.mark.skip_on_windows(reason="Windows does not support SIGINT")
@pytest.mark.skip_initial_onedir_failure
def test_interrupt_on_long_running_job(salt_cli, salt_master, salt_minion):
    """
    Ensure that a call to ``salt`` that is taking too long, when a user
    hits CTRL-C, that the JID is printed to the console.

    Refer to https://github.com/saltstack/salt/issues/60963 for more details
    """
    # Ensure test.sleep is working as supposed
    start = time.time()
    ret = salt_cli.run("test.sleep", "1", minion_tgt=salt_minion.id)
    stop = time.time()
    assert ret.returncode == 0
    assert ret.data is True
    assert stop - start > 1, "The command should have taken more than 1 second"

    # Now the real test
    terminal_stdout = tempfile.SpooledTemporaryFile(512000, buffering=0)
    terminal_stderr = tempfile.SpooledTemporaryFile(512000, buffering=0)
    cmdline = [
        sys.executable,
        salt_cli.get_script_path(),
        f"--config-dir={salt_master.config_dir}",
        salt_minion.id,
        "test.sleep",
        "30",
    ]

    # If this test starts failing, commend the following block of code
    proc = subprocess.Popen(
        cmdline,
        shell=False,
        stdout=terminal_stdout,
        stderr=terminal_stderr,
        universal_newlines=True,
    )
    # and uncomment the following block of code

    # with default_signals(signal.SIGINT, signal.SIGTERM):
    #    proc = subprocess.Popen(
    #        cmdline,
    #        shell=False,
    #        stdout=terminal_stdout,
    #        stderr=terminal_stderr,
    #        universal_newlines=True,
    #    )

    # What this means is that something in salt or the test suite is setting
    # the SIGTERM and SIGINT signals to SIG_IGN, ignore.
    # Check which line of code is doing that and fix it
    start = time.time()
    try:
        # Make sure it actually starts
        proc.wait(1)
    except subprocess.TimeoutExpired:
        pass
    else:
        terminate_process(proc.pid, kill_children=True)
        pytest.fail("The test process failed to start")

    time.sleep(2)
    # Send CTRL-C to the process
    os.kill(proc.pid, signal.SIGINT)
    with proc:
        # Wait for the process to terminate, to avoid zombies.
        # Shouldn't really take the 30 seconds
        proc.wait(30)
        # poll the terminal so the right returncode is set on the popen object
        proc.poll()
        # This call shouldn't really be necessary
        proc.communicate()
    stop = time.time()

    terminal_stdout.flush()
    terminal_stdout.seek(0)
    stdout = proc._translate_newlines(
        terminal_stdout.read(), __salt_system_encoding__, sys.stdout.errors
    )
    terminal_stdout.close()

    terminal_stderr.flush()
    terminal_stderr.seek(0)
    stderr = proc._translate_newlines(
        terminal_stderr.read(), __salt_system_encoding__, sys.stderr.errors
    )
    terminal_stderr.close()
    ret = ProcessResult(
        returncode=proc.returncode, stdout=stdout, stderr=stderr, cmdline=proc.args
    )
    log.debug(ret)
    # If the minion ID is on stdout it means that the command finished and wasn't terminated
    assert (
        salt_minion.id not in ret.stdout
    ), "The command wasn't actually terminated. Took {} seconds.".format(
        round(stop - start, 2)
    )

    # Make sure the ctrl+c exited gracefully
    assert "Exiting gracefully on Ctrl-c" in ret.stderr
    assert "Exception ignored in" not in ret.stderr
    assert "This job's jid is" in ret.stderr


def test_minion_65400(salt_cli, salt_minion, salt_minion_2, salt_master):
    """
    Ensure correct exit status when salt CLI starts correctly.

    """
    state = """
    custom_test_state:
      test.configurable_test_state:
        - name: example
        - changes: True
        - result: False
        - comment: 65400 regression test
    """
    with salt_master.state_tree.base.temp_file("test_65400.sls", state):
        ret = salt_cli.run("state.sls", "test_65400", minion_tgt="*")
        assert isinstance(ret.data, dict)
        assert len(ret.data.keys()) == 2
        for minion_id in ret.data:
            assert ret.data[minion_id] != "Error: test.configurable_test_state"
            assert isinstance(ret.data[minion_id], dict)
