import pytest

import salt.netapi
from salt.exceptions import EauthAuthenticationError, SaltInvocationError
from tests.support.helpers import SaveRequestsPostHandler, Webserver
from tests.support.mock import patch

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.requires_sshd_server,
]


@pytest.fixture
def client_config(client_config):
    client_config["netapi_enable_clients"] = ["ssh"]
    return client_config


@pytest.fixture
def client(client_config, salt_minion):
    return salt.netapi.NetapiClient(client_config)


@pytest.fixture
def rosters_dir(salt_ssh_roster_file):
    return str(salt_ssh_roster_file.parent)


@pytest.fixture
def ssh_priv_key(sshd_server):
    return str(sshd_server.config_dir / "client_key")


@pytest.fixture(scope="module")
def webserver():
    with Webserver(handler=SaveRequestsPostHandler) as server:
        yield server


@pytest.fixture(scope="module")
def webserver_root(webserver):
    return webserver.web_root


@pytest.fixture(scope="module")
def webserver_handler(webserver):
    return webserver.handler


@pytest.fixture(scope="module")
def salt_auth_account_1(salt_auth_account_1_factory):
    with salt_auth_account_1_factory as account:
        yield account


@pytest.fixture(scope="module")
def salt_auto_account(salt_auto_account_factory):
    with salt_auto_account_factory as account:
        yield account


def test_ssh(client, auth_creds, salt_ssh_roster_file, rosters_dir, ssh_priv_key):
    low = {
        "client": "ssh",
        "tgt": "localhost",
        "fun": "test.ping",
        "ignore_host_keys": True,
        "roster_file": str(salt_ssh_roster_file),
        "rosters": [rosters_dir],
        "ssh_priv": ssh_priv_key,
        **auth_creds,
    }

    ret = client.run(low)

    assert "localhost" in ret
    assert "return" in ret["localhost"]
    assert ret["localhost"]["return"] is True
    assert ret["localhost"]["id"] == "localhost"
    assert ret["localhost"]["fun"] == "test.ping"


def test_ssh_unauthenticated(client):
    low = {"client": "ssh", "tgt": "localhost", "fun": "test.ping"}

    with pytest.raises(EauthAuthenticationError):
        client.run(low)


def test_ssh_unauthenticated_raw_shell_curl(client, webserver_root, webserver_handler):

    fun = "-o ProxyCommand curl {}".format(webserver_root)
    low = {"client": "ssh", "tgt": "localhost", "fun": fun, "raw_shell": True}

    with pytest.raises(EauthAuthenticationError):
        client.run(low)

    assert webserver_handler.received_requests == []


def test_ssh_unauthenticated_raw_shell_touch(client, tmp_path):

    badfile = tmp_path / "badfile.txt"
    fun = "-o ProxyCommand touch {}".format(badfile)
    low = {"client": "ssh", "tgt": "localhost", "fun": fun, "raw_shell": True}

    with pytest.raises(EauthAuthenticationError):
        client.run(low)

    assert badfile.exists() is False


def test_ssh_authenticated_raw_shell_disabled(client, tmp_path):

    badfile = tmp_path / "badfile.txt"
    fun = "-o ProxyCommand touch {}".format(badfile)
    low = {"client": "ssh", "tgt": "localhost", "fun": fun, "raw_shell": True}

    with patch.dict(client.opts, {"netapi_allow_raw_shell": False}):
        with pytest.raises(EauthAuthenticationError):
            client.run(low)

    assert badfile.exists() is False


def test_ssh_disabled(client, auth_creds):
    low = {"client": "ssh", "tgt": "localhost", "fun": "test.ping", **auth_creds}

    ret = None
    with patch.dict(client.opts, {"netapi_enable_clients": []}):
        with pytest.raises(SaltInvocationError):
            ret = client.run(low)

    assert ret is None


def test_shell_inject_ssh_priv(
    client, salt_ssh_roster_file, rosters_dir, tmp_path, salt_auto_account
):
    """
    Verify CVE-2020-16846 for ssh_priv variable
    """
    # ZDI-CAN-11143
    path = tmp_path / "test-11143"
    tgts = ["repo.saltproject.io", "www.zerodayinitiative.com"]
    for tgt in tgts:
        low = {
            "roster": "cache",
            "client": "ssh",
            "tgt": tgt,
            "ssh_priv": "aaa|id>{} #".format(path),
            "fun": "test.ping",
            "eauth": "auto",
            "username": salt_auto_account.username,
            "password": salt_auto_account.password,
            "roster_file": str(salt_ssh_roster_file),
            "rosters": [rosters_dir],
        }
        ret = client.run(low)
        if ret:
            break
    assert path.exists() is False
    assert not ret[tgt]["stdout"]
    assert ret[tgt]["stderr"]


def test_shell_inject_tgt(client, salt_ssh_roster_file, tmp_path, salt_auto_account):
    """
    Verify CVE-2020-16846 for tgt variable
    """
    # ZDI-CAN-11167
    path = tmp_path / "test-11167"
    low = {
        "roster": "cache",
        "client": "ssh",
        "tgt": "root|id>{} #@127.0.0.1".format(path),
        "roster_file": str(salt_ssh_roster_file),
        "rosters": "/",
        "fun": "test.ping",
        "eauth": "auto",
        "username": salt_auto_account.username,
        "password": salt_auto_account.password,
        "ignore_host_keys": True,
    }
    ret = client.run(low)
    assert path.exists() is False
    assert not ret["127.0.0.1"]["stdout"]
    assert ret["127.0.0.1"]["stderr"]


def test_shell_inject_ssh_options(
    client, salt_ssh_roster_file, tmp_path, salt_auto_account
):
    """
    Verify CVE-2020-16846 for ssh_options
    """
    # ZDI-CAN-11169
    path = tmp_path / "test-11169"
    low = {
        "roster": "cache",
        "client": "ssh",
        "tgt": "127.0.0.1",
        "renderer": "jinja|yaml",
        "fun": "test.ping",
        "eauth": "auto",
        "username": salt_auto_account.username,
        "password": salt_auto_account.password,
        "roster_file": str(salt_ssh_roster_file),
        "rosters": "/",
        "ssh_options": ["|id>{} #".format(path), "lol"],
    }
    ret = client.run(low)
    assert path.exists() is False
    assert not ret["127.0.0.1"]["stdout"]
    assert ret["127.0.0.1"]["stderr"]


def test_shell_inject_ssh_port(
    client, salt_ssh_roster_file, tmp_path, salt_auto_account
):
    """
    Verify CVE-2020-16846 for ssh_port variable
    """
    # ZDI-CAN-11172
    path = tmp_path / "test-11172"
    low = {
        "roster": "cache",
        "client": "ssh",
        "tgt": "127.0.0.1",
        "renderer": "jinja|yaml",
        "fun": "test.ping",
        "eauth": "auto",
        "username": salt_auto_account.username,
        "password": salt_auto_account.password,
        "roster_file": str(salt_ssh_roster_file),
        "rosters": "/",
        "ssh_port": "hhhhh|id>{} #".format(path),
        "ignore_host_keys": True,
    }
    ret = client.run(low)
    assert path.exists() is False
    assert not ret["127.0.0.1"]["stdout"]
    assert ret["127.0.0.1"]["stderr"]


def test_shell_inject_remote_port_forwards(
    client, salt_ssh_roster_file, tmp_path, salt_auto_account
):
    """
    Verify CVE-2020-16846 for remote_port_forwards variable
    """
    # ZDI-CAN-11173
    path = tmp_path / "test-1173"
    low = {
        "roster": "cache",
        "client": "ssh",
        "tgt": "127.0.0.1",
        "renderer": "jinja|yaml",
        "fun": "test.ping",
        "roster_file": str(salt_ssh_roster_file),
        "rosters": "/",
        "ssh_remote_port_forwards": "hhhhh|id>{} #, lol".format(path),
        "eauth": "auto",
        "username": salt_auto_account.username,
        "password": salt_auto_account.password,
        "ignore_host_keys": True,
    }
    ret = client.run(low)
    assert path.exists() is False
    assert not ret["127.0.0.1"]["stdout"]
    assert ret["127.0.0.1"]["stderr"]


def test_extra_mods(client, ssh_priv_key, rosters_dir, tmp_path, salt_auth_account_1):
    """
    validate input from extra_mods
    """
    path = tmp_path / "test_extra_mods"
    low = {
        "client": "ssh",
        "tgt": "localhost",
        "fun": "test.ping",
        "roster_file": "roster",
        "rosters": [rosters_dir],
        "ssh_priv": ssh_priv_key,
        "eauth": "pam",
        "username": salt_auth_account_1.username,
        "password": salt_auth_account_1.password,
        "regen_thin": True,
        "thin_extra_mods": "';touch {};'".format(path),
    }

    ret = client.run(low)
    assert path.exists() is False
    assert "localhost" in ret
    assert "return" in ret["localhost"]
    assert ret["localhost"]["return"] is True


def test_ssh_auth_bypass(client, salt_ssh_roster_file):
    """
    CVE-2020-25592 - Bogus eauth raises exception.
    """
    low = {
        "roster": "cache",
        "client": "ssh",
        "tgt": "127.0.0.1",
        "renderer": "jinja|yaml",
        "fun": "test.ping",
        "roster_file": str(salt_ssh_roster_file),
        "rosters": "/",
        "eauth": "xx",
        "ignore_host_keys": True,
    }
    with pytest.raises(EauthAuthenticationError):
        client.run(low)


def test_ssh_auth_valid(client, ssh_priv_key, rosters_dir, salt_auth_account_1):
    """
    CVE-2020-25592 - Valid eauth works as expected.
    """
    low = {
        "client": "ssh",
        "tgt": "localhost",
        "fun": "test.ping",
        "roster_file": "roster",
        "rosters": [rosters_dir],
        "ssh_priv": ssh_priv_key,
        "eauth": "pam",
        "username": salt_auth_account_1.username,
        "password": salt_auth_account_1.password,
    }
    ret = client.run(low)
    assert "localhost" in ret
    assert "return" in ret["localhost"]
    assert ret["localhost"]["return"] is True


def test_ssh_auth_invalid(client, rosters_dir, ssh_priv_key, salt_auth_account_1):
    """
    CVE-2020-25592 - Wrong password raises exception.
    """
    low = {
        "client": "ssh",
        "tgt": "localhost",
        "fun": "test.ping",
        "roster_file": "roster",
        "rosters": [rosters_dir],
        "ssh_priv": ssh_priv_key,
        "eauth": "pam",
        "username": salt_auth_account_1.username,
        "password": "notvalidpassword",
    }
    with pytest.raises(EauthAuthenticationError):
        client.run(low)


def test_ssh_auth_invalid_acl(client, rosters_dir, ssh_priv_key, salt_auth_account_1):
    """
    CVE-2020-25592 - Eauth ACL enforced.
    """
    low = {
        "client": "ssh",
        "tgt": "localhost",
        "fun": "at.at",
        "args": ["12:05am", "echo foo"],
        "roster_file": "roster",
        "rosters": [rosters_dir],
        "ssh_priv": ssh_priv_key,
        "eauth": "pam",
        "username": salt_auth_account_1.username,
        "password": "notvalidpassword",
    }
    with pytest.raises(EauthAuthenticationError):
        client.run(low)


def test_ssh_auth_token(client, rosters_dir, ssh_priv_key, salt_auth_account_1):
    """
    CVE-2020-25592 - Eauth tokens work as expected.
    """
    low = {
        "eauth": "pam",
        "username": salt_auth_account_1.username,
        "password": salt_auth_account_1.password,
    }
    ret = client.loadauth.mk_token(low)
    assert "token" in ret
    assert ret["token"]

    low = {
        "client": "ssh",
        "tgt": "localhost",
        "fun": "test.ping",
        "roster_file": "roster",
        "rosters": [rosters_dir],
        "ssh_priv": ssh_priv_key,
        "token": ret["token"],
    }
    ret = client.run(low)
    assert "localhost" in ret
    assert "return" in ret["localhost"]
    assert ret["localhost"]["return"] is True


def test_ssh_cve_2021_3197_a(
    client, rosters_dir, ssh_priv_key, salt_auth_account_1, tmp_path
):
    exploited_path = tmp_path / "exploited"
    assert exploited_path.exists() is False
    low = {
        "eauth": "auto",
        "username": salt_auth_account_1.username,
        "password": salt_auth_account_1.password,
        "client": "ssh",
        "tgt": "localhost",
        "fun": "test.ping",
        "ssh_port": '22 -o ProxyCommand="touch {}"'.format(exploited_path),
        "ssh_priv": ssh_priv_key,
        "roster_file": "roster",
        "rosters": [rosters_dir],
    }
    ret = client.run(low)
    assert exploited_path.exists() is False
    assert "localhost" in ret
    assert ret["localhost"]["return"] is True


def test_ssh_cve_2021_3197_b(
    client, rosters_dir, ssh_priv_key, salt_auth_account_1, tmp_path
):
    exploited_path = tmp_path / "exploited"
    assert exploited_path.exists() is False
    low = {
        "eauth": "auto",
        "username": salt_auth_account_1.username,
        "password": salt_auth_account_1.password,
        "client": "ssh",
        "tgt": "localhost",
        "fun": "test.ping",
        "ssh_port": 22,
        "ssh_options": ['ProxyCommand="touch {}"'.format(exploited_path)],
        "ssh_priv": ssh_priv_key,
        "roster_file": "roster",
        "rosters": [rosters_dir],
    }
    ret = client.run(low)
    assert exploited_path.exists() is False
    assert "localhost" in ret
    assert "return" in ret["localhost"]
    assert ret["localhost"]["return"] is True
