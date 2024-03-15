"""
    :codeauthor: Pedro Algarvio (pedro@algarvio.me)
    tests.unit.utils.cloud_test
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Test the salt-cloud utilities module.

"""

import os
import string
import tempfile

import pytest

try:
    from smbprotocol.exceptions import CannotDelete

    HAS_PSEXEC = True
except ImportError:
    HAS_PSEXEC = False

import salt.utils.cloud as cloud
from salt.exceptions import SaltCloudException
from salt.utils.cloud import __ssh_gateway_arguments as ssh_gateway_arguments
from tests.support.mock import MagicMock, patch


@pytest.fixture()
def configure_loader_modules():
    return {
        cloud: {"__opts__": {"sock_dir": "master"}},
    }


@pytest.fixture
def create_class(tmp_path):
    old_cwd = os.getcwd()
    gpg_keydir = tmp_path / "gpg-keydir"
    gpg_keydir.mkdir()
    try:
        # The keyring library uses `getcwd()`, let's make sure we in a good directory
        # before importing keyring
        os.chdir(str(gpg_keydir))
        # Late import because of the above reason
        import keyring
        import keyring.backend

        class CustomKeyring(keyring.backend.KeyringBackend):
            """
            A test keyring which always outputs same password
            """

            def __init__(self):
                self.__storage = {}

            def supported(self):
                return 0

            def set_password(
                self, servicename, username, password
            ):  # pylint: disable=arguments-differ,arguments-renamed
                self.__storage.setdefault(servicename, {}).update({username: password})
                return 0

            def get_password(
                self, servicename, username
            ):  # pylint: disable=arguments-differ,arguments-renamed
                return self.__storage.setdefault(servicename, {}).get(username)

            def delete_password(
                self, servicename, username
            ):  # pylint: disable=arguments-differ,arguments-renamed
                self.__storage.setdefault(servicename, {}).pop(username, None)
                return 0

        # set the keyring for keyring lib
        keyring.set_keyring(CustomKeyring())
        yield
    except ImportError:
        pytest.skip('The "keyring" python module is not installed')
    finally:
        os.chdir(old_cwd)


def test_ssh_password_regex():
    """Test matching ssh password patterns"""
    for pattern in (
        "Password for root@127.0.0.1:",
        "root@127.0.0.1 Password:",
        " Password:",
    ):
        assert cloud.SSH_PASSWORD_PROMP_RE.match(pattern) is not None
        assert cloud.SSH_PASSWORD_PROMP_RE.match(pattern.lower()) is not None
        assert cloud.SSH_PASSWORD_PROMP_RE.match(pattern.strip()) is not None
        assert cloud.SSH_PASSWORD_PROMP_RE.match(pattern.lower().strip()) is not None


def test__save_password_in_keyring(create_class):
    """
    Test storing password in the keyring
    """
    # Late import
    import keyring

    cloud._save_password_in_keyring(
        "salt.cloud.provider.test_case_provider",
        "fake_username",
        "fake_password_c8231",
    )
    stored_pw = keyring.get_password(
        "salt.cloud.provider.test_case_provider",
        "fake_username",
    )
    keyring.delete_password(
        "salt.cloud.provider.test_case_provider",
        "fake_username",
    )
    assert stored_pw == "fake_password_c8231"


def test_retrieve_password_from_keyring(create_class):
    # Late import
    import keyring

    keyring.set_password(
        "salt.cloud.provider.test_case_provider",
        "fake_username",
        "fake_password_c8231",
    )
    pw_in_keyring = cloud.retrieve_password_from_keyring(
        "salt.cloud.provider.test_case_provider", "fake_username"
    )
    assert pw_in_keyring == "fake_password_c8231"


def test_sftp_file_with_content_under_python3():
    with pytest.raises(Exception) as context:
        cloud.sftp_file("/tmp/test", "ТЕSТ test content")
        # we successful pass the place with os.write(tmpfd, ...
        assert "a bytes-like object is required, not 'str'" != str(context.exception)


@pytest.mark.skip_on_windows(reason="Not applicable for Windows.")
def test_check_key_path_and_mode():
    with tempfile.NamedTemporaryFile() as f:
        key_file = f.name

        os.chmod(key_file, 0o644)
        assert cloud.check_key_path_and_mode("foo", key_file) is False
        os.chmod(key_file, 0o600)
        assert cloud.check_key_path_and_mode("foo", key_file) is True
        os.chmod(key_file, 0o400)
        assert cloud.check_key_path_and_mode("foo", key_file) is True

    # tmp file removed
    assert cloud.check_key_path_and_mode("foo", key_file) is False


@pytest.mark.skip_unless_on_windows(reason="Only applicable for Windows.")
def test_deploy_windows_default_port():
    """
    Test deploy_windows with default port
    """
    mock_true = MagicMock(return_value=True)
    mock_tuple = MagicMock(return_value=(0, 0, 0))
    with patch("salt.utils.smb.get_conn", MagicMock()) as mock, patch(
        "salt.utils.smb.mkdirs", MagicMock()
    ), patch("salt.utils.smb.put_file", MagicMock()), patch(
        "salt.utils.smb.delete_file", MagicMock()
    ), patch(
        "salt.utils.smb.delete_directory", MagicMock()
    ), patch(
        "time.sleep", MagicMock()
    ), patch.object(
        cloud, "wait_for_port", mock_true
    ), patch.object(
        cloud, "fire_event", MagicMock()
    ), patch.object(
        cloud, "wait_for_psexecsvc", mock_true
    ), patch.object(
        cloud, "run_psexec_command", mock_tuple
    ):

        cloud.deploy_windows(host="test", win_installer="")
        mock.assert_called_once_with("test", "Administrator", None, 445)


@pytest.mark.skip_unless_on_windows(reason="Only applicable for Windows.")
def test_deploy_windows_custom_port():
    """
    Test deploy_windows with a custom port
    """
    mock_true = MagicMock(return_value=True)
    mock_tuple = MagicMock(return_value=(0, 0, 0))
    with patch("salt.utils.smb.get_conn", MagicMock()) as mock, patch(
        "salt.utils.smb.mkdirs", MagicMock()
    ), patch("salt.utils.smb.put_file", MagicMock()), patch(
        "salt.utils.smb.delete_file", MagicMock()
    ), patch(
        "salt.utils.smb.delete_directory", MagicMock()
    ), patch(
        "time.sleep", MagicMock()
    ), patch.object(
        cloud, "wait_for_port", mock_true
    ), patch.object(
        cloud, "fire_event", MagicMock()
    ), patch.object(
        cloud, "wait_for_psexecsvc", mock_true
    ), patch.object(
        cloud, "run_psexec_command", mock_tuple
    ):

        cloud.deploy_windows(host="test", port=1234, win_installer="")
        mock.assert_called_once_with("test", "Administrator", None, 1234)


@pytest.mark.skipif(not HAS_PSEXEC, reason="Missing SMB Protocol Library")
def test_run_psexec_command_cleanup_lingering_paexec(caplog):
    pytest.importorskip("pypsexec.client", reason="Requires PyPsExec")
    mock_psexec = patch("salt.utils.cloud.PsExecClient", autospec=True)
    mock_scmr = patch("salt.utils.cloud.ScmrService", autospec=True)
    # We're mocking 'remove_service' because all we care about is the cleanup
    # command
    mock_rm_svc = patch("salt.utils.cloud.Client.remove_service", autospec=True)
    with mock_scmr, mock_rm_svc, mock_psexec as mock_client:
        mock_client.return_value.session = MagicMock(username="Gary")
        mock_client.return_value.connection = MagicMock(server_name="Krabbs")
        mock_client.return_value.run_executable.return_value = (
            "Sandy",
            "MermaidMan",
            "BarnicleBoy",
        )
        cloud.run_psexec_command(
            "spongebob",
            "squarepants",
            "patrick",
            "squidward",
            "plankton",
        )
        mock_client.return_value.cleanup.assert_called_once()

    # Testing handling an error when it can't delete the PAexec binary
    with mock_scmr, mock_rm_svc, mock_psexec as mock_client:
        mock_client.return_value.session = MagicMock(username="Gary")
        mock_client.return_value.connection = MagicMock(server_name="Krabbs")
        mock_client.return_value.run_executable.return_value = (
            "Sandy",
            "MermaidMan",
            "BarnicleBoy",
        )
        # pylint: disable=no-value-for-parameter
        mock_client.return_value.cleanup = MagicMock(side_effect=CannotDelete())

        cloud.run_psexec_command(
            "spongebob",
            "squarepants",
            "patrick",
            "squidward",
            "plankton",
        )
        assert "Exception cleaning up PAexec:" in caplog.text
        mock_client.return_value.disconnect.assert_called_once()


@pytest.mark.skip_unless_on_windows(reason="Only applicable for Windows.")
def test_deploy_windows_programdata():
    """
    Test deploy_windows to ProgramData
    """
    mock_true = MagicMock(return_value=True)
    mock_tuple = MagicMock(return_value=(0, 0, 0))
    mock_conn = MagicMock()

    with patch("salt.utils.smb", MagicMock()) as mock_smb:
        mock_smb.get_conn.return_value = mock_conn
        mock_smb.mkdirs.return_value = None
        mock_smb.put_file.return_value = None
        mock_smb.delete_file.return_value = None
        mock_smb.delete_directory.return_value = None
        with patch("time.sleep", MagicMock()), patch.object(
            cloud, "wait_for_port", mock_true
        ), patch.object(cloud, "fire_event", MagicMock()), patch.object(
            cloud, "wait_for_psexecsvc", mock_true
        ), patch.object(
            cloud, "run_psexec_command", mock_tuple
        ):
            cloud.deploy_windows(host="test", win_installer="")
            expected = "ProgramData/Salt Project/Salt/conf/pki/minion"
            mock_smb.mkdirs.assert_called_with(expected, conn=mock_conn)


@pytest.mark.skip_unless_on_windows(reason="Only applicable for Windows.")
def test_deploy_windows_programdata_minion_pub():
    """
    Test deploy_windows with a custom port
    """
    mock_true = MagicMock(return_value=True)
    mock_tuple = MagicMock(return_value=(0, 0, 0))
    mock_conn = MagicMock()

    with patch("salt.utils.smb", MagicMock()) as mock_smb:
        mock_smb.get_conn.return_value = mock_conn
        mock_smb.mkdirs.return_value = None
        mock_smb.put_file.return_value = None
        mock_smb.put_str.return_value = None
        mock_smb.delete_file.return_value = None
        mock_smb.delete_directory.return_value = None
        with patch("time.sleep", MagicMock()), patch.object(
            cloud, "wait_for_port", mock_true
        ), patch.object(cloud, "fire_event", MagicMock()), patch.object(
            cloud, "wait_for_psexecsvc", mock_true
        ), patch.object(
            cloud, "run_psexec_command", mock_tuple
        ):
            cloud.deploy_windows(host="test", minion_pub="pub", win_installer="")
            expected = "ProgramData\\Salt Project\\Salt\\conf\\pki\\minion\\minion.pub"
            mock_smb.put_str.assert_called_with("pub", expected, conn=mock_conn)


@pytest.mark.skip_unless_on_windows(reason="Only applicable for Windows.")
def test_deploy_windows_programdata_minion_pem():
    """
    Test deploy_windows with a custom port
    """
    mock_true = MagicMock(return_value=True)
    mock_tuple = MagicMock(return_value=(0, 0, 0))
    mock_conn = MagicMock()

    with patch("salt.utils.smb", MagicMock()) as mock_smb:
        mock_smb.get_conn.return_value = mock_conn
        mock_smb.mkdirs.return_value = None
        mock_smb.put_file.return_value = None
        mock_smb.put_str.return_value = None
        mock_smb.delete_file.return_value = None
        mock_smb.delete_directory.return_value = None
        with patch("time.sleep", MagicMock()), patch.object(
            cloud, "wait_for_port", mock_true
        ), patch.object(cloud, "fire_event", MagicMock()), patch.object(
            cloud, "wait_for_psexecsvc", mock_true
        ), patch.object(
            cloud, "run_psexec_command", mock_tuple
        ):
            cloud.deploy_windows(host="test", minion_pem="pem", win_installer="")
            expected = "ProgramData\\Salt Project\\Salt\\conf\\pki\\minion\\minion.pem"
            mock_smb.put_str.assert_called_with("pem", expected, conn=mock_conn)


@pytest.mark.skip_unless_on_windows(reason="Only applicable for Windows.")
def test_deploy_windows_programdata_master_sign_pub_file():
    """
    Test deploy_windows with a custom port
    """
    mock_true = MagicMock(return_value=True)
    mock_tuple = MagicMock(return_value=(0, 0, 0))
    mock_conn = MagicMock()

    with patch("salt.utils.smb", MagicMock()) as mock_smb:
        mock_smb.get_conn.return_value = mock_conn
        mock_smb.mkdirs.return_value = None
        mock_smb.put_file.return_value = None
        mock_smb.put_str.return_value = None
        mock_smb.delete_file.return_value = None
        mock_smb.delete_directory.return_value = None
        with patch("time.sleep", MagicMock()), patch.object(
            cloud, "wait_for_port", mock_true
        ), patch.object(cloud, "fire_event", MagicMock()), patch.object(
            cloud, "wait_for_psexecsvc", mock_true
        ), patch.object(
            cloud, "run_psexec_command", mock_tuple
        ):
            cloud.deploy_windows(
                host="test", master_sign_pub_file="test.txt", win_installer=""
            )
            expected = (
                "ProgramData\\Salt Project\\Salt\\conf\\pki\\minion\\master_sign.pub"
            )
            called = False
            for call in mock_smb.put_file.mock_calls:
                if expected in call[1]:
                    called = True
            assert called


@pytest.mark.skip_unless_on_windows(reason="Only applicable for Windows.")
def test_deploy_windows_programdata_minion_conf_grains():
    """
    Test deploy_windows with a custom port
    """
    mock_true = MagicMock(return_value=True)
    mock_tuple = MagicMock(return_value=(0, 0, 0))
    mock_conn = MagicMock()

    with patch("salt.utils.smb", MagicMock()) as mock_smb:
        mock_smb.get_conn.return_value = mock_conn
        mock_smb.mkdirs.return_value = None
        mock_smb.put_file.return_value = None
        mock_smb.put_str.return_value = None
        mock_smb.delete_file.return_value = None
        mock_smb.delete_directory.return_value = None
        with patch("time.sleep", MagicMock()), patch.object(
            cloud, "wait_for_port", mock_true
        ), patch.object(cloud, "fire_event", MagicMock()), patch.object(
            cloud, "wait_for_psexecsvc", mock_true
        ), patch.object(
            cloud, "run_psexec_command", mock_tuple
        ):
            minion_conf = {"grains": {"spongebob": "squarepants"}}
            cloud.deploy_windows(host="test", minion_conf=minion_conf, win_installer="")
            expected = "ProgramData\\Salt Project\\Salt\\conf\\grains"
            called = False
            for call in mock_smb.put_str.mock_calls:
                if expected in call[1]:
                    called = True
            assert called


@pytest.mark.skip_unless_on_windows(reason="Only applicable for Windows.")
def test_deploy_windows_programdata_minion_conf():
    """
    Test deploy_windows with a custom port
    """
    mock_true = MagicMock(return_value=True)
    mock_tuple = MagicMock(return_value=(0, 0, 0))
    mock_conn = MagicMock()

    with patch("salt.utils.smb", MagicMock()) as mock_smb:
        mock_smb.get_conn.return_value = mock_conn
        mock_smb.mkdirs.return_value = None
        mock_smb.put_file.return_value = None
        mock_smb.put_str.return_value = None
        mock_smb.delete_file.return_value = None
        mock_smb.delete_directory.return_value = None
        with patch("time.sleep", MagicMock()), patch.object(
            cloud, "wait_for_port", mock_true
        ), patch.object(cloud, "fire_event", MagicMock()), patch.object(
            cloud, "wait_for_psexecsvc", mock_true
        ), patch.object(
            cloud, "run_psexec_command", mock_tuple
        ):
            minion_conf = {"master": "test-master"}
            cloud.deploy_windows(host="test", minion_conf=minion_conf, win_installer="")
            config = (
                "ipc_mode: tcp\r\n"
                "master: test-master\r\n"
                "multiprocessing: true\r\n"
                "pki_dir: /conf/pki/minion\r\n"
            )
            expected = "ProgramData\\Salt Project\\Salt\\conf\\minion"
            mock_smb.put_str.assert_called_with(config, expected, conn=mock_conn)


@pytest.mark.skip_unless_on_windows(reason="Only applicable for Windows.")
def test_winrm_pinnned_version():
    """
    Test that winrm is pinned to a version 0.3.0 or higher.
    """
    mock_true = MagicMock(return_value=True)
    mock_tuple = MagicMock(return_value=(0, 0, 0))
    with patch("salt.utils.smb.get_conn", MagicMock()), patch(
        "salt.utils.smb.mkdirs", MagicMock()
    ), patch("salt.utils.smb.put_file", MagicMock()), patch(
        "salt.utils.smb.delete_file", MagicMock()
    ), patch(
        "salt.utils.smb.delete_directory", MagicMock()
    ), patch(
        "time.sleep", MagicMock()
    ), patch.object(
        cloud, "wait_for_port", mock_true
    ), patch.object(
        cloud, "fire_event", MagicMock()
    ), patch.object(
        cloud, "wait_for_psexecsvc", mock_true
    ), patch.object(
        cloud, "run_psexec_command", mock_tuple
    ):

        try:
            import winrm  # pylint: disable=unused-import
        except ImportError:
            raise pytest.skip('The "winrm" python module is not installed in this env.')
        else:
            import pkg_resources

            winrm_pkg = pkg_resources.get_distribution("pywinrm")
            assert winrm_pkg.version >= "0.3.0"
    # fmt: on


def test_ssh_gateway_arguments_default_alive_args():
    server_alive_interval = 60
    server_alive_count_max = 3
    arguments = ssh_gateway_arguments({"ssh_gateway": "host"})
    assert f"-oServerAliveInterval={server_alive_interval}" in arguments
    assert f"-oServerAliveCountMax={server_alive_count_max}" in arguments


def test_ssh_gateway_arguments_alive_args():
    server_alive_interval = 10
    server_alive_count_max = 8
    arguments = ssh_gateway_arguments(
        {
            "ssh_gateway": "host",
            "server_alive_interval": server_alive_interval,
            "server_alive_count_max": server_alive_count_max,
        }
    )
    assert f"-oServerAliveInterval={server_alive_interval}" in arguments
    assert f"-oServerAliveCountMax={server_alive_count_max}" in arguments


def test_wait_for_port_default_alive_args():
    server_alive_interval = 60
    server_alive_count_max = 3
    with patch("salt.utils.cloud.socket", autospec=True), patch(
        "salt.utils.cloud._exec_ssh_cmd", autospec=True, return_value=0
    ) as exec_ssh_cmd:
        cloud.wait_for_port(
            "127.0.0.1",
            gateway={"ssh_gateway": "host", "ssh_gateway_user": "user"},
        )
        assert exec_ssh_cmd.call_count == 2
        ssh_call = exec_ssh_cmd.call_args[0][0]
        assert f"-oServerAliveInterval={server_alive_interval}" in ssh_call
        assert f"-oServerAliveCountMax={server_alive_count_max}" in ssh_call


def test_wait_for_port_alive_args():
    server_alive_interval = 66
    server_alive_count_max = 1
    with patch("salt.utils.cloud.socket", autospec=True), patch(
        "salt.utils.cloud._exec_ssh_cmd", autospec=True, return_value=0
    ) as exec_ssh_cmd:
        cloud.wait_for_port(
            "127.0.0.1",
            server_alive_interval=server_alive_interval,
            server_alive_count_max=server_alive_count_max,
            gateway={"ssh_gateway": "host", "ssh_gateway_user": "user"},
        )
        assert exec_ssh_cmd.call_count == 2
        ssh_call = exec_ssh_cmd.call_args[0][0]
        assert f"-oServerAliveInterval={server_alive_interval}" in ssh_call
        assert f"-oServerAliveCountMax={server_alive_count_max}" in ssh_call


def test_scp_file_default_alive_args():
    server_alive_interval = 60
    server_alive_count_max = 3
    with patch("salt.utils.cloud.socket", autospec=True), patch(
        "salt.utils.cloud._exec_ssh_cmd", autospec=True, return_value=0
    ) as exec_ssh_cmd:
        cloud.scp_file(
            "/salt.txt",
            contents=None,
            kwargs={"hostname": "127.0.0.1", "username": "user"},
            local_file="/salt.txt",
        )
        assert exec_ssh_cmd.call_count == 1
        ssh_call = exec_ssh_cmd.call_args[0][0]
        assert f"-oServerAliveInterval={server_alive_interval}" in ssh_call
        assert f"-oServerAliveCountMax={server_alive_count_max}" in ssh_call


def test_scp_file_alive_args():
    server_alive_interval = 64
    server_alive_count_max = 4
    with patch("salt.utils.cloud.socket", autospec=True), patch(
        "salt.utils.cloud._exec_ssh_cmd", autospec=True, return_value=0
    ) as exec_ssh_cmd:
        cloud.scp_file(
            "/salt.txt",
            contents=None,
            kwargs={
                "hostname": "127.0.0.1",
                "username": "user",
                "server_alive_interval": server_alive_interval,
                "server_alive_count_max": server_alive_count_max,
            },
            local_file="/salt.txt",
        )
        assert exec_ssh_cmd.call_count == 1
        ssh_call = exec_ssh_cmd.call_args[0][0]
        assert f"-oServerAliveInterval={server_alive_interval}" in ssh_call
        assert f"-oServerAliveCountMax={server_alive_count_max}" in ssh_call


def test_sftp_file_default_alive_args():
    server_alive_interval = 60
    server_alive_count_max = 3
    with patch("salt.utils.cloud.socket", autospec=True), patch(
        "salt.utils.cloud._exec_ssh_cmd", autospec=True, return_value=0
    ) as exec_ssh_cmd:
        cloud.sftp_file(
            "/salt.txt",
            contents=None,
            kwargs={"hostname": "127.0.0.1", "username": "user"},
            local_file="/salt.txt",
        )
        assert exec_ssh_cmd.call_count == 1
        ssh_call = exec_ssh_cmd.call_args[0][0]
        assert f"-oServerAliveInterval={server_alive_interval}" in ssh_call
        assert f"-oServerAliveCountMax={server_alive_count_max}" in ssh_call


def test_sftp_file_alive_args():
    server_alive_interval = 62
    server_alive_count_max = 6
    with patch("salt.utils.cloud.socket", autospec=True), patch(
        "salt.utils.cloud._exec_ssh_cmd", autospec=True, return_value=0
    ) as exec_ssh_cmd:
        cloud.sftp_file(
            "/salt.txt",
            contents=None,
            kwargs={
                "hostname": "127.0.0.1",
                "username": "user",
                "server_alive_interval": server_alive_interval,
                "server_alive_count_max": server_alive_count_max,
            },
            local_file="/salt.txt",
        )
        assert exec_ssh_cmd.call_count == 1
        ssh_call = exec_ssh_cmd.call_args[0][0]
        assert f"-oServerAliveInterval={server_alive_interval}" in ssh_call
        assert f"-oServerAliveCountMax={server_alive_count_max}" in ssh_call


def test_deploy_script_ssh_timeout():
    with patch("salt.utils.cloud.root_cmd", return_value=False) as root_cmd, patch(
        "salt.utils.cloud.wait_for_port", return_value=True
    ), patch("salt.utils.cloud.wait_for_passwd", return_value=True), patch(
        "salt.utils.cloud._exec_ssh_cmd"
    ):
        cloud.deploy_script("127.0.0.1", ssh_timeout=34)
        # verify that ssh_timeout made it into ssh_kwargs
        assert root_cmd.call_count == 1
        ssh_kwargs = root_cmd.call_args.kwargs
        assert "ssh_timeout" in ssh_kwargs
        assert ssh_kwargs["ssh_timeout"] == 34


@pytest.mark.parametrize(
    "master,expected",
    [
        (None, None),
        ("single_master", "single_master"),
        (["master1", "master2", "master3"], "master1,master2,master3"),
    ],
)
def test__format_master_param(master, expected):
    result = cloud._format_master_param(master)
    assert result == expected


@pytest.mark.skip_unless_on_windows(reason="Only applicable for Windows.")
@pytest.mark.parametrize(
    "master,expected",
    [
        (None, None),
        ("single_master", "single_master"),
        (["master1", "master2", "master3"], "master1,master2,master3"),
    ],
)
def test_deploy_windows_master(master, expected):
    """
    Test deploy_windows with master parameter
    """
    mock_true = MagicMock(return_value=True)
    mock_tuple = MagicMock(return_value=(0, 0, 0))
    with patch("salt.utils.smb.get_conn", MagicMock()), patch(
        "salt.utils.smb.mkdirs", MagicMock()
    ), patch("salt.utils.smb.put_file", MagicMock()), patch(
        "salt.utils.smb.delete_file", MagicMock()
    ), patch(
        "salt.utils.smb.delete_directory", MagicMock()
    ), patch(
        "time.sleep", MagicMock()
    ), patch.object(
        cloud, "wait_for_port", mock_true
    ), patch.object(
        cloud, "fire_event", MagicMock()
    ), patch.object(
        cloud, "wait_for_psexecsvc", mock_true
    ), patch.object(
        cloud, "run_psexec_command", mock_tuple
    ) as mock:
        cloud.deploy_windows(host="test", win_installer="install.exe", master=master)
        expected_cmd = "c:\\salttemp\\install.exe"
        expected_args = f"/S /master={expected} /minion-name=None"
        assert mock.call_args_list[0].args[0] == expected_cmd
        assert mock.call_args_list[0].args[1] == expected_args


def test___ssh_gateway_config_dict():
    assert cloud.__ssh_gateway_config_dict(None) == {}
    gate = {
        "ssh_gateway": "Gozar",
        "ssh_gateway_key": "Zuul",
        "ssh_gateway_user": "Vinz Clortho",
        "ssh_gateway_command": "Are you the keymaster?",
    }
    assert cloud.__ssh_gateway_config_dict(gate) == gate


def test_ip_to_int():
    assert cloud.ip_to_int("127.0.0.1") == 2130706433


def test_is_public_ip():
    assert cloud.is_public_ip("8.8.8.8") is True
    assert cloud.is_public_ip("127.0.0.1") is False
    assert cloud.is_public_ip("172.17.3.1") is False
    assert cloud.is_public_ip("192.168.30.4") is False
    assert cloud.is_public_ip("10.145.1.1") is False
    assert cloud.is_public_ip("fe80::123:ffff:ffff:ffff") is False
    assert cloud.is_public_ip("2001:db8:3333:4444:CCCC:DDDD:EEEE:FFFF") is True


def test_check_name():
    try:
        cloud.check_name("test", string.ascii_letters)
    except SaltCloudException as exc:
        assert False, f"cloud.check_name rasied SaltCloudException: {exc}"

    with pytest.raises(SaltCloudException):
        cloud.check_name("test", string.digits)


def test__strip_cache_events():
    events = {
        "test": "foobar",
        "passwd": "fakepass",
    }
    events2 = {"test1": "foobar", "test2": "foobar"}
    opts = {"cache_event_strip_fields": ["passwd"]}
    assert cloud._strip_cache_events(events, opts) == {"test": "foobar"}
    assert cloud._strip_cache_events(events2, opts) == events2


def test_salt_cloud_force_asciii():
    try:
        "\u0411".encode("iso-8859-15")
    except UnicodeEncodeError as exc:
        with pytest.raises(UnicodeEncodeError):
            cloud._salt_cloud_force_ascii(exc)

    with pytest.raises(TypeError):
        cloud._salt_cloud_force_ascii("not the thing")

    try:
        "\xa0\u2013".encode("iso-8859-15")
    except UnicodeEncodeError as exc:
        assert cloud._salt_cloud_force_ascii(exc) == ("-", 2)


def test__unwrap_dict():
    assert cloud._unwrap_dict({"a": {"b": {"c": "foobar"}}}, "a,b,c") == "foobar"


def test_get_salt_interface():
    with patch(
        "salt.config.get_cloud_config_value",
        MagicMock(side_effect=[False, "public_ips"]),
    ) as cloud_config:
        assert cloud.get_salt_interface({}, {}) == "public_ips"
        assert cloud_config.call_count == 2
    with patch(
        "salt.config.get_cloud_config_value", MagicMock(return_value="private_ips")
    ) as cloud_config:
        assert cloud.get_salt_interface({}, {}) == "private_ips"
        assert cloud_config.call_count == 1


def test_userdata_template():
    assert cloud.userdata_template(opts=None, vm_=None, userdata=None) is None
    with patch("salt.config.get_cloud_config_value", MagicMock(return_value=False)):
        assert cloud.userdata_template(opts=None, vm_=None, userdata="test") == "test"
    with patch("salt.config.get_cloud_config_value", MagicMock(return_value=None)):
        opts = {"userdata_template": None}
        assert cloud.userdata_template(opts=opts, vm_=None, userdata="test") == "test"

    renders = {"jinja": MagicMock(return_value="test")}

    with patch("salt.config.get_cloud_config_value", MagicMock(return_value="jinja")):
        with patch("salt.loader.render", MagicMock(return_value=renders)):
            opts = {
                "userdata_template": "test",
                "renderer_blacklist": None,
                "renderer_whitelist": None,
                "renderer": "jinja",
            }
            assert cloud.userdata_template(opts=opts, vm_={}, userdata="test") == "test"

    renders = {"jinja": MagicMock(return_value=True)}

    with patch("salt.config.get_cloud_config_value", MagicMock(return_value="jinja")):
        with patch("salt.loader.render", MagicMock(return_value=renders)):
            opts = {
                "userdata_template": "test",
                "renderer_blacklist": None,
                "renderer_whitelist": None,
                "renderer": "jinja",
            }
            assert cloud.userdata_template(opts=opts, vm_={}, userdata="test") == "True"
