"""
    :codeauthor: :email:`Daniel Wallace <dwallace@saltstack.com`
"""

import os
import re
import shutil
import tempfile

import pytest
import salt.client.ssh.client
import salt.config
import salt.roster
import salt.utils.files
import salt.utils.path
import salt.utils.thin
import salt.utils.yaml
from salt.client import ssh
from tests.support.case import ShellCase
from tests.support.mock import MagicMock, call, patch
from tests.support.runtests import RUNTIME_VARS
from tests.support.unit import TestCase, skipIf


@skipIf(not salt.utils.path.which("ssh"), "No ssh binary found in path")
class SSHPasswordTests(ShellCase):
    @pytest.mark.slow_test
    def test_password_failure(self):
        """
        Check password failures when trying to deploy keys
        """
        opts = salt.config.client_config(self.get_config_file_path("master"))
        opts["list_hosts"] = False
        opts["argv"] = ["test.ping"]
        opts["selected_target_option"] = "glob"
        opts["tgt"] = "localhost"
        opts["arg"] = []
        roster = os.path.join(RUNTIME_VARS.TMP_CONF_DIR, "roster")
        handle_ssh_ret = [
            {
                "localhost": {
                    "retcode": 255,
                    "stderr": "Permission denied (publickey).\r\n",
                    "stdout": "",
                }
            },
        ]
        expected = {"localhost": "Permission denied (publickey)"}
        display_output = MagicMock()
        with patch(
            "salt.roster.get_roster_file", MagicMock(return_value=roster)
        ), patch(
            "salt.client.ssh.SSH.handle_ssh", MagicMock(return_value=handle_ssh_ret)
        ), patch(
            "salt.client.ssh.SSH.key_deploy", MagicMock(return_value=expected)
        ), patch(
            "salt.output.display_output", display_output
        ):
            client = ssh.SSH(opts)
            ret = next(client.run_iter())
            with self.assertRaises(SystemExit):
                client.run()
        display_output.assert_called_once_with(expected, "nested", opts)
        self.assertIs(ret, handle_ssh_ret[0])


@skipIf(not salt.utils.path.which("ssh"), "No ssh binary found in path")
class SSHReturnEventTests(ShellCase):
    def test_not_missing_fun_calling_wfuncs(self):
        opts = salt.config.client_config(self.get_config_file_path("master"))
        opts["list_hosts"] = False
        opts["argv"] = ["state.show_highstate"]
        opts["selected_target_option"] = "glob"
        opts["tgt"] = "localhost"
        opts["arg"] = []
        roster = os.path.join(RUNTIME_VARS.TMP_CONF_DIR, "roster")
        handle_ssh_ret = [
            {"localhost": {}},
        ]

        expected = {"localhost": {}}
        display_output = MagicMock()
        with patch(
            "salt.roster.get_roster_file", MagicMock(return_value=roster)
        ), patch(
            "salt.client.ssh.SSH.handle_ssh", MagicMock(return_value=handle_ssh_ret)
        ), patch(
            "salt.client.ssh.SSH.key_deploy", MagicMock(return_value=expected)
        ), patch(
            "salt.output.display_output", display_output
        ):
            client = ssh.SSH(opts)
            client.event = MagicMock()
            ret = next(client.run_iter())
            assert "localhost" in ret
            assert "fun" in ret["localhost"]
            client.run()
        display_output.assert_called_once_with(expected, "nested", opts)
        self.assertIs(ret, handle_ssh_ret[0])
        assert len(client.event.fire_event.call_args_list) == 2
        assert "fun" in client.event.fire_event.call_args_list[0][0][0]
        assert "fun" in client.event.fire_event.call_args_list[1][0][0]


class SSHRosterDefaults(TestCase):
    def setUp(self):
        self.roster = """
            localhost:
              host: 127.0.0.1
              port: 2827
            self:
              host: 0.0.0.0
              port: 42
            """

    def test_roster_defaults_flat(self):
        """
        Test Roster Defaults on the flat roster
        """
        tempdir = tempfile.mkdtemp(dir=RUNTIME_VARS.TMP)
        expected = {
            "self": {"host": "0.0.0.0", "user": "daniel", "port": 42},
            "localhost": {"host": "127.0.0.1", "user": "daniel", "port": 2827},
        }
        try:
            root_dir = os.path.join(tempdir, "foo", "bar")
            os.makedirs(root_dir)
            fpath = os.path.join(root_dir, "config")
            with salt.utils.files.fopen(fpath, "w") as fp_:
                fp_.write(
                    """
                    roster_defaults:
                      user: daniel
                    """
                )
            opts = salt.config.master_config(fpath)
            with patch(
                "salt.roster.get_roster_file", MagicMock(return_value=self.roster)
            ):
                with patch(
                    "salt.template.compile_template",
                    MagicMock(return_value=salt.utils.yaml.safe_load(self.roster)),
                ):
                    roster = salt.roster.Roster(opts=opts)
                    self.assertEqual(roster.targets("*", "glob"), expected)
        finally:
            if os.path.isdir(tempdir):
                shutil.rmtree(tempdir)


class SSHSingleTests(TestCase):
    def setUp(self):
        self.tmp_cachedir = tempfile.mkdtemp(dir=RUNTIME_VARS.TMP)
        self.argv = [
            "ssh.set_auth_key",
            "root",
            "hobn+amNAXSBTiOXEqlBjGB...rsa root@master",
        ]
        self.opts = {
            "argv": self.argv,
            "__role": "master",
            "cachedir": self.tmp_cachedir,
            "extension_modules": os.path.join(self.tmp_cachedir, "extmods"),
        }
        self.target = {
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

    def test_single_opts(self):
        """Sanity check for ssh.Single options"""

        single = ssh.Single(
            self.opts,
            self.opts["argv"],
            "localhost",
            mods={},
            fsclient=None,
            thin=salt.utils.thin.thin_path(self.opts["cachedir"]),
            mine=False,
            **self.target
        )

        self.assertEqual(single.shell._ssh_opts(), "")
        self.assertEqual(
            single.shell._cmd_str("date +%s"),
            "ssh login1 "
            "-o KbdInteractiveAuthentication=no -o "
            "PasswordAuthentication=yes -o ConnectTimeout=65 -o Port=22 "
            "-o IdentityFile=/etc/salt/pki/master/ssh/salt-ssh.rsa "
            "-o User=root  date +%s",
        )

    def test_run_with_pre_flight(self):
        """
        test Single.run() when ssh_pre_flight is set
        and script successfully runs
        """
        target = self.target.copy()
        target["ssh_pre_flight"] = os.path.join(RUNTIME_VARS.TMP, "script.sh")
        single = ssh.Single(
            self.opts,
            self.opts["argv"],
            "localhost",
            mods={},
            fsclient=None,
            thin=salt.utils.thin.thin_path(self.opts["cachedir"]),
            mine=False,
            **target
        )

        cmd_ret = ("Success", "", 0)
        mock_flight = MagicMock(return_value=cmd_ret)
        mock_cmd = MagicMock(return_value=cmd_ret)
        patch_flight = patch("salt.client.ssh.Single.run_ssh_pre_flight", mock_flight)
        patch_cmd = patch("salt.client.ssh.Single.cmd_block", mock_cmd)
        patch_exec_cmd = patch(
            "salt.client.ssh.shell.Shell.exec_cmd", return_value=("", "", 1)
        )
        patch_os = patch("os.path.exists", side_effect=[True])

        with patch_os, patch_flight, patch_cmd, patch_exec_cmd:
            ret = single.run()
            mock_cmd.assert_called()
            mock_flight.assert_called()
            assert ret == cmd_ret

    def test_run_with_pre_flight_stderr(self):
        """
        test Single.run() when ssh_pre_flight is set
        and script errors when run
        """
        target = self.target.copy()
        target["ssh_pre_flight"] = os.path.join(RUNTIME_VARS.TMP, "script.sh")
        single = ssh.Single(
            self.opts,
            self.opts["argv"],
            "localhost",
            mods={},
            fsclient=None,
            thin=salt.utils.thin.thin_path(self.opts["cachedir"]),
            mine=False,
            **target
        )

        cmd_ret = ("", "Error running script", 1)
        mock_flight = MagicMock(return_value=cmd_ret)
        mock_cmd = MagicMock(return_value=cmd_ret)
        patch_flight = patch("salt.client.ssh.Single.run_ssh_pre_flight", mock_flight)
        patch_cmd = patch("salt.client.ssh.Single.cmd_block", mock_cmd)
        patch_exec_cmd = patch(
            "salt.client.ssh.shell.Shell.exec_cmd", return_value=("", "", 1)
        )
        patch_os = patch("os.path.exists", side_effect=[True])

        with patch_os, patch_flight, patch_cmd, patch_exec_cmd:
            ret = single.run()
            mock_cmd.assert_not_called()
            mock_flight.assert_called()
            assert ret == cmd_ret

    def test_run_with_pre_flight_script_doesnot_exist(self):
        """
        test Single.run() when ssh_pre_flight is set
        and the script does not exist
        """
        target = self.target.copy()
        target["ssh_pre_flight"] = os.path.join(RUNTIME_VARS.TMP, "script.sh")
        single = ssh.Single(
            self.opts,
            self.opts["argv"],
            "localhost",
            mods={},
            fsclient=None,
            thin=salt.utils.thin.thin_path(self.opts["cachedir"]),
            mine=False,
            **target
        )

        cmd_ret = ("Success", "", 0)
        mock_flight = MagicMock(return_value=cmd_ret)
        mock_cmd = MagicMock(return_value=cmd_ret)
        patch_flight = patch("salt.client.ssh.Single.run_ssh_pre_flight", mock_flight)
        patch_cmd = patch("salt.client.ssh.Single.cmd_block", mock_cmd)
        patch_exec_cmd = patch(
            "salt.client.ssh.shell.Shell.exec_cmd", return_value=("", "", 1)
        )
        patch_os = patch("os.path.exists", side_effect=[False])

        with patch_os, patch_flight, patch_cmd, patch_exec_cmd:
            ret = single.run()
            mock_cmd.assert_called()
            mock_flight.assert_not_called()
            assert ret == cmd_ret

    def test_run_with_pre_flight_thin_dir_exists(self):
        """
        test Single.run() when ssh_pre_flight is set
        and thin_dir already exists
        """
        target = self.target.copy()
        target["ssh_pre_flight"] = os.path.join(RUNTIME_VARS.TMP, "script.sh")
        single = ssh.Single(
            self.opts,
            self.opts["argv"],
            "localhost",
            mods={},
            fsclient=None,
            thin=salt.utils.thin.thin_path(self.opts["cachedir"]),
            mine=False,
            **target
        )

        cmd_ret = ("", "", 0)
        mock_flight = MagicMock(return_value=cmd_ret)
        mock_cmd = MagicMock(return_value=cmd_ret)
        patch_flight = patch("salt.client.ssh.Single.run_ssh_pre_flight", mock_flight)
        patch_cmd = patch("salt.client.ssh.shell.Shell.exec_cmd", mock_cmd)
        patch_cmd_block = patch("salt.client.ssh.Single.cmd_block", mock_cmd)
        patch_os = patch("os.path.exists", return_value=True)

        with patch_os, patch_flight, patch_cmd, patch_cmd_block:
            ret = single.run()
            mock_cmd.assert_called()
            mock_flight.assert_not_called()
            assert ret == cmd_ret

    def test_execute_script(self):
        """
        test Single.execute_script()
        """
        single = ssh.Single(
            self.opts,
            self.opts["argv"],
            "localhost",
            mods={},
            fsclient=None,
            thin=salt.utils.thin.thin_path(self.opts["cachedir"]),
            mine=False,
            winrm=False,
            **self.target
        )

        exp_ret = ("Success", "", 0)
        mock_cmd = MagicMock(return_value=exp_ret)
        patch_cmd = patch("salt.client.ssh.shell.Shell.exec_cmd", mock_cmd)
        script = os.path.join(RUNTIME_VARS.TMP, "script.sh")

        with patch_cmd:
            ret = single.execute_script(script=script)
            assert ret == exp_ret
            assert mock_cmd.call_count == 2
            assert [
                call("/bin/sh '{}'".format(script)),
                call("rm '{}'".format(script)),
            ] == mock_cmd.call_args_list

    def test_shim_cmd(self):
        """
        test Single.shim_cmd()
        """
        single = ssh.Single(
            self.opts,
            self.opts["argv"],
            "localhost",
            mods={},
            fsclient=None,
            thin=salt.utils.thin.thin_path(self.opts["cachedir"]),
            mine=False,
            winrm=False,
            tty=True,
            **self.target
        )

        exp_ret = ("Success", "", 0)
        mock_cmd = MagicMock(return_value=exp_ret)
        patch_cmd = patch("salt.client.ssh.shell.Shell.exec_cmd", mock_cmd)
        patch_send = patch("salt.client.ssh.shell.Shell.send", return_value=("", "", 0))
        patch_rand = patch("os.urandom", return_value=b"5\xd9l\xca\xc2\xff")

        with patch_cmd, patch_rand, patch_send:
            ret = single.shim_cmd(cmd_str="echo test")
            assert ret == exp_ret
            assert [
                call("/bin/sh '.35d96ccac2ff.py'"),
                call("rm '.35d96ccac2ff.py'"),
            ] == mock_cmd.call_args_list

    def test_run_ssh_pre_flight(self):
        """
        test Single.run_ssh_pre_flight
        """
        target = self.target.copy()
        target["ssh_pre_flight"] = os.path.join(RUNTIME_VARS.TMP, "script.sh")
        single = ssh.Single(
            self.opts,
            self.opts["argv"],
            "localhost",
            mods={},
            fsclient=None,
            thin=salt.utils.thin.thin_path(self.opts["cachedir"]),
            mine=False,
            winrm=False,
            tty=True,
            **target
        )

        exp_ret = ("Success", "", 0)
        mock_cmd = MagicMock(return_value=exp_ret)
        patch_cmd = patch("salt.client.ssh.shell.Shell.exec_cmd", mock_cmd)
        patch_send = patch("salt.client.ssh.shell.Shell.send", return_value=exp_ret)
        exp_tmp = os.path.join(
            tempfile.gettempdir(), os.path.basename(target["ssh_pre_flight"])
        )

        with patch_cmd, patch_send:
            ret = single.run_ssh_pre_flight()
            assert ret == exp_ret
            assert [
                call("/bin/sh '{}'".format(exp_tmp)),
                call("rm '{}'".format(exp_tmp)),
            ] == mock_cmd.call_args_list

    @skipIf(salt.utils.platform.is_windows(), "SSH_PY_SHIM not set on windows")
    def test_cmd_run_set_path(self):
        """
        test when set_path is set
        """
        target = self.target
        target["set_path"] = "$PATH:/tmp/path/"
        single = ssh.Single(
            self.opts,
            self.opts["argv"],
            "localhost",
            mods={},
            fsclient=None,
            thin=salt.utils.thin.thin_path(self.opts["cachedir"]),
            mine=False,
            **self.target
        )

        ret = single._cmd_str()
        assert re.search("\\" + target["set_path"], ret)

    @skipIf(salt.utils.platform.is_windows(), "SSH_PY_SHIM not set on windows")
    def test_cmd_run_not_set_path(self):
        """
        test when set_path is not set
        """
        target = self.target
        single = ssh.Single(
            self.opts,
            self.opts["argv"],
            "localhost",
            mods={},
            fsclient=None,
            thin=salt.utils.thin.thin_path(self.opts["cachedir"]),
            mine=False,
            **self.target
        )

        ret = single._cmd_str()
        assert re.search('SET_PATH=""', ret)


@skipIf(not salt.utils.path.which("ssh"), "No ssh binary found in path")
class SSHTests(ShellCase):
    def setUp(self):
        self.roster = """
            localhost:
              host: 127.0.0.1
              port: 2827
            """
        self.opts = salt.config.client_config(self.get_config_file_path("master"))
        self.opts["selected_target_option"] = "glob"

    def test_expand_target_ip_address(self):
        """
        test expand_target when target is root@<ip address>
        """
        host = "127.0.0.1"
        user = "test-user@"
        opts = self.opts
        opts["tgt"] = user + host

        with patch(
            "salt.utils.network.is_reachable_host", MagicMock(return_value=False)
        ):
            client = ssh.SSH(opts)
        assert opts["tgt"] == user + host
        with patch(
            "salt.roster.get_roster_file", MagicMock(return_value="/etc/salt/roster")
        ), patch(
            "salt.client.ssh.compile_template",
            MagicMock(return_value=salt.utils.yaml.safe_load(self.roster)),
        ):
            client._expand_target()
        assert opts["tgt"] == host

    def test_expand_target_dns(self):
        """
        test expand_target when target is root@<dns>
        """
        host = "localhost"
        user = "test-user@"
        opts = self.opts
        opts["tgt"] = user + host

        with patch(
            "salt.utils.network.is_reachable_host", MagicMock(return_value=False)
        ):
            client = ssh.SSH(opts)
        assert opts["tgt"] == user + host
        with patch(
            "salt.roster.get_roster_file", MagicMock(return_value="/etc/salt/roster")
        ), patch(
            "salt.client.ssh.compile_template",
            MagicMock(return_value=salt.utils.yaml.safe_load(self.roster)),
        ):
            client._expand_target()
        assert opts["tgt"] == host

    def test_expand_target_no_user(self):
        """
        test expand_target when no user defined
        """
        host = "127.0.0.1"
        opts = self.opts
        opts["tgt"] = host

        with patch(
            "salt.utils.network.is_reachable_host", MagicMock(return_value=False)
        ):
            client = ssh.SSH(opts)
        assert opts["tgt"] == host

        with patch(
            "salt.roster.get_roster_file", MagicMock(return_value="/etc/salt/roster")
        ), patch(
            "salt.client.ssh.compile_template",
            MagicMock(return_value=salt.utils.yaml.safe_load(self.roster)),
        ):
            client._expand_target()
        assert opts["tgt"] == host

    def test_update_targets_ip_address(self):
        """
        test update_targets when host is ip address
        """
        host = "127.0.0.1"
        user = "test-user@"
        opts = self.opts
        opts["tgt"] = user + host

        with patch(
            "salt.utils.network.is_reachable_host", MagicMock(return_value=False)
        ):
            client = ssh.SSH(opts)
        assert opts["tgt"] == user + host
        client._update_targets()
        assert opts["tgt"] == host
        assert client.targets[host]["user"] == user.split("@")[0]

    def test_update_targets_dns(self):
        """
        test update_targets when host is dns
        """
        host = "localhost"
        user = "test-user@"
        opts = self.opts
        opts["tgt"] = user + host

        with patch(
            "salt.utils.network.is_reachable_host", MagicMock(return_value=False)
        ):
            client = ssh.SSH(opts)
        assert opts["tgt"] == user + host
        client._update_targets()
        assert opts["tgt"] == host
        assert client.targets[host]["user"] == user.split("@")[0]

    def test_update_targets_no_user(self):
        """
        test update_targets when no user defined
        """
        host = "127.0.0.1"
        opts = self.opts
        opts["tgt"] = host

        with patch(
            "salt.utils.network.is_reachable_host", MagicMock(return_value=False)
        ):
            client = ssh.SSH(opts)
        assert opts["tgt"] == host
        client._update_targets()
        assert opts["tgt"] == host

    def test_update_expand_target_dns(self):
        """
        test update_targets and expand_target when host is dns
        """
        host = "localhost"
        user = "test-user@"
        opts = self.opts
        opts["tgt"] = user + host

        with patch(
            "salt.utils.network.is_reachable_host", MagicMock(return_value=False)
        ):
            client = ssh.SSH(opts)
        assert opts["tgt"] == user + host
        with patch(
            "salt.roster.get_roster_file", MagicMock(return_value="/etc/salt/roster")
        ), patch(
            "salt.client.ssh.compile_template",
            MagicMock(return_value=salt.utils.yaml.safe_load(self.roster)),
        ):
            client._expand_target()
        client._update_targets()
        assert opts["tgt"] == host
        assert client.targets[host]["user"] == user.split("@")[0]

    def test_parse_tgt(self):
        """
        test parse_tgt when user and host set on
        the ssh cli tgt
        """
        host = "localhost"
        user = "test-user@"
        opts = self.opts
        opts["tgt"] = user + host

        with patch(
            "salt.utils.network.is_reachable_host", MagicMock(return_value=False)
        ):
            assert not self.opts.get("ssh_cli_tgt")
            client = ssh.SSH(opts)
            assert client.parse_tgt["hostname"] == host
            assert client.parse_tgt["user"] == user.split("@")[0]
            assert self.opts.get("ssh_cli_tgt") == user + host

    def test_parse_tgt_no_user(self):
        """
        test parse_tgt when only the host set on
        the ssh cli tgt
        """
        host = "localhost"
        opts = self.opts
        opts["ssh_user"] = "ssh-usr"
        opts["tgt"] = host

        with patch(
            "salt.utils.network.is_reachable_host", MagicMock(return_value=False)
        ):
            assert not self.opts.get("ssh_cli_tgt")
            client = ssh.SSH(opts)
            assert client.parse_tgt["hostname"] == host
            assert client.parse_tgt["user"] == opts["ssh_user"]
            assert self.opts.get("ssh_cli_tgt") == host

    def test_extra_filerefs(self):
        """
        test "extra_filerefs" are not excluded from kwargs
        when preparing the SSH opts
        """
        opts = {
            "eauth": "auto",
            "username": "test",
            "password": "test",
            "client": "ssh",
            "tgt": "localhost",
            "fun": "test.ping",
            "ssh_port": 22,
            "extra_filerefs": "salt://foobar",
        }
        roster = os.path.join(RUNTIME_VARS.TMP_CONF_DIR, "roster")
        client = salt.client.ssh.client.SSHClient(
            mopts=self.opts, disable_custom_roster=True
        )
        with patch("salt.roster.get_roster_file", MagicMock(return_value=roster)):
            ssh_obj = client._prep_ssh(**opts)
            assert ssh_obj.opts.get("extra_filerefs", None) == "salt://foobar"
