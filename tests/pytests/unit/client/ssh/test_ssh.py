import pytest

import salt.client.ssh.shell
import salt.config
import salt.utils.files
import salt.utils.network
import salt.utils.platform
import salt.utils.yaml
from salt.client import ssh
from tests.support.mock import ANY, MagicMock, patch

pytestmark = [
    pytest.mark.skipif(
        not salt.utils.path.which("ssh"), reason="No ssh binary found in path"
    ),
    pytest.mark.skip_on_windows(reason="Not supported on Windows"),
]


@pytest.fixture
def opts(tmp_path):
    opts = salt.config.DEFAULT_MASTER_OPTS.copy()
    opts["optimization_order"] = [0]
    opts["extension_modules"] = ""
    opts["pki_dir"] = str(tmp_path / "pki")
    opts["cachedir"] = str(tmp_path / "cache")
    opts["sock_dir"] = str(tmp_path / "sock")
    opts["token_dir"] = str(tmp_path / "tokens")
    opts["syndic_dir"] = str(tmp_path / "syndics")
    opts["sqlite_queue_dir"] = str(tmp_path / "queue")
    opts["ssh_max_procs"] = 1
    opts["ssh_user"] = "root"
    opts["ssh_passwd"] = ""
    opts["ssh_priv"] = ""
    opts["ssh_port"] = "22"
    opts["ssh_sudo"] = False
    opts["ssh_sudo_user"] = ""
    opts["ssh_scan_ports"] = "22"
    opts["ssh_scan_timeout"] = 0.01
    opts["ssh_identities_only"] = False
    opts["ssh_log_file"] = str(tmp_path / "ssh_log")
    opts["ssh_config_file"] = str(tmp_path / "ssh_config")
    opts["tgt"] = "localhost"
    opts["selected_target_option"] = "glob"
    opts["argv"] = ["test.ping"]
    return opts


@pytest.fixture
def roster(tmp_path):
    return """
        localhost:
          host: 127.0.0.1
          port: 2827
        """


def test_ssh_kwargs(opts, roster):
    """
    test ssh_kwargs
    """
    opts["ssh_user"] = "test-user"
    opts["ssh_port"] = "2827"
    opts["ssh_passwd"] = "abc123"
    opts["ssh_sudo"] = True
    opts["ssh_sudo_user"] = "sudo-user"
    opts["ssh_identities_only"] = True

    with patch("salt.roster.get_roster_file", MagicMock(return_value="")), patch(
        "salt.client.ssh.SSH.handle_ssh", MagicMock(return_value=[])
    ):
        client = ssh.SSH(opts)
        # Verify kwargs
        assert client.defaults["user"] == "test-user"
        assert client.defaults["port"] == "2827"
        assert client.defaults["passwd"] == "abc123"
        assert client.defaults["sudo"] is True
        assert client.defaults["sudo_user"] == "sudo-user"
        assert client.defaults["identities_only"] is True


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
    host = "localhost"
    user = ""
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

    client.targets = {}
    client._update_targets()
    assert host in client.targets


def test_update_targets_dns(opts):
    """
    test update_targets when host is dns
    """
    host = "localhost"
    user = "test-user@"
    opts["tgt"] = user + host

    with patch("salt.utils.network.is_reachable_host", MagicMock(return_value=False)):
        client = ssh.SSH(opts)

    client.targets = {}
    client._update_targets()
    assert host in client.targets


def test_update_targets_no_user(opts):
    """
    test update_targets when no user
    """
    host = "localhost"
    opts["tgt"] = host

    with patch("salt.utils.network.is_reachable_host", MagicMock(return_value=False)):
        client = ssh.SSH(opts)

    client.targets = {}
    client._update_targets()
    assert host in client.targets


def test_update_expand_target_dns(opts, roster):
    """
    test update_targets expansion
    """
    host = "localhost"
    user = "test-user@"
    opts["tgt"] = user + host

    with patch("salt.utils.network.is_reachable_host", MagicMock(return_value=True)):
        with patch(
            "salt.roster.get_roster_file", MagicMock(return_value="/etc/salt/roster")
        ), patch(
            "salt.client.ssh.compile_template",
            MagicMock(return_value=salt.utils.yaml.safe_load(roster)),
        ):
            client = ssh.SSH(opts)
    assert host in client.targets


def test_parse_tgt(opts):
    """
    test parse_tgt when target is root@localhost
    """
    host = "localhost"
    user = "root"
    opts["tgt"] = f"{user}@{host}"
    with patch("salt.utils.network.is_reachable_host", MagicMock(return_value=False)):
        client = ssh.SSH(opts)
    ret = client.parse_tgt
    assert ret["user"] == user
    assert ret["hostname"] == host


def test_parse_tgt_no_user(opts):
    """
    test parse_tgt when target is localhost
    """
    host = "localhost"
    opts["tgt"] = host
    with patch("salt.utils.network.is_reachable_host", MagicMock(return_value=False)):
        client = ssh.SSH(opts)
    ret = client.parse_tgt
    assert ret["user"] == "root"
    assert ret["hostname"] == host


def test_extra_filerefs(opts):
    """
    test extra_filerefs
    """
    opts["extra_filerefs"] = "salt://foo,salt://bar"
    with patch("salt.roster.get_roster_file", MagicMock(return_value="")), patch(
        "salt.client.ssh.SSH.handle_ssh", MagicMock(return_value=[])
    ):
        client = ssh.SSH(opts)
        assert "salt://foo" in client.opts["extra_filerefs"]
        assert "salt://bar" in client.opts["extra_filerefs"]


def test_key_deploy_permission_denied_scp(opts):
    """
    test key_deploy when scp fails with permission denied
    """
    host = "localhost"
    opts["tgt"] = host
    expected = {host: "Permission denied (publickey)"}
    handle_ssh_ret = [({host: "Permission denied (publickey)"}, 255)]

    # Mock Single object and its run method
    single = MagicMock(spec=ssh.Single)
    single.id = host
    single.run.return_value = ("Permission denied (publickey)", "", 255)

    with patch("salt.roster.get_roster_file", MagicMock(return_value="")), patch(
        "salt.client.ssh.SSH.handle_ssh", MagicMock(return_value=handle_ssh_ret)
    ), patch(
        "salt.client.ssh.SSH.key_deploy", MagicMock(return_value=(expected, 255))
    ), patch(
        "salt.output.display_output", MagicMock()
    ) as display_output:
        client = ssh.SSH(opts)
        ret = next(client.run_iter())
        with pytest.raises(SystemExit):
            client.run()
    display_output.assert_called_once_with(expected, "nested", ANY)
    assert ret == handle_ssh_ret[0][0]


def test_key_deploy_no_permission_denied(opts):
    """
    test key_deploy when no permission denied
    """
    host = "localhost"
    opts["tgt"] = host
    handle_ssh_ret = [({host: "foo"}, 0)]

    with patch("salt.roster.get_roster_file", MagicMock(return_value="")), patch(
        "salt.client.ssh.SSH.handle_ssh", MagicMock(return_value=handle_ssh_ret)
    ), patch(
        "salt.client.ssh.SSH.key_deploy", MagicMock(return_value=({host: "foo"}, None))
    ):
        client = ssh.SSH(opts)
        ret = next(client.run_iter())
        client.run()
    assert ret == handle_ssh_ret[0][0]


def test_handle_routine_single_run_invalid_retcode(opts, caplog):
    """
    Ensure that if Single.run() returns an invalid retcode,
    the final exit code is still an integer and set to 1 at least.
    """
    host = "localhost"
    # Roster entry passed as **target to Single (see SSH.handle_routine / handle_ssh).
    target = {"host": "127.0.0.1", "user": "root"}
    # Single.run() returns (stdout, stderr, retcode)
    single_ret = ("", "Something went seriously wrong", None)
    opts["tgt"] = host
    single = MagicMock(spec=ssh.Single)
    single.id = host
    single.run.return_value = single_ret

    import multiprocessing

    with patch("salt.roster.get_roster_file", MagicMock(return_value="")), patch(
        "salt.client.ssh.Single", autospec=True, return_value=single
    ):
        client = ssh.SSH(opts)
        que = multiprocessing.Queue()
        client.handle_routine(que, opts, host, target)
        ret, exit_code = que.get(timeout=10)

    assert exit_code == 1
    assert "Got an invalid retcode for host 'localhost': 'None'" in caplog.text
