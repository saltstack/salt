"""
:codeauthor: Thayne Harbaugh (tharbaug@adobe.com)
"""

import glob
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
from tests.conftest import FIPS_TESTRUN

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
        overrides={
            "fips_mode": FIPS_TESTRUN,
            "encryption_algorithm": "OAEP-SHA224" if FIPS_TESTRUN else "OAEP-SHA1",
            "signing_algorithm": "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1",
        },
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
    )
    try:
        with factory.started(start_timeout=120):
            yield factory
    finally:
        # ``factory.started()`` stops the minion daemon on exit but leaves the
        # minion's accepted key under ``{master_pki_dir}/minions/minion-2``.
        # The subsequent ``test_salt_key.py::test_list_*`` tests in the same
        # session enumerate PKI keys and fail their expected-list assertions
        # when this stale key is present.  Delete it via the master's
        # salt-key CLI so the master pki dir is clean for the next test.
        # ``salt_master.salt_key_cli`` is a *factory* method on the saltfactories
        # ``SaltMaster``, not an attribute -- it must be called to obtain a
        # runnable ``SaltKey`` CLI factory.
        salt_master.salt_key_cli().run("-d", factory.id, "-y")

    # Clean up the key so it doesn't affect subsequent tests like test_salt_key.py
    key_file = os.path.join(salt_master.config["pki_dir"], "minions", "minion-2")
    if os.path.exists(key_file):
        os.remove(key_file)


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
def test_interrupt_on_long_running_job(
    event_listener, salt_cli, salt_master, salt_minion
):
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

    # Track the moment we spawn the CLI so ``event_listener`` only considers
    # events published after this point.
    launch_time = time.time()

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

    # Wait until the master publishes the new job before sending SIGINT.
    # A fixed ``time.sleep`` here is racy on slow CI hosts: the salt CLI has
    # not yet set ``pub_data`` when the signal arrives, so its signal
    # handler falls back to just ``Exiting gracefully on Ctrl-c`` with no
    # jid, and the ``This job's jid is`` assertion below fails. Waiting on
    # the ``salt/job/*/new`` event guarantees ``pub_data`` is populated in
    # the CLI process before we interrupt it.
    matched_events = event_listener.wait_for_events(
        [(salt_master.id, "salt/job/*/new")],
        after_time=launch_time,
        timeout=30,
    )
    if not matched_events.found_all_events:
        terminate_process(proc.pid, kill_children=True)
        pytest.fail(
            "The salt CLI never published a job; cannot exercise the "
            "SIGINT path. Matched events: {}".format(matched_events.matches)
        )

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


@pytest.mark.skip_on_windows(reason="Windows does not support SIGUSR1")
def test_sigusr1_handler(salt_master, salt_minion):
    """
    Ensure SIGUSR1 handler works.

    Refer to https://docs.saltproject.io/en/latest/topics/troubleshooting/minion.html#live-python-debug-output for more details.
    """
    tb_glob = os.path.join(tempfile.gettempdir(), "salt-debug-*.log")
    tracebacks_before = glob.glob(tb_glob)
    os.kill(salt_minion.pid, signal.SIGUSR1)
    for i in range(10):
        if len(glob.glob(tb_glob)) - len(tracebacks_before) == 1:
            break
        time.sleep(1)

    os.kill(salt_master.pid, signal.SIGUSR1)
    for i in range(10):
        if len(glob.glob(tb_glob)) - len(tracebacks_before) == 2:
            break
        time.sleep(1)

    tracebacks_after = glob.glob(tb_glob)
    assert len(tracebacks_after) - len(tracebacks_before) == 2
