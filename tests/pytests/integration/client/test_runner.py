import pytest

import salt.auth
import salt.runner

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skip_if_not_root,
    pytest.mark.destructive_test,
    pytest.mark.windows_whitelisted,
]


@pytest.fixture
def client(client_config):
    return salt.runner.Runner(client_config)


def test_eauth(client, auth_creds):
    """
    Test executing master_call with lowdata

    The choice of using error.error for this is arbitrary and should be
    changed to some mocked function that is more testing friendly.
    """
    low = {"client": "runner", "fun": "error.error", **auth_creds}

    ret = client.master_call(**low)
    assert ret
    assert "jid" in ret
    assert "tag" in ret
    assert ret["tag"] == "salt/run/{}".format(ret["jid"])


def test_token(client, client_config, auth_creds):
    """
    Test executing master_call with lowdata

    The choice of using error.error for this is arbitrary and should be
    changed to some mocked function that is more testing friendly.
    """
    auth = salt.auth.LoadAuth(client_config)
    token = auth.mk_token(auth_creds)

    low = {
        "client": "runner",
        "fun": "error.error",
        "token": token["token"],
    }
    ret = client.master_call(**low)
    assert ret
    assert "jid" in ret
    assert "tag" in ret
    assert ret["tag"] == "salt/run/{}".format(ret["jid"])


def test_cmd_sync(client, auth_creds):
    low = {
        "client": "runner",
        "fun": "error.error",
        **auth_creds,
    }

    ret = client.cmd_sync(low.copy())
    assert ret == {}


def test_cmd_async(client, auth_creds):
    low = {
        "client": "runner",
        "fun": "error.error",
        **auth_creds,
    }

    ret = client.cmd_async(low.copy())
    assert ret
    assert "jid" in ret
    assert "tag" in ret
    assert ret["tag"] == "salt/run/{}".format(ret["jid"])


def test_cmd_sync_w_arg(client, auth_creds):
    low = {"fun": "test.arg", "foo": "Foo!", "bar": "Bar!", **auth_creds}

    ret = client.cmd_sync(low.copy())
    assert ret
    assert "kwargs" in ret
    assert ret["kwargs"]["foo"] == "Foo!"
    assert ret["kwargs"]["bar"] == "Bar!"


def test_wildcard_auth(client):
    # This test passes because of the following master config
    # external_auth:
    #   auto:
    #     '*':
    #       - '@wheel'
    #       - '@runner'
    #       - test.*
    low = {
        "fun": "test.arg",
        "foo": "Foo!",
        "bar": "Bar!",
        "username": "the_s0und_of_t3ch",
        "password": "willrockyou",
        "eauth": "auto",
    }

    ret = client.cmd_sync(low.copy())
    assert ret
    assert "kwargs" in ret
    assert ret["kwargs"]["foo"] == "Foo!"
    assert ret["kwargs"]["bar"] == "Bar!"


def test_full_return_kwarg(client, auth_creds):
    low = {"fun": "test.arg", **auth_creds}
    ret = client.cmd_sync(low.copy(), full_return=True)
    assert ret
    assert "data" in ret
    assert "success" in ret["data"]


def test_cmd_sync_arg_kwarg_parsing(client, auth_creds):
    low = {
        "client": "runner",
        "fun": "test.arg",
        "arg": ["foo", "bar=off", "baz={qux: 123}"],
        "kwarg": {"quux": "Quux"},
        "quuz": "on",
        **auth_creds,
    }

    ret = client.cmd_sync(low.copy())
    assert ret
    assert ret == {
        "args": ["foo"],
        "kwargs": {"bar": False, "baz": {"qux": 123}, "quux": "Quux", "quuz": "on"},
    }


def test_invalid_kwargs_are_ignored(client, auth_creds):
    low = {
        "client": "runner",
        "fun": "test.metasyntactic",
        "thiskwargisbad": "justpretendimnothere",
        **auth_creds,
    }

    ret = client.cmd_sync(low.copy())
    assert ret
    assert ret[0] == "foo"


def test_get_docs(client):
    ret = client.get_docs(arg="*")
    assert "auth.del_token" in ret
    assert "auth.mk_token" in ret
    assert "cache.clear_pillar" in ret
    assert "cache.grains" in ret
    assert "state.soft_kill" in ret
    assert "virt.start" in ret
    assert "test.arg" in ret
