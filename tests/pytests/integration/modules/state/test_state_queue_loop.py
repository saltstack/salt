import time

import pytest

import salt.utils.files


@pytest.fixture(scope="module")
def loop_sls(base_env_state_tree_root_dir, tmp_path_factory):
    sls_name = "loop_check"
    sls_dir = base_env_state_tree_root_dir
    sls_file = sls_dir / f"{sls_name}.sls"
    target_path = tmp_path_factory.mktemp("state_queue_loop") / "run_count.txt"

    # Use cmd.run to append to a file so we can count executions
    sls_content = f"""
    loop_check_run:
      cmd.run:
        - name: echo "Ran" >> {target_path}
    """
    with salt.utils.files.fopen(sls_file, "w", encoding="utf-8") as f:
        f.write(sls_content)

    yield sls_name, target_path


def test_state_queue_no_loop(salt_cli, salt_minion, loop_sls):
    """
    Test that state.apply with queue=True executes only once and does not loop.
    """

    sls_name, target_path = loop_sls

    # Ensure target doesn't exist
    if target_path.exists():
        target_path.unlink()

    # Run state with queue=True when no conflicts exist
    # It should execute immediately and only once
    ret = salt_cli.run("state.apply", sls_name, "queue=True", minion_tgt=salt_minion.id)

    assert ret.returncode == 0, f"Job failed: {ret}"
    assert target_path.exists(), "Target state did not execute"

    # Wait a bit more to ensure no additional executions
    time.sleep(2)

    # Check execution count - should be exactly 1
    content = target_path.read_text().strip().splitlines()
    count = len(content)

    assert count == 1, f"State ran {count} times! Should run only once."
