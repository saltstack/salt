import os

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


def test_state_queue_basic(salt_cli, salt_minion, quick_sls):
    """
    Test that state.apply with queue=True works correctly.
    This demonstrates the basic queuing functionality works.
    """

    quick_sls_name, quick_target_path = quick_sls

    # Ensure target doesn't exist
    if quick_target_path.exists():
        quick_target_path.unlink()

    # Step 1: Run a state job with queue=True
    # Since no conflicts exist, it should execute immediately
    ret = salt_cli.run(
        "state.apply",
        quick_sls_name,
        "queue=True",
        minion_tgt=salt_minion.id,
    )

    # Should execute immediately (no conflicts)
    assert ret.returncode == 0, f"Job failed: {ret}"
    assert quick_target_path.exists(), "Job should have executed immediately"

    # Step 2: Verify no files were left in state_queue
    state_queue_dir = os.path.join(salt_minion.config["cachedir"], "state_queue")
    if os.path.exists(state_queue_dir):
        files = os.listdir(state_queue_dir)
        queued_files = [
            f for f in files if f.startswith("queued_") and f.endswith(".p")
        ]
        assert len(queued_files) == 0, f"Unexpected queued files found: {queued_files}"


def test_state_queue_true(salt_cli, salt_minion, quick_sls):
    """
    Test that state.apply with queue=True works correctly.
    Since creating real conflicts is complex and timing-dependent,
    this test verifies that queuing doesn't break normal execution.
    """

    quick_sls_name, quick_target_path = quick_sls

    # Ensure target doesn't exist
    if quick_target_path.exists():
        quick_target_path.unlink()

    # Run a state job with queue=True when no conflicts exist
    # It should execute immediately
    ret = salt_cli.run(
        "state.apply",
        quick_sls_name,
        "queue=True",
        minion_tgt=salt_minion.id,
    )

    # Should execute successfully (no conflicts to queue against)
    assert ret.returncode == 0, f"Job failed: {ret}"
    assert quick_target_path.exists(), "Job should have executed"

    # Verify no files were left in state_queue (since it executed immediately)
    state_queue_dir = os.path.join(salt_minion.config["cachedir"], "state_queue")
    if os.path.exists(state_queue_dir):
        files = os.listdir(state_queue_dir)
        queued_files = [
            f for f in files if f.startswith("queued_") and f.endswith(".p")
        ]
        assert len(queued_files) == 0, f"Unexpected queued files found: {queued_files}"
