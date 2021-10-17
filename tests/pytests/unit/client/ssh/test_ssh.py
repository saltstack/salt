import pytest
import salt.client.ssh.client
import salt.utils.msgpack
from salt.client import ssh
from tests.support.mock import MagicMock, patch

pytestmark = [
    pytest.mark.skip_if_binaries_missing("ssh", "ssh-keygen", check_all=True),
]


@pytest.fixture
def ssh_target(tmpdir):
    argv = [
        "ssh.set_auth_key",
        "root",
        "hobn+amNAXSBTiOXEqlBjGB...rsa root@master",
    ]

    opts = {
        "argv": argv,
        "__role": "master",
        "cachedir": tmpdir.strpath,
        "extension_modules": tmpdir.join("extmods").strpath,
    }
    target = {
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
    return opts, target


@pytest.mark.skip_on_windows(reason="SSH_PY_SHIM not set on windows")
def test_cmd_block_python_version_error(ssh_target):
    opts = ssh_target[0]
    target = ssh_target[1]

    single = ssh.Single(
        opts,
        opts["argv"],
        "localhost",
        mods={},
        fsclient=None,
        thin=salt.utils.thin.thin_path(opts["cachedir"]),
        mine=False,
        winrm=False,
        **target
    )
    mock_shim = MagicMock(
        return_value=(("", "ERROR: Unable to locate appropriate python command\n", 10))
    )
    patch_shim = patch("salt.client.ssh.Single.shim_cmd", mock_shim)
    with patch_shim:
        ret = single.cmd_block()
        assert "ERROR: Python version error. Recommendation(s) follow:" in ret[0]


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

    with patch("salt.roster.get_roster_file", MagicMock(return_value="")):
        ssh_obj = client._prep_ssh(**opts)
        assert ssh_obj.opts.get(opt_key, None) == opt_value
