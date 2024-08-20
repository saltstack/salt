import pytest

import salt.netapi
from salt.exceptions import EauthAuthenticationError, SaltInvocationError
from tests.support.mock import patch


@pytest.fixture
def client(salt_minion, salt_sub_minion, client_config):
    return salt.netapi.NetapiClient(client_config)


@pytest.mark.slow_test
def test_local(client, auth_creds, salt_minion, salt_sub_minion):
    low = {"client": "local", "tgt": "*", "fun": "test.ping", **auth_creds}

    with patch.dict(client.opts, {"netapi_enable_clients": ["local"]}):
        ret = client.run(low)
    assert ret == {salt_minion.id: True, salt_sub_minion.id: True}


@pytest.mark.slow_test
def test_local_batch(client, auth_creds, salt_minion, salt_sub_minion):
    low = {"client": "local_batch", "tgt": "*", "fun": "test.ping", **auth_creds}

    with patch.dict(client.opts, {"netapi_enable_clients": ["local_batch"]}):
        ret = client.run(low)
    assert ret
    # local_batch returns a generator
    ret = list(ret)
    assert ret
    assert {salt_minion.id: True} in ret
    assert {salt_sub_minion.id: True} in ret


def test_local_async(client, auth_creds, salt_minion, salt_sub_minion):
    low = {"client": "local_async", "tgt": "*", "fun": "test.ping", **auth_creds}

    with patch.dict(client.opts, {"netapi_enable_clients": ["local_async"]}):
        ret = client.run(low)

    assert "jid" in ret
    assert sorted(ret["minions"]) == sorted([salt_minion.id, salt_sub_minion.id])


def test_local_unauthenticated(client):
    low = {"client": "local", "tgt": "*", "fun": "test.ping"}

    with patch.dict(client.opts, {"netapi_enable_clients": ["local"]}):
        with pytest.raises(EauthAuthenticationError):
            client.run(low)


def test_local_disabled(client, auth_creds):
    low = {"client": "local", "tgt": "*", "fun": "test.ping", **auth_creds}

    ret = None
    with pytest.raises(SaltInvocationError):
        ret = client.run(low)

    assert ret is None


def test_local_batch_disabled(client, auth_creds):
    low = {"client": "local_batch", "tgt": "*", "fun": "test.ping", **auth_creds}

    ret = None
    with pytest.raises(SaltInvocationError):
        ret = client.run(low)

    assert ret is None


def test_local_subset_disabled(client, auth_creds):
    low = {
        "client": "local_subset",
        "tgt": "*",
        "fun": "test.ping",
        "subset": 1,
        **auth_creds,
    }

    ret = None
    with pytest.raises(SaltInvocationError):
        ret = client.run(low)

    assert ret is None


@pytest.mark.slow_test
def test_wheel(client, auth_creds):
    low = {"client": "wheel", "fun": "key.list_all", **auth_creds}

    with patch.dict(client.opts, {"netapi_enable_clients": ["wheel"]}):
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

    with patch.dict(client.opts, {"netapi_enable_clients": ["wheel_async"]}):
        ret = client.run(low)
    assert "jid" in ret
    assert "tag" in ret


def test_wheel_unauthenticated(client):
    low = {"client": "wheel", "tgt": "*", "fun": "test.ping"}

    with patch.dict(client.opts, {"netapi_enable_clients": ["wheel"]}):
        with pytest.raises(EauthAuthenticationError):
            client.run(low)


def test_wheel_disabled(client, auth_creds):
    low = {"client": "wheel", "tgt": "*", "fun": "test.ping", **auth_creds}

    ret = None
    with pytest.raises(SaltInvocationError):
        ret = client.run(low)

    assert ret is None


def test_wheel_async_disabled(client, auth_creds):
    low = {"client": "wheel_async", "tgt": "*", "fun": "test.ping", **auth_creds}

    ret = None
    with pytest.raises(SaltInvocationError):
        ret = client.run(low)

    assert ret is None


def test_runner_unauthenticated(client):
    low = {"client": "runner", "tgt": "*", "fun": "test.ping"}

    with patch.dict(client.opts, {"netapi_enable_clients": ["runner"]}):
        with pytest.raises(EauthAuthenticationError):
            client.run(low)


def test_runner_disabled(client, auth_creds):
    low = {"client": "runner", "tgt": "*", "fun": "test.ping", **auth_creds}

    ret = None
    with pytest.raises(SaltInvocationError):
        ret = client.run(low)

    assert ret is None
