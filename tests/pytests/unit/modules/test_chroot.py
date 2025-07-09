"""
:maintainer:    Alberto Planas <aplanas@suse.com>
:platform:      Linux
"""

import sys

import pytest

import salt.loader.context
import salt.modules.chroot as chroot
import salt.utils.platform
from salt.exceptions import CommandExecutionError
from tests.support.mock import MagicMock, patch

pytestmark = [
    pytest.mark.skip_on_windows,
]


@pytest.fixture
def configure_loader_modules():
    loader_context = salt.loader.context.LoaderContext()
    return {
        chroot: {
            "__salt__": {},
            "__utils__": {"files.rm_rf": MagicMock()},
            "__opts__": {"extension_modules": "", "cachedir": "/tmp/"},
            "__pillar__": salt.loader.context.NamedLoaderContext(
                "__pillar__", loader_context, {}
            ),
        }
    }


def test__create_and_execute_salt_state():
    with patch("salt.client.ssh.wrapper.state._cleanup_slsmod_low_data", MagicMock()):
        with patch("salt.utils.hashutils.get_hash", MagicMock(return_value="deadbeaf")):
            with patch("salt.fileclient.get_file_client", MagicMock()):
                with patch("salt.modules.chroot.call", MagicMock()):
                    chroot._create_and_execute_salt_state("", {}, {}, False, "md5")


def test_exist():
    """
    Test if the chroot environment exist.
    """
    with patch("os.path.isdir") as isdir:
        isdir.side_effect = (True, True, True, True)
        assert chroot.exist("/chroot")

    with patch("os.path.isdir") as isdir:
        isdir.side_effect = (True, True, True, False)
        assert not chroot.exist("/chroot")


def test_create():
    """
    Test the creation of an empty chroot environment.
    """
    with patch("os.makedirs") as makedirs:
        with patch("salt.modules.chroot.exist") as exist:
            exist.return_value = True
            assert chroot.create("/chroot")
            makedirs.assert_not_called()

    with patch("os.makedirs") as makedirs:
        with patch("salt.modules.chroot.exist") as exist:
            exist.return_value = False
            assert chroot.create("/chroot")
            makedirs.assert_called()


def test_in_chroot():
    """
    Test the detection of chroot environment.
    """
    matrix = (("a", "b", True), ("a", "a", False))
    with patch("salt.utils.files.fopen") as fopen:
        for root_mountinfo, self_mountinfo, result in matrix:
            fopen.return_value.__enter__.return_value = fopen
            fopen.read = MagicMock(side_effect=(root_mountinfo, self_mountinfo))
            assert chroot.in_chroot() == result


def test_call_fails_input_validation():
    """
    Test execution of Salt functions in chroot.
    """
    # Basic input validation
    with patch("salt.modules.chroot.exist") as exist:
        exist.return_value = False
        pytest.raises(CommandExecutionError, chroot.call, "/chroot", "")
        pytest.raises(CommandExecutionError, chroot.call, "/chroot", "test.ping")


def test_call_fails_untar():
    """
    Test execution of Salt functions in chroot.
    """
    # Fail the tar command
    with patch("salt.modules.chroot.exist") as exist:
        with patch("tempfile.mkdtemp") as mkdtemp:
            exist.return_value = True
            mkdtemp.return_value = "/chroot/tmp01"
            utils_mock = {
                "thin.gen_thin": MagicMock(return_value="/salt-thin.tgz"),
                "files.rm_rf": MagicMock(),
            }
            salt_mock = {
                "cmd.run": MagicMock(return_value="Error"),
                "config.option": MagicMock(),
            }
            with patch.dict(chroot.__utils__, utils_mock), patch.dict(
                chroot.__salt__, salt_mock
            ):
                assert chroot.call("/chroot", "test.ping") == {
                    "result": False,
                    "comment": "Error",
                }
                utils_mock["thin.gen_thin"].assert_called_once()
                salt_mock["config.option"].assert_called()
                salt_mock["cmd.run"].assert_called_once()
                utils_mock["files.rm_rf"].assert_called_once()


def test_call_fails_salt_thin():
    """
    Test execution of Salt functions in chroot.
    """
    # Fail the inner command
    with patch("salt.modules.chroot.exist") as exist:
        with patch("tempfile.mkdtemp") as mkdtemp:
            exist.return_value = True
            mkdtemp.return_value = "/chroot/tmp01"
            utils_mock = {
                "thin.gen_thin": MagicMock(return_value="/salt-thin.tgz"),
                "files.rm_rf": MagicMock(),
                "json.find_json": MagicMock(side_effect=ValueError()),
            }
            salt_mock = {
                "cmd.run": MagicMock(return_value=""),
                "config.option": MagicMock(),
                "cmd.run_chroot": MagicMock(
                    return_value={"retcode": 1, "stdout": "", "stderr": "Error"}
                ),
            }
            with patch.dict(chroot.__utils__, utils_mock), patch.dict(
                chroot.__salt__, salt_mock
            ):
                assert chroot.call("/chroot", "test.ping") == {
                    "result": False,
                    "retcode": 1,
                    "comment": {"stdout": "", "stderr": "Error"},
                }
                utils_mock["thin.gen_thin"].assert_called_once()
                salt_mock["config.option"].assert_called()
                salt_mock["cmd.run"].assert_called_once()
                salt_mock["cmd.run_chroot"].assert_called_with(
                    "/chroot",
                    [
                        f"python{sys.version_info[0]}",
                        "/tmp01/salt-call",
                        "--metadata",
                        "--local",
                        "--log-file",
                        "/tmp01/log",
                        "--cachedir",
                        "/tmp01/cache",
                        "--out",
                        "json",
                        "-l",
                        "quiet",
                        "--",
                        "test.ping",
                    ],
                )
                utils_mock["files.rm_rf"].assert_called_once()


def test_call_success():
    """
    Test execution of Salt functions in chroot.
    """
    # Success test
    with patch("salt.modules.chroot.exist") as exist:
        with patch("tempfile.mkdtemp") as mkdtemp:
            exist.return_value = True
            mkdtemp.return_value = "/chroot/tmp01"
            utils_mock = {
                "thin.gen_thin": MagicMock(return_value="/salt-thin.tgz"),
                "files.rm_rf": MagicMock(),
                "json.find_json": MagicMock(return_value={"return": "result"}),
            }
            salt_mock = {
                "cmd.run": MagicMock(return_value=""),
                "config.option": MagicMock(),
                "cmd.run_chroot": MagicMock(return_value={"retcode": 0, "stdout": ""}),
            }
            with patch.dict(chroot.__utils__, utils_mock), patch.dict(
                chroot.__salt__, salt_mock
            ):
                assert chroot.call("/chroot", "test.ping") == "result"
                utils_mock["thin.gen_thin"].assert_called_once()
                salt_mock["config.option"].assert_called()
                salt_mock["cmd.run"].assert_called_once()
                salt_mock["cmd.run_chroot"].assert_called_with(
                    "/chroot",
                    [
                        f"python{sys.version_info[0]}",
                        "/tmp01/salt-call",
                        "--metadata",
                        "--local",
                        "--log-file",
                        "/tmp01/log",
                        "--cachedir",
                        "/tmp01/cache",
                        "--out",
                        "json",
                        "-l",
                        "quiet",
                        "--",
                        "test.ping",
                    ],
                )
                utils_mock["files.rm_rf"].assert_called_once()


def test_call_success_parameters():
    """
    Test execution of Salt functions in chroot with parameters.
    """
    # Success test
    with patch("salt.modules.chroot.exist") as exist:
        with patch("tempfile.mkdtemp") as mkdtemp:
            exist.return_value = True
            mkdtemp.return_value = "/chroot/tmp01"
            utils_mock = {
                "thin.gen_thin": MagicMock(return_value="/salt-thin.tgz"),
                "files.rm_rf": MagicMock(),
                "json.find_json": MagicMock(return_value={"return": "result"}),
            }
            salt_mock = {
                "cmd.run": MagicMock(return_value=""),
                "config.option": MagicMock(),
                "cmd.run_chroot": MagicMock(return_value={"retcode": 0, "stdout": ""}),
            }
            with patch.dict(chroot.__utils__, utils_mock), patch.dict(
                chroot.__salt__, salt_mock
            ):
                assert (
                    chroot.call("/chroot", "module.function", key="value") == "result"
                )
                utils_mock["thin.gen_thin"].assert_called_once()
                salt_mock["config.option"].assert_called()
                salt_mock["cmd.run"].assert_called_once()
                salt_mock["cmd.run_chroot"].assert_called_with(
                    "/chroot",
                    [
                        f"python{sys.version_info[0]}",
                        "/tmp01/salt-call",
                        "--metadata",
                        "--local",
                        "--log-file",
                        "/tmp01/log",
                        "--cachedir",
                        "/tmp01/cache",
                        "--out",
                        "json",
                        "-l",
                        "quiet",
                        "--",
                        "module.function",
                        "key=value",
                    ],
                )
                utils_mock["files.rm_rf"].assert_called_once()


def test_sls():
    """
    Test execution of Salt states in chroot.
    """
    with patch("salt.utils.state.get_sls_opts") as get_sls_opts:
        with patch("salt.fileclient.get_file_client") as get_file_client:
            with patch("salt.client.ssh.state.SSHHighState") as SSHHighState:
                with patch(
                    "salt.modules.chroot._create_and_execute_salt_state"
                ) as _create_and_execute_salt_state:
                    SSHHighState.return_value = SSHHighState
                    SSHHighState.render_highstate.return_value = (None, [])
                    SSHHighState.state.reconcile_extend.return_value = (None, [])
                    SSHHighState.state.requisite_in.return_value = (None, [])
                    SSHHighState.state.verify_high.return_value = []

                    _create_and_execute_salt_state.return_value = "result"
                    opts_mock = {
                        "hash_type": "md5",
                    }
                    get_sls_opts.return_value = opts_mock
                    with patch.dict(chroot.__opts__, opts_mock):
                        assert chroot.sls("/chroot", "module") == "result"
                        _create_and_execute_salt_state.assert_called_once()


def test_highstate():
    """
    Test execution of Salt states in chroot.
    """
    with patch("salt.utils.state.get_sls_opts") as get_sls_opts:
        with patch("salt.fileclient.get_file_client") as get_file_client:
            with patch("salt.client.ssh.state.SSHHighState") as SSHHighState:
                with patch(
                    "salt.modules.chroot._create_and_execute_salt_state"
                ) as _create_and_execute_salt_state:
                    SSHHighState.return_value = SSHHighState

                    _create_and_execute_salt_state.return_value = "result"
                    opts_mock = {
                        "hash_type": "md5",
                    }
                    get_sls_opts.return_value = opts_mock
                    with patch.dict(chroot.__opts__, opts_mock):
                        assert chroot.highstate("/chroot") == "result"
                        _create_and_execute_salt_state.assert_called_once()
