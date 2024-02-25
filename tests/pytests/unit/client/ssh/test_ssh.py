import pytest

import salt.client.ssh.client
import salt.utils.msgpack
from salt.client import ssh
from tests.support.mock import MagicMock, Mock, patch

pytestmark = [
    pytest.mark.skip_if_binaries_missing("ssh", "ssh-keygen", check_all=True),
    pytest.mark.slow_test,
]


@pytest.fixture
def opts(tmp_path, temp_salt_master):
    updated_values = {
        "argv": [
            "ssh.set_auth_key",
            "root",
            "hobn+amNAXSBTiOXEqlBjGB...rsa root@master",
        ],
        "__role": "master",
        "cachedir": str(tmp_path),
        "extension_modules": str(tmp_path / "extmods"),
        "selected_target_option": "glob",
    }

    opts = temp_salt_master.config.copy()
    opts.update(updated_values)
    return opts


@pytest.fixture
def target():
    return {
        "passwd": "abc123",
        "ssh_options": None,
        "sudo": False,
        "identities_only": False,
        "host": "login1",
        "user": "root",
        "timeout": 65,
        "remote_port_forwards": None,
        "sudo_user": "",
        "port": "22",
        "priv": "/etc/salt/pki/master/ssh/salt-ssh.rsa",
    }


@pytest.fixture
def roster():
    return """
        localhost:
          host: 127.0.0.1
          port: 2827
        """


@pytest.mark.parametrize(
    "test_opts",
    [
        ("extra_filerefs", "salt://foobar", True),
        ("host", "testhost", False),
        ("ssh_user", "testuser", True),
        ("ssh_passwd", "testpasswd", True),
        ("ssh_port", 23, False),
        ("ssh_sudo", True, True),
        ("ssh_sudo_user", "sudouser", False),
        ("ssh_priv", "test_priv", True),
        ("ssh_priv_passwd", "sshpasswd", True),
        ("ssh_identities_only", True, True),
        ("ssh_remote_port_forwards", "test", True),
        ("ssh_options", ["test1", "test2"], True),
        ("ssh_max_procs", 2, True),
        ("ssh_askpass", True, True),
        ("ssh_key_deploy", True, True),
        ("ssh_update_roster", True, True),
        ("ssh_scan_ports", "test", True),
        ("ssh_scan_timeout", 1.0, True),
        ("ssh_timeout", 1, False),
        ("ssh_log_file", "/tmp/test", True),
        ("raw_shell", True, True),
        ("refresh_cache", True, True),
        ("roster", "/test", True),
        ("roster_file", "/test1", True),
        ("rosters", ["test1"], False),
        ("ignore_host_keys", True, True),
        ("min_extra_mods", "test", True),
        ("thin_extra_mods", "test1", True),
        ("verbose", True, True),
        ("static", True, True),
        ("ssh_wipe", True, True),
        ("rand_thin_dir", True, True),
        ("regen_thin", True, True),
        ("ssh_run_pre_flight", True, True),
        ("no_host_keys", True, True),
        ("saltfile", "/tmp/test", True),
        ("doesnotexist", None, False),
    ],
)
def test_ssh_kwargs(test_opts):
    """
    test all ssh kwargs are not excluded from kwargs
    when preparing the SSH opts
    """
    opt_key = test_opts[0]
    opt_value = test_opts[1]
    # Is the kwarg in salt.utils.parsers?
    in_parser = test_opts[2]

    opts = {
        "eauth": "auto",
        "username": "test",
        "password": "test",
        "client": "ssh",
        "tgt": "localhost",
        "fun": "test.ping",
        opt_key: opt_value,
    }
    client = salt.client.ssh.client.SSHClient(disable_custom_roster=True)
    if in_parser:
        ssh_kwargs = salt.utils.parsers.SaltSSHOptionParser().defaults
        assert opt_key in ssh_kwargs

    with patch("salt.roster.get_roster_file", MagicMock(return_value="")), patch(
        "salt.client.ssh.shell.gen_key"
    ), patch("salt.fileserver.Fileserver.update"), patch("salt.utils.thin.gen_thin"):
        ssh_obj = client._prep_ssh(**opts)
        assert ssh_obj.opts.get(opt_key, None) == opt_value


@pytest.mark.slow_test
def test_expand_target_ip_address(opts, roster):
    """
    test expand_target when target is root@<ip address>
    """
    host = "127.0.0.1"
    user = "test-user@"
    opts["tgt"] = user + host

    with patch("salt.utils.network.is_reachable_host", MagicMock(return_value=False)):
        client = ssh.SSH(opts)
    assert opts["tgt"] == user + host
    with patch(
        "salt.roster.get_roster_file", MagicMock(return_value="/etc/salt/roster")
    ), patch(
        "salt.client.ssh.compile_template",
        MagicMock(return_value=salt.utils.yaml.safe_load(roster)),
    ):
        client._expand_target()
    assert opts["tgt"] == host


def test_expand_target_no_host(opts, tmp_path):
    """
    test expand_target when host is not included in the rosterdata
    """
    host = "127.0.0.1"
    user = "test-user@"
    opts["tgt"] = user + host

    roster = """
        localhost: 127.0.0.1
        """
    roster_file = str(tmp_path / "test_roster_no_host")
    with salt.utils.files.fopen(roster_file, "w") as fp:
        salt.utils.yaml.safe_dump(salt.utils.yaml.safe_load(roster), fp)

    with patch("salt.utils.network.is_reachable_host", MagicMock(return_value=False)):
        client = ssh.SSH(opts)
    assert opts["tgt"] == user + host
    with patch("salt.roster.get_roster_file", MagicMock(return_value=roster_file)):
        client._expand_target()
    assert opts["tgt"] == host


def test_expand_target_dns(opts, roster):
    """
    test expand_target when target is root@<dns>
    """
    host = "localhost"
    user = "test-user@"
    opts["tgt"] = user + host

    with patch("salt.utils.network.is_reachable_host", MagicMock(return_value=False)):
        client = ssh.SSH(opts)
    assert opts["tgt"] == user + host
    with patch(
        "salt.roster.get_roster_file", MagicMock(return_value="/etc/salt/roster")
    ), patch(
        "salt.client.ssh.compile_template",
        MagicMock(return_value=salt.utils.yaml.safe_load(roster)),
    ):
        client._expand_target()
    assert opts["tgt"] == host


def test_expand_target_no_user(opts, roster):
    """
    test expand_target when no user defined
    """
    host = "127.0.0.1"
    opts["tgt"] = host

    with patch("salt.utils.network.is_reachable_host", MagicMock(return_value=False)):
        client = ssh.SSH(opts)
    assert opts["tgt"] == host

    with patch(
        "salt.roster.get_roster_file", MagicMock(return_value="/etc/salt/roster")
    ), patch(
        "salt.client.ssh.compile_template",
        MagicMock(return_value=salt.utils.yaml.safe_load(roster)),
    ):
        client._expand_target()
    assert opts["tgt"] == host


def test_update_targets_ip_address(opts):
    """
    test update_targets when host is ip address
    """
    host = "127.0.0.1"
    user = "test-user@"
    opts["tgt"] = user + host

    with patch("salt.utils.network.is_reachable_host", MagicMock(return_value=False)):
        client = ssh.SSH(opts)
    assert opts["tgt"] == user + host
    client._update_targets()
    assert opts["tgt"] == host
    assert client.targets[host]["user"] == user.split("@", maxsplit=1)[0]


def test_update_targets_dns(opts):
    """
    test update_targets when host is dns
    """
    host = "localhost"
    user = "test-user@"
    opts["tgt"] = user + host

    with patch("salt.utils.network.is_reachable_host", MagicMock(return_value=False)):
        client = ssh.SSH(opts)
    assert opts["tgt"] == user + host
    client._update_targets()
    assert opts["tgt"] == host
    assert client.targets[host]["user"] == user.split("@", maxsplit=1)[0]


def test_update_targets_no_user(opts):
    """
    test update_targets when no user defined
    """
    host = "127.0.0.1"
    opts["tgt"] = host

    with patch("salt.utils.network.is_reachable_host", MagicMock(return_value=False)):
        client = ssh.SSH(opts)
    assert opts["tgt"] == host
    client._update_targets()
    assert opts["tgt"] == host


def test_update_expand_target_dns(opts, roster):
    """
    test update_targets and expand_target when host is dns
    """
    host = "localhost"
    user = "test-user@"
    opts["tgt"] = user + host

    with patch("salt.utils.network.is_reachable_host", MagicMock(return_value=False)):
        client = ssh.SSH(opts)
    assert opts["tgt"] == user + host
    with patch(
        "salt.roster.get_roster_file", MagicMock(return_value="/etc/salt/roster")
    ), patch(
        "salt.client.ssh.compile_template",
        MagicMock(return_value=salt.utils.yaml.safe_load(roster)),
    ):
        client._expand_target()
    client._update_targets()
    assert opts["tgt"] == host
    assert client.targets[host]["user"] == user.split("@", maxsplit=1)[0]


def test_parse_tgt(opts):
    """
    test parse_tgt when user and host set on
    the ssh cli tgt
    """
    host = "localhost"
    user = "test-user@"
    opts["tgt"] = user + host

    with patch("salt.utils.network.is_reachable_host", MagicMock(return_value=False)):
        assert not opts.get("ssh_cli_tgt")
        client = ssh.SSH(opts)
        assert client.parse_tgt["hostname"] == host
        assert client.parse_tgt["user"] == user.split("@", maxsplit=1)[0]
        assert opts.get("ssh_cli_tgt") == user + host


def test_parse_tgt_no_user(opts):
    """
    test parse_tgt when only the host set on
    the ssh cli tgt
    """
    host = "localhost"
    opts["ssh_user"] = "ssh-usr"
    opts["tgt"] = host

    with patch("salt.utils.network.is_reachable_host", MagicMock(return_value=False)):
        assert not opts.get("ssh_cli_tgt")
        client = ssh.SSH(opts)
        assert client.parse_tgt["hostname"] == host
        assert client.parse_tgt["user"] == opts["ssh_user"]
        assert opts.get("ssh_cli_tgt") == host


def test_extra_filerefs(tmp_path, opts):
    """
    test "extra_filerefs" are not excluded from kwargs
    when preparing the SSH opts
    """
    ssh_opts = {
        "eauth": "auto",
        "username": "test",
        "password": "test",
        "client": "ssh",
        "tgt": "localhost",
        "fun": "test.ping",
        "ssh_port": 22,
        "extra_filerefs": "salt://foobar",
    }
    roster = str(tmp_path / "roster")
    client = salt.client.ssh.client.SSHClient(mopts=opts, disable_custom_roster=True)
    with patch("salt.roster.get_roster_file", MagicMock(return_value=roster)):
        ssh_obj = client._prep_ssh(**ssh_opts)
        assert ssh_obj.opts.get("extra_filerefs", None) == "salt://foobar"


def test_key_deploy_permission_denied_scp(tmp_path, opts):
    """
    test "key_deploy" function when
    permission denied authentication error
    when attempting to use scp to copy file
    to target
    """
    host = "localhost"
    passwd = "password"
    usr = "ssh-usr"
    opts["ssh_user"] = usr
    opts["tgt"] = host

    ssh_ret = {
        host: {
            "stdout": "\rroot@192.168.1.187's password: \n\rroot@192.168.1.187's password: \n\rroot@192.168.1.187's password: \n",
            "stderr": "Permission denied, please try again.\nPermission denied, please try again.\nroot@192.168.1.187: Permission denied (publickey,gssapi-keyex,gssapi-with-micimport pudb; pu.dbassword).\nscp: Connection closed\n",
            "retcode": 255,
        }
    }
    key_run_ret = {
        "localhost": {
            "jid": "20230922155652279959",
            "return": "test",
            "retcode": 0,
            "id": "test",
            "fun": "cmd.run",
            "fun_args": ["echo test"],
        }
    }
    patch_roster_file = patch("salt.roster.get_roster_file", MagicMock(return_value=""))
    with patch_roster_file:
        client = ssh.SSH(opts)
    patch_input = patch("builtins.input", side_effect=["y"])
    patch_getpass = patch("getpass.getpass", return_value=["password"])
    mock_key_run = MagicMock(return_value=key_run_ret)
    patch_key_run = patch("salt.client.ssh.SSH._key_deploy_run", mock_key_run)
    with patch_input, patch_getpass, patch_key_run:
        ret = client.key_deploy(host, ssh_ret)
    assert mock_key_run.call_args_list[0][0] == (
        host,
        {"passwd": [passwd], "host": host, "user": usr},
        True,
    )
    assert ret == key_run_ret
    assert mock_key_run.call_count == 1


def test_key_deploy_permission_denied_file_scp(tmp_path, opts):
    """
    test "key_deploy" function when permission denied
    due to not having access to copy the file to the target
    We do not want to deploy the key, because this is not
    an authentication to the target error.
    """
    host = "localhost"
    passwd = "password"
    usr = "ssh-usr"
    opts["ssh_user"] = usr
    opts["tgt"] = host

    mock_key_run = MagicMock(return_value=False)
    patch_key_run = patch("salt.client.ssh.SSH._key_deploy_run", mock_key_run)

    ssh_ret = {
        "localhost": {
            "stdout": "",
            "stderr": 'scp: dest open "/tmp/preflight.sh": Permission denied\nscp: failed to upload file /etc/salt/preflight.sh to /tmp/preflight.sh\n',
            "retcode": 1,
        }
    }
    patch_roster_file = patch("salt.roster.get_roster_file", MagicMock(return_value=""))
    with patch_roster_file:
        client = ssh.SSH(opts)
    ret = client.key_deploy(host, ssh_ret)
    assert ret == ssh_ret
    assert mock_key_run.call_count == 0


def test_key_deploy_no_permission_denied(tmp_path, opts):
    """
    test "key_deploy" function when no permission denied
    is returned
    """
    host = "localhost"
    passwd = "password"
    usr = "ssh-usr"
    opts["ssh_user"] = usr
    opts["tgt"] = host

    mock_key_run = MagicMock(return_value=False)
    patch_key_run = patch("salt.client.ssh.SSH._key_deploy_run", mock_key_run)
    ssh_ret = {
        "localhost": {
            "jid": "20230922161937998385",
            "return": "test",
            "retcode": 0,
            "id": "test",
            "fun": "cmd.run",
            "fun_args": ["echo test"],
        }
    }
    patch_roster_file = patch("salt.roster.get_roster_file", MagicMock(return_value=""))
    with patch_roster_file:
        client = ssh.SSH(opts)
    ret = client.key_deploy(host, ssh_ret)
    assert ret == ssh_ret
    assert mock_key_run.call_count == 0


@pytest.mark.parametrize("retcode,expected", [("null", None), ('"foo"', "foo")])
def test_handle_routine_remote_invalid_retcode(opts, target, retcode, expected, caplog):
    """
    Ensure that if a remote returns an invalid retcode as part of the return dict,
    the final exit code is still an integer and set to 1 at least.
    """
    single_ret = (f'{{"local": {{"retcode": {retcode}, "return": "foo"}}}}', "", 0)
    opts["tgt"] = "localhost"
    single = MagicMock(spec=ssh.Single)
    single.id = "localhost"
    single.run.return_value = single_ret
    que = Mock()

    with patch("salt.roster.get_roster_file", MagicMock(return_value="")), patch(
        "salt.client.ssh.Single", autospec=True, return_value=single
    ):
        client = ssh.SSH(opts)
        client.handle_routine(que, opts, "localhost", target)
    que.put.assert_called_once_with(
        ({"id": "localhost", "ret": {"retcode": expected, "return": "foo"}}, 1)
    )
    assert f"Host 'localhost' reported an invalid retcode: '{expected}'" in caplog.text


def test_handle_routine_single_run_invalid_retcode(opts, target, caplog):
    """
    Ensure that if Single.run() call returns an invalid retcode,
    the final exit code is still an integer and set to 1 at least.
    """
    single_ret = ("", "Something went seriously wrong", None)
    opts["tgt"] = "localhost"
    single = MagicMock(spec=ssh.Single)
    single.id = "localhost"
    single.run.return_value = single_ret
    que = Mock()

    with patch("salt.roster.get_roster_file", MagicMock(return_value="")), patch(
        "salt.client.ssh.Single", autospec=True, return_value=single
    ):
        client = ssh.SSH(opts)
        client.handle_routine(que, opts, "localhost", target)
    que.put.assert_called_once_with(
        (
            {
                "id": "localhost",
                "ret": {
                    "stdout": "",
                    "stderr": "Something went seriously wrong",
                    "retcode": 1,
                },
            },
            1,
        )
    )
    assert "Got an invalid retcode for host 'localhost': 'None'" in caplog.text
