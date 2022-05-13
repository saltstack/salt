import io

import pytest
import salt.modules.cmdmod as cmdmod
import salt.modules.restartcheck as restartcheck
import salt.modules.system as system
import salt.modules.systemd_service as service
from tests.support.mock import create_autospec, patch


@pytest.fixture
def configure_loader_modules():
    return {restartcheck: {}}


def test_when_timestamp_file_does_not_exist_then_file_changed_nilrt_should_be_True():
    expected_changed = True

    def timestamp_not_exists(filename):
        if filename.endswith(".timestamp"):
            return False
        return True

    with patch("os.path.exists", side_effect=timestamp_not_exists, autospec=True):
        actual_changed = restartcheck._file_changed_nilrt(full_filepath="fnord")
        assert actual_changed == expected_changed


def test_when_timestamp_file_exists_but_not_md5sum_file_then_file_changed_nilrt_should_be_True():
    expected_changed = True

    def timestamp_not_exists(filename):
        if filename.endswith(".md5sum"):
            return False
        return True

    with patch("os.path.exists", side_effect=timestamp_not_exists, autospec=True):
        actual_changed = restartcheck._file_changed_nilrt(full_filepath="fnord")
        assert actual_changed == expected_changed


def test_when_nisysapi_path_exists_and_nilrt_files_changed_then_sysapi_changed_nilrt_should_be_True():
    expected_change = True
    patch_os_path = patch("os.path.exists", return_value=True, autospec=True)
    patch_file_changed = patch(
        "salt.modules.restartcheck._file_changed_nilrt",
        autospec=True,
        return_value=True,
    )
    with patch_os_path, patch_file_changed:
        actual_change = restartcheck._sysapi_changed_nilrt()
    assert actual_change == expected_change


# TODO: can I parametrize a fixture? And use mocked_grain or something? -W. Werner, 2020-08-18
@pytest.mark.parametrize("cpuarch_grain", ["arm", "x86_64"])
def test_when_nisysapi_conf_d_path_does_not_exist_then_sysapi_changed_should_be_False(
    cpuarch_grain,
):
    expected_change = False

    def conf_d_not_exists(filename):
        return "nisysapi/conf.d" not in filename

    patch_os_path = patch(
        "os.path.exists", side_effect=conf_d_not_exists, autospec=True
    )
    patch_file_changed = patch(
        "salt.modules.restartcheck._file_changed_nilrt",
        autospec=True,
        return_value=False,
    )
    patch_grain = patch.dict(restartcheck.__grains__, {"cpuarch": cpuarch_grain})
    with patch_os_path, patch_file_changed, patch_grain:
        actual_change = restartcheck._sysapi_changed_nilrt()
    assert actual_change == expected_change


@pytest.mark.parametrize("cpuarch_grain", ["arm", "x86_64"])
def test_when_nisysapi_conf_d_path_does_exist_and_no_restart_check_file_exists_then_sysapi_changed_should_be_True(
    cpuarch_grain,
):
    expected_change = True

    def conf_d_not_exists(filename):
        return not filename.endswith("/sysapi.conf.d.count")

    patch_os_path = patch(
        "os.path.exists", side_effect=conf_d_not_exists, autospec=True
    )
    patch_file_changed = patch(
        "salt.modules.restartcheck._file_changed_nilrt",
        autospec=True,
        return_value=False,
    )
    patch_grain = patch.dict(restartcheck.__grains__, {"cpuarch": cpuarch_grain})
    with patch_os_path, patch_file_changed, patch_grain:
        actual_change = restartcheck._sysapi_changed_nilrt()
    assert actual_change == expected_change


@pytest.mark.parametrize("cpuarch_grain", ["arm", "x86_64"])
def test_when_nisysapi_conf_d_path_does_exist_and_count_file_exists_and_count_is_different_than_files_in_conf_d_path_then_sysapi_changed_should_be_True(
    cpuarch_grain,
):
    expected_change = True

    # Fake count and listdir should be different values
    fake_count = io.StringIO("42")
    patch_listdir = patch("os.listdir", autospec=True, return_value=["boop"])
    patch_os_path = patch("os.path.exists", return_value=True, autospec=True)
    patch_file_changed = patch(
        "salt.modules.restartcheck._file_changed_nilrt",
        autospec=True,
        return_value=False,
    )
    patch_grain = patch.dict(restartcheck.__grains__, {"cpuarch": cpuarch_grain})
    patch_fopen = patch(
        "salt.utils.files.fopen", autospec=True, return_value=fake_count
    )
    with patch_os_path, patch_file_changed, patch_grain, patch_listdir, patch_fopen:
        actual_change = restartcheck._sysapi_changed_nilrt()
    assert actual_change == expected_change


@pytest.mark.parametrize("cpuarch_grain", ["arm", "x86_64"])
def test_when_nisysapi_conf_d_path_does_exist_and_count_file_exists_and_count_is_same_as_files_in_conf_d_path_but_no_nilrt_files_changed_then_sysapi_changed_should_be_False(
    cpuarch_grain,
):
    expected_change = False
    # listdir should return the same number of values as count
    fake_count = io.StringIO("42")
    patch_listdir = patch("os.listdir", autospec=True, return_value=["boop"] * 42)
    patch_os_path = patch("os.path.exists", return_value=True, autospec=True)
    patch_file_changed = patch(
        "salt.modules.restartcheck._file_changed_nilrt",
        autospec=True,
        return_value=False,
    )
    patch_grain = patch.dict(restartcheck.__grains__, {"cpuarch": cpuarch_grain})
    patch_fopen = patch(
        "salt.utils.files.fopen", autospec=True, return_value=fake_count
    )
    with patch_os_path, patch_file_changed, patch_grain, patch_listdir, patch_fopen:
        actual_change = restartcheck._sysapi_changed_nilrt()
    assert actual_change == expected_change


@pytest.mark.parametrize("cpuarch_grain", ["arm", "x86_64"])
def test_when_nisysapi_conf_d_path_does_exist_and_count_file_exists_and_count_is_same_as_files_in_conf_d_path_and_file_changed_nilrt_then_sysapi_changed_should_be_True(
    cpuarch_grain,
):
    expected_change = True

    def fake_file_changed(filename):
        return filename != "/usr/local/natinst/share/nisysapi.ini"

    # listdir should return the same number of values as count
    fake_count = io.StringIO("42")
    patch_listdir = patch("os.listdir", autospec=True, return_value=["boop"] * 42)
    patch_os_path = patch("os.path.exists", return_value=True, autospec=True)
    patch_file_changed = patch(
        "salt.modules.restartcheck._file_changed_nilrt",
        autospec=True,
        side_effect=fake_file_changed,
    )
    patch_grain = patch.dict(restartcheck.__grains__, {"cpuarch": cpuarch_grain})
    patch_fopen = patch(
        "salt.utils.files.fopen", autospec=True, return_value=fake_count
    )
    with patch_os_path, patch_file_changed, patch_grain, patch_listdir, patch_fopen:
        actual_change = restartcheck._sysapi_changed_nilrt()
    assert actual_change == expected_change


def test_when_nilinuxrt_and_not_kernel_modules_changed_or_sysapi_files_changed_and_not_reboot_required_witnessed_then_no_reboot_should_be_required():
    expected_result = "No packages seem to need to be restarted."
    restart_required = False
    current_kernel = "fnord"

    patch_grains = patch.dict(restartcheck.__grains__, {"os_family": "NILinuxRT"})
    patch_kernel_versions = patch(
        "salt.modules.restartcheck._kernel_versions_nilrt",
        autospec=True,
        return_value=[current_kernel],
    )
    patch_salt = patch.dict(
        restartcheck.__salt__,
        {
            "cmd.run": create_autospec(cmdmod.run, return_value=current_kernel),
            "system.get_reboot_required_witnessed": create_autospec(
                system.get_reboot_required_witnessed,
                return_value=restart_required,
            ),
            "service.get_running": create_autospec(
                service.get_running, return_value=[]
            ),
        },
    )
    patch_kernel_mod_changed = patch(
        "salt.modules.restartcheck._kernel_modules_changed_nilrt",
        autospec=True,
        return_value=False,
    )
    patch_sysapi_changed = patch(
        "salt.modules.restartcheck._sysapi_changed_nilrt",
        autospec=True,
        return_value=False,
    )
    patch_del_files = patch(
        "salt.modules.restartcheck._deleted_files",
        autospec=True,
        return_value=[],
    )

    with patch_grains, patch_kernel_versions, patch_salt, patch_sysapi_changed, patch_kernel_mod_changed, patch_del_files:
        actual_result = restartcheck.restartcheck()
    assert actual_result == expected_result


def test_when_nilinuxrt_and_not_kernel_modules_changed_or_sysapi_files_changed_and_reboot_required_witnessed_then_reboot_should_be_required():
    expected_result = "System restart required.\n\n"
    restart_required = True
    current_kernel = "fnord"

    patch_grains = patch.dict(restartcheck.__grains__, {"os_family": "NILinuxRT"})
    patch_kernel_versions = patch(
        "salt.modules.restartcheck._kernel_versions_nilrt",
        autospec=True,
        return_value=[current_kernel],
    )
    patch_salt = patch.dict(
        restartcheck.__salt__,
        {
            "cmd.run": create_autospec(cmdmod.run, return_value=current_kernel),
            "system.get_reboot_required_witnessed": create_autospec(
                system.get_reboot_required_witnessed,
                return_value=restart_required,
            ),
            "service.get_running": create_autospec(
                service.get_running, return_value=[]
            ),
        },
    )
    patch_kernel_mod_changed = patch(
        "salt.modules.restartcheck._kernel_modules_changed_nilrt",
        autospec=True,
        return_value=False,
    )
    patch_sysapi_changed = patch(
        "salt.modules.restartcheck._sysapi_changed_nilrt",
        autospec=True,
        return_value=False,
    )
    patch_del_files = patch(
        "salt.modules.restartcheck._deleted_files",
        autospec=True,
        return_value=[],
    )

    with patch_grains, patch_kernel_versions, patch_salt, patch_sysapi_changed, patch_kernel_mod_changed, patch_del_files:
        actual_result = restartcheck.restartcheck()
    assert actual_result == expected_result
