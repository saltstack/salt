import pytest
import salt.netapi
from salt.exceptions import EauthAuthenticationError


@pytest.fixture
def client(salt_minion, salt_sub_minion, client_config):
    return salt.netapi.NetapiClient(client_config)


@pytest.mark.slow_test
def test_local(client, auth_creds, salt_minion, salt_sub_minion):
    low = {"client": "local", "tgt": "*", "fun": "test.ping", **auth_creds}

    ret = client.run(low)
    assert ret == {salt_minion.id: True, salt_sub_minion.id: True}


@pytest.mark.slow_test
def test_local_batch(client, auth_creds, salt_minion, salt_sub_minion):
    low = {"client": "local_batch", "tgt": "*", "fun": "test.ping", **auth_creds}

    ret = client.run(low)
    assert ret
    # local_batch returns a generator
    ret = list(ret)
    assert ret
    assert {salt_minion.id: True} in ret
    assert {salt_sub_minion.id: True} in ret


def test_local_async(client, auth_creds, salt_minion, salt_sub_minion):
    low = {"client": "local_async", "tgt": "*", "fun": "test.ping", **auth_creds}

    ret = client.run(low)

    assert "jid" in ret
    assert sorted(ret["minions"]) == sorted([salt_minion.id, salt_sub_minion.id])


def test_local_unauthenticated(client):
    low = {"client": "local", "tgt": "*", "fun": "test.ping"}
    with pytest.raises(EauthAuthenticationError):
        client.run(low)


@pytest.mark.slow_test
def test_wheel(client, auth_creds):
    low = {"client": "wheel", "fun": "key.list_all", **auth_creds}

    ret = client.run(low)

    assert "tag" in ret
    assert "data" in ret
    assert "jid" in ret["data"]
    assert "tag" in ret["data"]
    assert "return" in ret["data"]
    assert "local" in ret["data"]["return"]
    assert {"master.pem", "master.pub"}.issubset(set(ret["data"]["return"]["local"]))


@pytest.mark.slow_test
def test_wheel_async(client, auth_creds):
    low = {"client": "wheel_async", "fun": "key.list_all", **auth_creds}

    ret = client.run(low)
    assert "jid" in ret
    assert "tag" in ret


def test_wheel_unauthenticated(client):
    low = {"client": "wheel", "tgt": "*", "fun": "test.ping"}

    with pytest.raises(EauthAuthenticationError):
        client.run(low)


def test_runner_unauthenticated(client):
    low = {"client": "runner", "tgt": "*", "fun": "test.ping"}
    with pytest.raises(EauthAuthenticationError):
        client.run(low)
