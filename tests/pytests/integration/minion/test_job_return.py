import pytest


@pytest.mark.timeout_unless_on_windows(360)
def test_job_return(salt_master_1, salt_master_2, salt_minion_1):
    cli = salt_master_1.salt_cli(timeout=120)
    ret = cli.run("test.ping", "-v", minion_tgt=salt_minion_1.id)
    for line in ret.stdout.splitlines():
        if "with jid" in line:
            jid = line.split("with jid")[1].strip()

    run_1 = salt_master_1.salt_run_cli(timeout=120)
    ret = run_1.run("jobs.lookup_jid", jid)
    assert ret.data == {"minion-1": True}

    run_2 = salt_master_2.salt_run_cli(timeout=120)
    ret = run_2.run("jobs.lookup_jid", jid)
    assert ret.data == {}
