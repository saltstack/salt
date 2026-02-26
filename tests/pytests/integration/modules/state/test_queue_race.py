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
    Directly orchestrate a race condition:
    1. Occupy minion slot.
    2. Queue Job 1 in minion daemon's job_queue.
    3. Run Job 2 via salt-call --local to see if it detects Job 1 in the queue.
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

    # Step 2: Queue Job 1 in Minion Daemon
    cmd_job1 = [
        sys.executable,
        salt_cli.script_name,
        "-c",
        salt_cli.config_dir,
        configured_minion.id,
        "state.apply",
        job1_sls_name,
        "queue=True",
    ]
    subprocess.Popen(cmd_job1, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # Step 3: Verify Job 1 is in job_queue on disk
    job_queue_dir = os.path.join(configured_minion.config["cachedir"], "job_queue")
    start = time.time()
    found = False
    while time.time() - start < 20:
        if os.path.exists(job_queue_dir):
            files = os.listdir(job_queue_dir)
            if any(f.startswith("queued_") for f in files):
                found = True
                break
        time.sleep(0.5)

    assert found, f"Job 1 never appeared in job_queue directory: {job_queue_dir}"

    # Step 4: Run Job 2 via salt-call --local
    # It SHOULD see Job 1 in the job_queue and return "Job queued".

    ret = salt_call_cli.run("--local", "state.apply", job2_sls_name, "queue=True")

    # Check output for the queuing message
    assert "Job queued for execution" in str(
        ret.data
    ), f"Job 2 failed to detect Job 1 in job_queue! Output: {ret.data}"

    # Cleanup
    salt_cli.run("saltutil.kill_job", "all", minion_tgt=configured_minion.id)
