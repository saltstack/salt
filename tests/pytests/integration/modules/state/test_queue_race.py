import logging
import os
import pathlib
import subprocess
import sys
import time

import pytest
import yaml

import salt.payload
import salt.utils.files

log = logging.getLogger(__name__)


@pytest.fixture(scope="module")
def configured_minion(salt_minion):
    """
    Configures the minion to have process_count_max=1 and no background noise.
    """
    if salt_minion.is_running():
        salt_minion.terminate()

    config_file = pathlib.Path(salt_minion.config_file)
    with salt.utils.files.fopen(config_file) as f:
        config = yaml.safe_load(f)

    original_max = config.get("process_count_max")
    config["process_count_max"] = 1
    config["mine_interval"] = 0
    config["schedule"] = {}  # Disable all scheduled jobs

    with salt.utils.files.fopen(config_file, "w") as f:
        yaml.safe_dump(config, f)

    salt_minion.start()
    yield salt_minion

    # Teardown
    if salt_minion.is_running():
        salt_minion.terminate()
    config["process_count_max"] = original_max
    with salt.utils.files.fopen(config_file, "w") as f:
        yaml.safe_dump(config, f)
    salt_minion.start()


@pytest.fixture(scope="module")
def job1_sls(salt_master, tmp_path_factory):
    sls_name = "job1"
    file_root = pathlib.Path(salt_master.config["file_roots"]["base"][0])
    sls_file = file_root / f"{sls_name}.sls"
    target_path = tmp_path_factory.mktemp("queue_race") / "job1_ran.txt"
    sls_content = f"""
job1_run:
  file.touch:
    - name: {target_path.as_posix()}
"""
    sls_file.write_text(sls_content)
    yield sls_name, target_path


@pytest.fixture(scope="module")
def job2_sls(salt_master, tmp_path_factory):
    sls_name = "job2"
    file_root = pathlib.Path(salt_master.config["file_roots"]["base"][0])
    sls_file = file_root / f"{sls_name}.sls"
    target_path = tmp_path_factory.mktemp("queue_race") / "job2_ran.txt"
    sls_content = f"""
job2_run:
  file.touch:
    - name: {target_path.as_posix()}
"""
    sls_file.write_text(sls_content)
    yield sls_name, target_path


def test_queue_jumping_visibility(
    salt_cli, salt_call_cli, configured_minion, job1_sls, job2_sls
):
    """
    Test that process queuing works correctly:
    1. Occupy minion slot with long-running job.
    2. Verify Job 1 gets queued due to process limits.
    3. Verify Job 2 also gets queued due to process limits.
    4. Verify both jobs are in job_queue.
    """
    job1_sls_name, _ = job1_sls
    job2_sls_name, _ = job2_sls

    # Step 1: Occupy the only slot using subprocess to avoid fixture argument issues
    # We fire it via the salt CLI script directly
    cmd_sleep = [
        sys.executable,
        salt_cli.script_name,
        "-c",
        salt_cli.config_dir,
        configured_minion.id,
        "test.sleep",
        "120",
    ]
    sleep_proc = subprocess.Popen(
        cmd_sleep, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )

    # Wait for it to be running in proc/
    proc_dir = os.path.join(configured_minion.config["cachedir"], "proc")
    start = time.time()
    found_sleep = False
    while time.time() - start < 30:
        if os.path.exists(proc_dir):
            for fn in os.listdir(proc_dir):
                try:
                    with salt.utils.files.fopen(
                        os.path.join(proc_dir, fn), "rb"
                    ) as fp_:
                        data = salt.payload.load(fp_)
                        if isinstance(data, dict) and data.get("fun") == "test.sleep":
                            found_sleep = True
                            break
                except (OSError, ValueError, EOFError, TypeError) as exc:
                    # Skip files that can't be read or parsed
                    # This can happen if the file is corrupted, truncated, or being written
                    log.debug("Skipping proc file %s: %s", fn, exc)
                    continue
        if found_sleep:
            break
        time.sleep(1)
    else:
        out, err = sleep_proc.communicate()
        pytest.fail(f"Sleeper job never started. stdout: {out}, stderr: {err}")

    # Step 2: Queue Job 1 - should be queued due to process_count_max=1
    cmd_job1 = [
        sys.executable,
        salt_cli.script_name,
        "-c",
        salt_cli.config_dir,
        configured_minion.id,
        "state.apply",
        job1_sls_name,
    ]
    subprocess.Popen(cmd_job1, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # Step 3: Verify Job 1 is in job_queue on disk
    job_queue_dir = os.path.join(configured_minion.config["cachedir"], "job_queue")
    start = time.time()
    found_job1 = False
    while time.time() - start < 20:
        if os.path.exists(job_queue_dir):
            files = os.listdir(job_queue_dir)
            if any(f.startswith("queued_") for f in files):
                found_job1 = True
                break
        time.sleep(0.5)

    assert found_job1, f"Job 1 never appeared in job_queue directory: {job_queue_dir}"

    # Step 4: Queue Job 2 - should also be queued since slot is still occupied
    cmd_job2 = [
        sys.executable,
        salt_cli.script_name,
        "-c",
        salt_cli.config_dir,
        configured_minion.id,
        "state.apply",
        job2_sls_name,
    ]
    subprocess.Popen(cmd_job2, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # Step 5: Verify Job 2 is also in job_queue
    start = time.time()
    found_job2 = False
    while time.time() - start < 20:
        if os.path.exists(job_queue_dir):
            files = os.listdir(job_queue_dir)
            queued_files = [f for f in files if f.startswith("queued_")]
            if len(queued_files) >= 2:  # Both Job 1 and Job 2 should be queued
                found_job2 = True
                break
        time.sleep(0.5)

    assert found_job2, f"Job 2 never appeared in job_queue directory: {job_queue_dir}"

    # Step 6: Verify queuing actually happened under load
    # With process_count_max=1 and 1 slot occupied, we should have queued jobs
    assert found_job1 and found_job2, "Process queuing did not work as expected"
