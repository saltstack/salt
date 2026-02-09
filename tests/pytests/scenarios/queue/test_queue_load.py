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


def test_queue_load_300(salt_master, salt_minion, salt_client, sleep_sls):
    """
    Fire 300 jobs with queue=True and ensure they all complete.
    This verifies that the queue processing is efficient and doesn't drop jobs.
    """
    job_count = 300
    print(f"Firing off {job_count} state runs...")

    test_start_time = time.time()

    # Fire jobs
    for i in range(job_count):
        salt_client.cmd_async(
            salt_minion.id, "state.apply", [sleep_sls], kwarg={"queue": True}
        )

    completed_count = 0
    # Timeout needs to account for 0.3s interval per batch of 5
    # 300 / 5 * 0.3 = 18s execution time + overhead
    # Give it generous padding
    timeout = 300
    start_wait = time.time()

    seen_jids = set()

    while completed_count < job_count:
        if time.time() - start_wait > timeout:
            pytest.fail(
                f"Timeout waiting for jobs. Completed: {completed_count}/{job_count}"
            )

        # Check all events since test start
        events = salt_master.event_listener.get_events(
            [(salt_master.id, "*")], after_time=test_start_time
        )

        for event in events:
            # We filter manually for ret events
            if (
                not event.tag.startswith("salt/job/")
                or f"/ret/{salt_minion.id}" not in event.tag
            ):
                continue

            data = event.data
            jid = data.get("jid")

            if data.get("fun") == "state.apply":
                ret_val = data.get("return")

                if isinstance(ret_val, dict):
                    if ret_val.get("queued") is True:
                        continue
                    if ret_val.get("__no_return__"):
                        continue

                    # Check for our specific state execution
                    found_target_state = False
                    for key in ret_val.keys():
                        if "sleep_task" in key:
                            found_target_state = True
                            break

                    if found_target_state:
                        if jid not in seen_jids:
                            seen_jids.add(jid)

        completed_count = len(seen_jids)
        if completed_count >= job_count:
            break

        time.sleep(1)

    assert completed_count >= job_count
