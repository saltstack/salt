def test_syndic(salt_cli, minion):
    ret = salt_cli.run("test.ping", minion_tgt="*", _timeout=15)
    assert ret.data == {
        "syndic": True,
        "minion": True,
    }


def test_syndic_target_single_minion(salt_cli, minion):
    """
    Test that the salt CLI exits after getting all returns + syndic_wait time
    rather than waiting for the full gather_job_timeout set high in conftest.
    """
    ret = salt_cli.run("test.ping", minion_tgt="minion", _timeout=15)
    assert ret.data is True
