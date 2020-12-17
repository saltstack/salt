import time

from tests.support.helpers import slowTest


@slowTest
def test_publish_retry(salt_master, salt_minion, salt_cli, salt_run_cli):
    # run job that takes some time for warmup
    rtn = salt_cli.run("test.sleep", "5", "--async", minion_tgt=salt_minion.id)
    # obtain JID
    jid = rtn.stdout.strip().split(" ")[-1]

    # stop the salt master for some time
    with salt_master.stopped():
        # verify we don't yet have the result and sleep
        assert salt_run_cli.run("jobs.lookup_jid", jid, _timeout=60).json == {}
        time.sleep(10)

    data = None
    for i in range(1, 30):
        time.sleep(1)
        data = salt_run_cli.run("jobs.lookup_jid", jid, _timeout=60).json
        if data:
            break

    assert salt_minion.id in data
    assert data[salt_minion.id] is True
