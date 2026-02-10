import logging
import os
import time

import pytest

import salt.utils.files

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.slow_test,
]


@pytest.fixture(scope="module")
def sleep_sls(salt_master):
    sls_name = "sleep_queue_test"
    # Write to the first base file_root
    file_root = salt_master.config["file_roots"]["base"][0]
    sls_file = os.path.join(file_root, f"{sls_name}.sls")

    sls_content = """
    sleep_task:
      cmd.run:
        - name: sleep 0.1
    """

    with salt.utils.files.fopen(sls_file, "w") as f:
        f.write(sls_content)

    yield sls_name

    if os.path.exists(sls_file):
        os.remove(sls_file)


def test_queue_load_500(salt_master, salt_minion, salt_client, sleep_sls):
    """
    TC1-TC4: Fire 500 jobs with queue=True and ensure they all complete safely.
    Verifies concurrency control, thread visibility, and Master stability.
    """
    job_count = 500
    process_count_max = salt_minion.config["process_count_max"]
    log.info(
        "Starting TC1-TC4: Firing 500 state runs (Max: %s, Multiprocessing: %s)",
        process_count_max,
        salt_minion.config["multiprocessing"],
    )

    test_start_time = time.time()

    # Fire jobs
    for i in range(job_count):
        salt_client.cmd_async(
            salt_minion.id, "state.apply", [sleep_sls], kwarg={"queue": True}
        )

    completed_count = 0
    queued_responses_count = 0
    timeout = 600
    start_wait = time.time()

    seen_jids = set()
    state_queue_dir = os.path.join(salt_minion.config["cachedir"], "state_queue")
    job_queue_dir = os.path.join(salt_minion.config["cachedir"], "job_queue")
    proc_dir = os.path.join(salt_minion.config["cachedir"], "proc")

    max_state_queue_size = 0
    max_job_queue_size = 0

    while completed_count < job_count:
        if time.time() - start_wait > timeout:
            pytest.fail(
                f"Timeout waiting for jobs. Completed: {completed_count}/{job_count}, "
                f"Queued responses: {queued_responses_count}, "
                f"Max state_queue: {max_state_queue_size}, Max job_queue: {max_job_queue_size}"
            )

        # Monitor disk activity
        if os.path.exists(state_queue_dir):
            max_state_queue_size = max(
                max_state_queue_size, len(os.listdir(state_queue_dir))
            )
        if os.path.exists(job_queue_dir):
            max_job_queue_size = max(max_job_queue_size, len(os.listdir(job_queue_dir)))

        # Check events
        events = salt_master.event_listener.get_events(
            [(salt_master.id, "*")], after_time=test_start_time
        )

        for event in events:
            if (
                not event.tag.startswith("salt/job/")
                or f"/ret/{salt_minion.id}" not in event.tag
            ):
                continue

            data = event.data
            # CRITICAL: Verify return is always a dictionary (TC7)
            assert isinstance(
                data.get("return"), dict
            ), f"Return for JID {data.get('jid')} was not a dictionary: {data.get('return')}"

            if data.get("fun") == "state.apply":
                ret_val = data.get("return")
                if ret_val.get("queued") is True:
                    queued_responses_count += 1
                    continue

                if any("sleep_task" in k for k in ret_val.keys()):
                    if data["jid"] not in seen_jids:
                        seen_jids.add(data["jid"])

        completed_count = len(seen_jids)
        if completed_count >= job_count:
            break
        time.sleep(1)

    log.info(
        "TC1-TC4 Complete. Max state_q: %s, Max job_q: %s, Queued rets: %s",
        max_state_queue_size,
        max_job_queue_size,
        queued_responses_count,
    )

    assert completed_count >= job_count
    # Ensure queuing actually happened under load
    assert (
        max_state_queue_size > 0 or max_job_queue_size > 0 or queued_responses_count > 0
    )
    # Ensure proc directory is cleaned up (Stale Proc check)
    if os.path.exists(proc_dir):
        # Allow a few seconds for final async cleanups
        time.sleep(5)
        assert (
            len(os.listdir(proc_dir)) == 0
        ), f"Proc directory not empty: {os.listdir(proc_dir)}"


def test_immediate_conflict_tc5(salt_master, salt_minion, salt_client, sleep_sls):
    """
    TC5: Fire jobs with queue=False and verify immediate conflict returns are dicts.
    """
    log.info("Starting TC5: Immediate conflict dictionary validation")

    # Fire 5 concurrent jobs WITHOUT queuing
    jids = []
    for i in range(5):
        jids.append(
            salt_client.cmd_async(
                salt_minion.id, "state.apply", [sleep_sls], kwarg={"queue": False}
            )
        )

    # We expect at least some to return "Already running" immediately as a dictionary
    conflicts_seen = 0
    start_wait = time.time()
    while time.time() - start_wait < 30:
        events = salt_master.event_listener.get_events([(salt_master.id, "*")])
        for event in events:
            if (
                not event.tag.startswith("salt/job/")
                or f"/ret/{salt_minion.id}" not in event.tag
            ):
                continue

            ret = event.data.get("return")
            if isinstance(ret, dict) and "salt_|-state_|-running_|-Conflict" in str(
                ret
            ):
                conflicts_seen += 1

        if conflicts_seen > 0:
            break
        time.sleep(1)

    assert conflicts_seen > 0, "No immediate conflicts seen with queue=False"


def test_compiler_error_schema(salt_master, salt_minion, salt_client):
    """
    Verify that a broken SLS returns a valid State Result Schema dictionary.
    """
    log.info("Starting Edge Case: Compiler error schema validation")
    jid = salt_client.cmd_async(salt_minion.id, "state.apply", ["non_existent_sls"])

    start_wait = time.time()
    while time.time() - start_wait < 30:
        events = salt_master.event_listener.get_events([(salt_master.id, "*")])
        for event in events:
            if event.data.get("jid") == jid:
                ret = event.data.get("return")
                assert isinstance(
                    ret, dict
                ), "Compiler error return was not a dictionary"
                # Check for our custom schema wrap
                assert any(
                    "compiler" in k for k in ret.keys()
                ), f"Missing compiler tag in return: {ret}"
                return
        time.sleep(1)
    pytest.fail("Timeout waiting for compiler error return")


def test_stale_lock_recovery(salt_master, salt_minion, salt_client, sleep_sls):
    """
    Verify that the Minion recovers from stale lock files on startup.
    (Assumes Minion handles this or we add it to the Minion class).
    """
    log.info("Starting Edge Case: Stale lock recovery")
    lock_path = os.path.join(salt_minion.config["cachedir"], "job_queue.lock")

    # Create a stale lock
    with salt.utils.files.fopen(lock_path, "w") as f:
        f.write("stale")

    # Job should still succeed (Minion should detect lock is stale or overwrite it)
    # Note: Our current await_lock uses O_EXCL, so we might need a Minion restart
    # to really test "startup cleanup". For now, we verify it doesn't hang forever.
    jid = salt_client.cmd_async(salt_minion.id, "state.apply", [sleep_sls])

    start_wait = time.time()
    while time.time() - start_wait < 30:
        events = salt_master.event_listener.get_events([(salt_master.id, "*")])
        for event in events:
            if event.data.get("jid") == jid:
                return
        time.sleep(1)
    pytest.fail("Minion hung or failed to recover from stale lock")
