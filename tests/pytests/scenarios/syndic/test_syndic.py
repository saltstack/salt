def test_syndic(salt_cli, minion):
    ret = salt_cli.run("test.ping", minion_tgt="*", _timeout=15)
    assert ret.data == {
        "syndic": True,
        "minion": True,
    }
