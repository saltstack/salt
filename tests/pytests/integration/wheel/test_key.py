import pytest

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.windows_whitelisted,
]


def test_list_all(client, salt_minion, salt_sub_minion):
    ret = client.cmd("key.list_all", print_event=False)
    assert ret
    assert "minions" in ret
    assert salt_minion.id in ret["minions"]
    assert salt_sub_minion.id in ret["minions"]


def test_gen(client):
    ret = client.cmd(
        "key.gen", kwarg={"id_": "soundtechniciansrock"}, print_event=False
    )
    assert ret
    assert "pub" in ret
    try:
        assert ret["pub"].startswith("-----BEGIN PUBLIC KEY-----")
    except AttributeError:
        assert ret["pub"].startswith("-----BEGIN RSA PUBLIC KEY-----")

    assert "priv" in ret
    assert ret["priv"].startswith("-----BEGIN RSA PRIVATE KEY-----")


def test_master_key_str(client):
    ret = client.cmd("key.master_key_str", print_event=False)
    assert ret
    assert "local" in ret
    data = ret["local"]
    assert "master.pub" in data
    assert data["master.pub"].startswith("-----BEGIN PUBLIC KEY-----")
