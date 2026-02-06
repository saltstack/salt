import threading
import time

import pytest

import salt.utils.files


@pytest.fixture(scope="module")
def long_running_sls(base_env_state_tree_root_dir, tmp_path_factory):
    sls_name = "long_running"
    sls_dir = base_env_state_tree_root_dir
    sls_file = sls_dir / f"{sls_name}.sls"

    sls_content = """
    long_running_sleep:
      cmd.run:
        - name: sleep 20
    """
    with salt.utils.files.fopen(sls_file, "w", encoding="utf-8") as f:
        f.write(sls_content)

    yield sls_name


@pytest.fixture(scope="module")
def quick_sls(base_env_state_tree_root_dir, tmp_path_factory):
    sls_name = "quick"
    sls_dir = base_env_state_tree_root_dir
    sls_file = sls_dir / f"{sls_name}.sls"
    target_path = tmp_path_factory.mktemp("state_queue") / "quick_ran.txt"

    sls_content = f"""
    quick_run:
      file.touch:
        - name: {target_path}
    """
    with salt.utils.files.fopen(sls_file, "w", encoding="utf-8") as f:
        f.write(sls_content)

    yield sls_name, target_path


def test_state_queue_true(salt_cli, salt_minion, long_running_sls, quick_sls):
    """
    Test that state.apply with queue=True queues the job and runs it after the current one finishes.
    """
    quick_sls_name, quick_target_path = quick_sls

    # Ensure target doesn't exist
    if quick_target_path.exists():
        quick_target_path.unlink()

    # We use threading to run long_running in parallel
    long_ret = {"ret": None}

    def run_long():
        # Use a separate process to avoid thread-safety issues with salt_cli fixture
        import subprocess

        # We need to find the salt executable. salt_cli.script_name might be a python script.
        # But we can assume venv310/bin/salt exists or use sys.executable
        import sys

        # Construct command to run salt against the test master
        # salt_cli provides configuration
        cmd = [
            sys.executable,
            salt_cli.script_name,
            "-c",
            str(salt_cli.config_dir),
            salt_minion.id,
            "state.apply",
            long_running_sls,
            "timeout=60",
        ]

        subprocess.run(cmd, capture_output=True, check=False)

    t1 = threading.Thread(target=run_long)
    t1.start()

    # Wait for the job to start and appear in running list
    start_wait = time.time()
    job_running = False
    long_jid = None

    while time.time() - start_wait < 30:
        ret_running = salt_cli.run(
            "saltutil.is_running", "state.*", minion_tgt=salt_minion.id
        )
        if ret_running.returncode == 0 and ret_running.data:
            minion_data = []
            if isinstance(ret_running.data, list):
                minion_data = ret_running.data
            elif isinstance(ret_running.data, dict):
                minion_data = ret_running.data.get(salt_minion.id, [])

            # Look for long_running
            if minion_data:
                for job in minion_data:
                    if job["fun"] in ["state.apply", "state.sls", "state.highstate"]:
                        long_jid = job["jid"]
                        job_running = True
                        break
        if job_running:
            break
        time.sleep(1)

    assert job_running, "Long running job did not appear in saltutil.is_running"

    # Now run quick with queue=True
    # This should return immediately with "Job queued"
    ret_quick = salt_cli.run(
        "state.apply",
        quick_sls_name,
        "queue=True",
        minion_tgt=salt_minion.id,
        timeout=60,
    )

    assert ret_quick.returncode == 0
    assert (
        "Job queued for execution" in ret_quick.stdout or "queued" in ret_quick.stdout
    ), f"Job was not queued. Stdout: {ret_quick.stdout}"

    assert not quick_target_path.exists(), "Queued state ran too early!"

    # Wait for long job to finish
    t1.join()

    # Wait for quick job to eventually run
    start_wait = time.time()
    while time.time() - start_wait < 30:
        if quick_target_path.exists():
            break
        time.sleep(1)

    assert (
        quick_target_path.exists()
    ), "Queued state did not execute after long job finished"
