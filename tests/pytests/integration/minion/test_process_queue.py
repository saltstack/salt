import pathlib
import subprocess
import sys
import textwrap
import time

import psutil
import pytest
import yaml

import salt.utils.files


@pytest.fixture(scope="module")
def configured_minion(salt_minion):
    """
    Configures the standard salt_minion to have process_count_max=2.
    Restarts the minion to apply changes.
    """
    # Stop minion
    if salt_minion.is_running():
        salt_minion.terminate()

    # Edit config
    config_file = pathlib.Path(salt_minion.config_file)
    with salt.utils.files.fopen(config_file) as f:
        config = yaml.safe_load(f)

    original_max = config.get("process_count_max")
    config["process_count_max"] = 2
    config["minion_jid_queue_hwm"] = 100

    with salt.utils.files.fopen(config_file, "w") as f:
        yaml.safe_dump(config, f)

    # Start minion
    salt_minion.start()

    yield salt_minion

    # Teardown: Restore config
    if salt_minion.is_running():
        salt_minion.terminate()

    if original_max is None:
        if "process_count_max" in config:
            del config["process_count_max"]
    else:
        config["process_count_max"] = original_max

    with salt.utils.files.fopen(config_file, "w") as f:
        yaml.safe_dump(config, f)

    salt_minion.start()


@pytest.fixture
def run_salt_cmd(salt_cli, configured_minion):
    def _run(fun, args=None, kw=None, timeout=60, background=False):
        if args is None:
            args = []
        if kw is None:
            kw = {}

        # Convert kw to string arguments "key=value"
        kw_args = [f"{k}={v}" for k, v in kw.items()]

        cmd = (
            [
                sys.executable,
                salt_cli.script_name,
                "-c",
                str(salt_cli.config_dir),
                configured_minion.id,
                fun,
            ]
            + list(args)
            + kw_args
        )

        # Add client timeout if provided (but not as kwarg to function)
        cmd.extend(["-t", str(timeout)])

        if background:
            return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        else:
            return subprocess.run(cmd, capture_output=True, text=True, check=False)

    return _run


@pytest.mark.slow_test
def test_process_queue_basic(salt_cli, configured_minion, run_salt_cmd, tmp_path):
    """
    Test that jobs are queued when process_count_max is reached.
    Config: process_count_max = 2
    """
    # Verify config on disk
    with salt.utils.files.fopen(configured_minion.config_file) as f:
        cfg = yaml.safe_load(f)
        assert cfg.get("process_count_max") == 2

    # 1. Start 2 long-running jobs to fill the slots
    p1 = run_salt_cmd("cmd.run", ["sleep 6"], background=True)
    p2 = run_salt_cmd("cmd.run", ["sleep 6"], background=True)

    time.sleep(2)

    # Verify they are running
    minion_proc = psutil.Process(configured_minion.pid)
    start_wait = time.time()
    while time.time() - start_wait < 10:
        try:
            children = minion_proc.children(recursive=True)
            sleep_jobs = [p for p in children if "sleep" in " ".join(p.cmdline())]
            if len(sleep_jobs) >= 2:
                break
        except psutil.NoSuchProcess:
            pass
        time.sleep(0.5)

    try:
        children = minion_proc.children(recursive=True)
        sleep_jobs = [p for p in children if "sleep" in " ".join(p.cmdline())]
    except psutil.NoSuchProcess:
        sleep_jobs = []

    assert len(sleep_jobs) >= 2, f"Found only {len(sleep_jobs)} sleep jobs"

    # 2. Start a 3rd job (marker file) - Should be queued
    marker = tmp_path / "job3.txt"
    start_time = time.time()
    p3 = run_salt_cmd("cmd.run", [f"touch {marker}"], background=True)

    # 3. Check if it ran immediately
    time.sleep(1)
    assert not marker.exists(), "Job 3 ran immediately despite process_count_max limit!"

    # 4. Wait for p1/p2 to finish
    p1.wait()
    p2.wait()

    # 5. Wait for p3 to finish
    p3.wait()
    end_time = time.time()

    timeout = 15
    start_wait = time.time()
    while not marker.exists() and time.time() - start_wait < timeout:
        time.sleep(0.5)

    assert marker.exists(), "Job 3 did not execute after queueing"

    duration = end_time - start_time
    assert duration > 3, f"Job 3 returned too quickly ({duration}s)"


@pytest.mark.slow_test
def test_state_queue_interaction(
    salt_cli, salt_master, configured_minion, run_salt_cmd, tmp_path
):
    """
    Test interaction between state.apply queue=True and process_count_max.
    Config: process_count_max = 2
    """
    marker = tmp_path / "job_b.txt"

    # Setup SLS files
    file_root = pathlib.Path(salt_master.config["file_roots"]["base"][0])

    sls_file = file_root / "test_interaction.sls"
    sls_file.write_text(
        textwrap.dedent(
            f"""
    job_b_marker:
      file.touch:
        - name: {marker}
    """
        )
    )

    sls_file_a = file_root / "job_a.sls"
    sls_file_a.write_text(
        textwrap.dedent(
            """
    job_a_sleep:
      cmd.run:
        - name: sleep 6
    """
        )
    )

    # 1. Start Job A (State, Long) -> Slot 1
    p1 = run_salt_cmd("state.sls", ["job_a"], background=True)
    time.sleep(2)

    # 2. Start Job B (State, Short, queue=True) -> Should go to STATE QUEUE (conflict)
    # Since __no_return__: True is set for queued state jobs, this call will block
    # until it is actually executed. We run it in the background to continue the test.
    p2 = run_salt_cmd(
        "state.sls",
        ["test_interaction", "--out=json"],
        kw={"queue": True},
        background=True,
    )
    time.sleep(2)

    assert not marker.exists(), "Job B ran immediately despite state conflict!"

    # 3. Start Job C (Non-State, Long) -> Slot 2
    # This fills the process table (A + C = 2/2)
    p3 = run_salt_cmd("cmd.run", ["sleep 6"], background=True)
    time.sleep(2)

    # 4. Job A finishes.
    p1.wait()
    # Under load the minion may need a moment to schedule the queued state.
    time.sleep(1)

    # Job B should be popped from State Queue.
    # Job C is still running (Slot 2). Slot 1 is open.
    # Job B should take Slot 1.

    # Wait for execution
    start_wait = time.time()
    while not marker.exists() and time.time() - start_wait < 45:
        time.sleep(0.5)

    assert marker.exists(), "Job B did not execute after Job A finished"

    p2.terminate()
    p3.wait()


@pytest.mark.slow_test
def test_state_queue_handoff_to_process_queue(
    salt_cli, salt_master, configured_minion, run_salt_cmd, tmp_path
):
    """
    Test scenario where a job leaves State Queue but hits Process Limit immediately.
    Config: process_count_max = 2
    """
    marker = tmp_path / "job_b_handoff.txt"

    file_root = pathlib.Path(salt_master.config["file_roots"]["base"][0])

    sls_file = file_root / "test_handoff.sls"
    sls_file.write_text(
        textwrap.dedent(
            f"""
    job_b_marker:
      file.touch:
        - name: {marker}
    """
        )
    )

    sls_file_a = file_root / "job_a_handoff.sls"
    sls_file_a.write_text(
        textwrap.dedent(
            """
    job_a_sleep:
      cmd.run:
        - name: sleep 6
    """
        )
    )

    # 1. Start Job A (State, Sleep 6) -> Slot 1
    p1 = run_salt_cmd("state.sls", ["job_a_handoff"], background=True)
    time.sleep(2)

    # 2. Start Job B (State, Touch, queue=True) -> State Queue (Conflict with A)
    # Background because it will block
    p2 = run_salt_cmd(
        "state.sls", ["test_handoff", "--out=json"], kw={"queue": True}, background=True
    )
    time.sleep(2)

    assert not marker.exists(), "Job B ran immediately despite state conflict!"

    # 3. Start Job C (Non-State, Sleep 6) -> Slot 2
    p3 = run_salt_cmd("cmd.run", ["sleep 6"], background=True)
    time.sleep(2)

    # 4. Start Job D (Non-State, Sleep 6) -> Process Queue (Limit 2 reached)
    p4 = run_salt_cmd("cmd.run", ["sleep 6"], background=True)

    # 5. Job A finishes.
    p1.wait()

    start_wait = time.time()
    while not marker.exists() and time.time() - start_wait < 20:
        time.sleep(0.5)

    assert marker.exists(), "Job B did not execute in high contention scenario"

    p2.terminate()
    p3.terminate()
    p4.terminate()
