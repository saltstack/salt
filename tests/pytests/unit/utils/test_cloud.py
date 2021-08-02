"""
    :codeauthor: Pedro Algarvio (pedro@algarvio.me)
    tests.unit.utils.cloud_test
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Test the salt-cloud utilities module.

"""


import os
import tempfile

import pytest
import salt.utils.cloud as cloud
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
            ):  # pylint: disable=arguments-differ
                self.__storage.setdefault(servicename, {}).update({username: password})
                return 0

            def get_password(
                self, servicename, username
            ):  # pylint: disable=arguments-differ
                return self.__storage.setdefault(servicename, {}).get(username)

            def delete_password(
                self, servicename, username
            ):  # pylint: disable=arguments-differ
                self.__storage.setdefault(servicename, {}).pop(username, None)
                return 0

        # set the keyring for keyring lib
        keyring.set_keyring(CustomKeyring())
        yield
    except ImportError:
        pytest.skip('The "keyring" python module is not installed')
    finally:
        os.chdir(old_cwd)


def test_ssh_password_regex(create_class):
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
        "salt.cloud.provider.test_case_provider", "fake_username",
    )
    keyring.delete_password(
        "salt.cloud.provider.test_case_provider", "fake_username",
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


def test_sftp_file_with_content_under_python3(create_class):
    with pytest.raises(Exception) as context:
        cloud.sftp_file("/tmp/test", "ТЕSТ test content")
        # we successful pass the place with os.write(tmpfd, ...
        assert "a bytes-like object is required, not 'str'" != str(context.exception)


@pytest.mark.skip_on_windows(reason="Not applicable for Windows.")
def test_check_key_path_and_mode(create_class):
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
    # fmt: off
    with patch("salt.utils.smb.get_conn", MagicMock()) as mock,\
            patch("salt.utils.smb.mkdirs", MagicMock()), \
            patch("salt.utils.smb.put_file", MagicMock()), \
            patch("salt.utils.smb.delete_file", MagicMock()), \
            patch("salt.utils.smb.delete_directory", MagicMock()), \
            patch("time.sleep", MagicMock()),\
            patch.object(cloud, "wait_for_port", mock_true), \
            patch.object(cloud, "fire_event", MagicMock()), \
            patch.object(cloud, "wait_for_psexecsvc", mock_true),\
            patch.object(cloud, "run_psexec_command", mock_tuple):

        cloud.deploy_windows(host="test", win_installer="")
        mock.assert_called_once_with("test", "Administrator", None, 445)
    # fmt: on


@pytest.mark.skip_unless_on_windows(reason="Only applicable for Windows.")
def test_deploy_windows_custom_port():
    """
    Test deploy_windows with a custom port
    """
    mock_true = MagicMock(return_value=True)
    mock_tuple = MagicMock(return_value=(0, 0, 0))
    # fmt: off
    with patch("salt.utils.smb.get_conn", MagicMock()) as mock, \
            patch("salt.utils.smb.mkdirs", MagicMock()), \
            patch("salt.utils.smb.put_file", MagicMock()), \
            patch("salt.utils.smb.delete_file", MagicMock()), \
            patch("salt.utils.smb.delete_directory", MagicMock()), \
            patch("time.sleep", MagicMock()), \
            patch.object(cloud, "wait_for_port", mock_true), \
            patch.object(cloud, "fire_event", MagicMock()), \
            patch.object(cloud, "wait_for_psexecsvc", mock_true), \
            patch.object(cloud, "run_psexec_command", mock_tuple):

        cloud.deploy_windows(host="test", port=1234, win_installer="")
        mock.assert_called_once_with("test", "Administrator", None, 1234)
    # fmt: on


@pytest.mark.skip_unless_on_windows(reason="Only applicable for Windows.")
def test_winrm_pinnned_version():
    """
    Test that winrm is pinned to a version 0.3.0 or higher.
    """
    mock_true = MagicMock(return_value=True)
    mock_tuple = MagicMock(return_value=(0, 0, 0))
    # fmt: off
    with patch("salt.utils.smb.get_conn", MagicMock()),\
            patch("salt.utils.smb.mkdirs", MagicMock()), \
            patch("salt.utils.smb.put_file", MagicMock()), \
            patch("salt.utils.smb.delete_file", MagicMock()), \
            patch("salt.utils.smb.delete_directory", MagicMock()), \
            patch("time.sleep", MagicMock()),\
            patch.object(cloud, "wait_for_port", mock_true), \
            patch.object(cloud, "fire_event", MagicMock()), \
            patch.object(cloud, "wait_for_psexecsvc", mock_true),\
            patch.object(cloud, "run_psexec_command", mock_tuple):

        try:
            import winrm
        except ImportError:
            raise pytest.skip('The "winrm" python module is not installed in this env.')
        else:
            import pkg_resources
            winrm_pkg = pkg_resources.get_distribution("pywinrm")
            assert winrm_pkg.version >= '0.3.0'
    # fmt: on
