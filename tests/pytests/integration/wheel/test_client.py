import pytest

import salt.auth

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skip_if_not_root,
    pytest.mark.destructive_test,
    pytest.mark.windows_whitelisted,
]


def test_master_call(client, auth_creds, salt_auto_account):
    """
    Test executing master_call with lowdata

    The choice of using key.list_all for this is arbitrary and should be
    changed to some mocked function that is more testing friendly.
    """
    low = {"client": "wheel", "fun": "key.list_all", "print_event": False, **auth_creds}
    ret = client.master_call(**low)
    assert ret
    assert "data" in ret
    data = ret["data"]
    assert data["success"] is True
    assert data["user"] == salt_auto_account.username
    assert data["fun"] == "wheel.key.list_all"
    assert data["return"]
    assert data["return"]["local"] == ["master.pem", "master.pub"]


def test_token(client, client_config, auth_creds, salt_auto_account):
    """
    Test executing master_call with lowdata

    The choice of using key.list_all for this is arbitrary and should be
    changed to some mocked function that is more testing friendly.
    """
    auth = salt.auth.LoadAuth(client_config)
    token = auth.mk_token(auth_creds)

    ret = client.master_call(
        **{
            "client": "wheel",
            "fun": "key.list_all",
            "token": token["token"],
            "print_event": False,
        }
    )
    assert ret
    assert "data" in ret
    data = ret["data"]
    assert data["success"] is True
    assert data["user"] == salt_auto_account.username
    assert data["fun"] == "wheel.key.list_all"
    assert data["return"]
    assert data["return"]["local"] == ["master.pem", "master.pub"]


def test_cmd_sync(client, auth_creds, salt_auto_account):
    low = {"client": "async", "fun": "key.list_all", "print_event": False, **auth_creds}

    ret = client.cmd_sync(low)
    assert ret
    assert "data" in ret
    data = ret["data"]
    assert data["success"] is True
    assert data["user"] == salt_auto_account.username
    assert data["fun"] == "wheel.key.list_all"
    assert data["return"]
    assert data["return"]["local"] == ["master.pem", "master.pub"]


# Remove this skipIf when https://github.com/saltstack/salt/issues/39616 is resolved
@pytest.mark.skip_on_windows(reason="Causes pickling error on Windows: Issue #39616")
def test_cmd_async(client, auth_creds):
    low = {
        "client": "wheel_async",
        "fun": "key.list_all",
        "print_event": False,
        **auth_creds,
    }

    ret = client.cmd_async(low)
    # Being an async command, we won't get any data back, just the JID and the TAG
    assert ret
    assert "jid" in ret
    assert "tag" in ret
    assert ret["tag"] == "salt/wheel/{}".format(ret["jid"])


def test_cmd_sync_w_arg(client, auth_creds, salt_auto_account):
    low = {"fun": "key.finger", "match": "*", "print_event": False, **auth_creds}
    ret = client.cmd_sync(low)
    assert ret
    assert "data" in ret
    data = ret["data"]
    assert data["success"] is True
    assert data["user"] == salt_auto_account.username
    assert data["fun"] == "wheel.key.finger"
    assert data["return"]
    assert data["return"]["local"]
    assert "master.pem" in data["return"]["local"]
    assert "master.pub" in data["return"]["local"]


def test_wildcard_auth(client):
    # This test passes because of the following master config
    # external_auth:
    #   auto:
    #     '*':
    #       - '@wheel'
    #       - '@runner'
    #       - test.*
    username = "the_s0und_of_t3ch"
    low = {
        "username": username,
        "password": "willrockyou",
        "eauth": "auto",
        "fun": "key.list_all",
        "print_event": False,
    }
    ret = client.cmd_sync(low)
    assert ret
    assert "data" in ret
    data = ret["data"]
    assert data["success"] is True
    assert data["user"] == username
    assert data["fun"] == "wheel.key.list_all"
    assert data["return"]
    assert data["return"]["local"] == ["master.pem", "master.pub"]
