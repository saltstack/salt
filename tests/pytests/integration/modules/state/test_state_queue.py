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
    # Since __no_return__: True is set for queued state jobs, this call will block
    # until it is actually executed. We run it in a thread to verify blocking.
    quick_ret = {"stdout": "", "returncode": None}

    def run_quick():
        ret = salt_cli.run(
            "state.apply",
            quick_sls_name,
            "queue=True",
            minion_tgt=salt_minion.id,
            timeout=60,
        )
        quick_ret["stdout"] = ret.stdout
        quick_ret["returncode"] = ret.returncode

    t2 = threading.Thread(target=run_quick)
    t2.start()

    # Give it a moment to reach the minion and get queued
    time.sleep(5)

    # Job should be queued and NOT executed yet
    assert not quick_target_path.exists(), "Queued state ran too early!"
    assert t2.is_alive(), "Quick job thread finished too early (should be blocking)"

    # Wait for long job thread to finish
    t1.join()

    # Now quick job should be de-queued and run
    t2.join(timeout=30)
    assert not t2.is_alive(), "Quick job thread did not finish after long job ended"

    assert quick_ret["returncode"] == 0
    # stdout should contain the actual state results now, not the "queued" message
    assert (
        "quick_run" in quick_ret["stdout"]
    ), f"Unexpected output: {quick_ret['stdout']}"
    assert (
        quick_target_path.exists()
    ), "Queued state did not execute after long job finished"
