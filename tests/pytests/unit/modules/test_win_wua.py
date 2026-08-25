"""
Test the win_wua execution module
"""

import os

import pytest

import salt.modules.win_wua as win_wua
import salt.utils.platform
import salt.utils.win_update
from salt.exceptions import CommandExecutionError
from tests.support.mock import MagicMock, patch

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.skip_unless_on_windows,
]


@pytest.fixture
def configure_loader_modules():
    return {win_wua: {}}


@pytest.fixture
def wu_services(monkeypatch):
    """
    Patch service.stop/service.start/service.restart in win_wua.__salt__ to
    succeed, and salt.utils.win_update.needs_reboot to return False, and
    return the mocks for assertions.
    """
    mock_stop = MagicMock(return_value=True)
    mock_start = MagicMock(return_value=True)
    with patch.dict(
        win_wua.__salt__, {"service.stop": mock_stop, "service.start": mock_start}
    ), patch("salt.utils.win_update.needs_reboot", autospec=True, return_value=False):
        yield {"stop": mock_stop, "start": mock_start}


@pytest.fixture
def updates_list():
    return {
        "ca3bb521-a8ea-4e26-a563-2ad6e3108b9a": {"KBs": ["KB4481252"]},
        "07609d43-d518-4e77-856e-d1b316d1b8a8": {"KBs": ["KB925673"]},
        "fbaa5360-a440-49d8-a3b6-0c4fc7ecaa19": {"KBs": ["KB4481252"]},
        "a873372b-7a5c-443c-8022-cd59a550bef4": {"KBs": ["KB3193497"]},
        "14075cbe-822e-4004-963b-f50e08d45563": {"KBs": ["KB4540723"]},
        "d931e99c-4dda-4d39-9905-0f6a73f7195f": {"KBs": ["KB3193497"]},
        "afda9e11-44a0-4602-9e9b-423af11ecaed": {"KBs": ["KB4541329"]},
        "a0f997b1-1abe-4a46-941f-b37f732f9fbd": {"KBs": ["KB3193497"]},
        "eac02b09-d745-4891-b80f-400e0e5e4b6d": {"KBs": ["KB4052623"]},
        "0689e74b-54d1-4f55-a916-96e3c737db90": {"KBs": ["KB890830"]},
    }


@pytest.fixture
def updates_summary():
    return {"Installed": 10}


class Updates:
    @staticmethod
    def list():
        return {
            "ca3bb521-a8ea-4e26-a563-2ad6e3108b9a": {"KBs": ["KB4481252"]},
            "07609d43-d518-4e77-856e-d1b316d1b8a8": {"KBs": ["KB925673"]},
            "fbaa5360-a440-49d8-a3b6-0c4fc7ecaa19": {"KBs": ["KB4481252"]},
            "a873372b-7a5c-443c-8022-cd59a550bef4": {"KBs": ["KB3193497"]},
            "14075cbe-822e-4004-963b-f50e08d45563": {"KBs": ["KB4540723"]},
            "d931e99c-4dda-4d39-9905-0f6a73f7195f": {"KBs": ["KB3193497"]},
            "afda9e11-44a0-4602-9e9b-423af11ecaed": {"KBs": ["KB4541329"]},
            "a0f997b1-1abe-4a46-941f-b37f732f9fbd": {"KBs": ["KB3193497"]},
            "eac02b09-d745-4891-b80f-400e0e5e4b6d": {"KBs": ["KB4052623"]},
            "0689e74b-54d1-4f55-a916-96e3c737db90": {"KBs": ["KB890830"]},
        }

    @staticmethod
    def summary():
        return {"Installed": 10}


def test__virtual__not_windows():
    """
    Test __virtual__ function on Non-Windows
    """
    with patch("salt.utils.platform.is_windows", autospec=True, return_value=False):
        expected = (False, "WUA: Only available on Windows systems")
        result = win_wua.__virtual__()
        assert result == expected


def test__virtual__missing_pywin32():
    """
    Test __virtual__ function when pywin32 is not installed
    """
    with patch("salt.modules.win_wua.HAS_PYWIN32", False):
        expected = (False, "WUA: Requires PyWin32 libraries")
        result = win_wua.__virtual__()
        assert result == expected


def test__virtual__wuauserv_disabled():
    """
    Test __virtual__ function when the wuauserv service is disabled
    """
    mock_service_info = MagicMock(
        side_effect=[
            {"StartType": "Disabled"},  # wuauserv
            {"StartType": "Auto"},  # msiserver
            {"StartType": "Auto"},  # BITS
            {"StartType": "Auto"},  # CryptSvc
            {"StartType": "Auto"},  # TrustedInstaller
        ]
    )
    with patch("salt.utils.win_service.info", mock_service_info):
        expected = (
            False,
            "WUA: The Windows Update service (wuauserv) must not be disabled",
        )
        result = win_wua.__virtual__()
        assert result == expected


def test__virtual__msiserver_disabled():
    """
    Test __virtual__ function when the msiserver service is disabled
    """
    mock_service_info = MagicMock(
        side_effect=[
            {"StartType": "Auto"},  # wuauserv
            {"StartType": "Disabled"},  # msiserver
            {"StartType": "Auto"},  # BITS
            {"StartType": "Auto"},  # CryptSvc
            {"StartType": "Auto"},  # TrustedInstaller
        ]
    )
    with patch("salt.utils.win_service.info", mock_service_info):
        expected = (
            False,
            "WUA: The Windows Installer service (msiserver) must not be disabled",
        )
        result = win_wua.__virtual__()
        assert result == expected


def test__virtual__BITS_disabled():
    """
    Test __virtual__ function when the BITS service is disabled
    """
    mock_service_info = MagicMock(
        side_effect=[
            {"StartType": "Auto"},  # wuauserv
            {"StartType": "Auto"},  # msiserver
            {"StartType": "Disabled"},  # BITS
            {"StartType": "Auto"},  # CryptSvc
            {"StartType": "Auto"},  # TrustedInstaller
        ]
    )
    with patch("salt.utils.win_service.info", mock_service_info):
        expected = (
            False,
            "WUA: The Background Intelligent Transfer service (bits) must not be"
            " disabled",
        )
        result = win_wua.__virtual__()
        assert result == expected


def test__virtual__BITS_manual():
    """
    Test __virtual__ function when the BITS service is set to manual
    Should not disable the module (__virtual__ should return True)
    """
    mock_service_info = MagicMock(
        side_effect=[
            {"StartType": "Auto"},  # wuauserv
            {"StartType": "Auto"},  # msiserver
            {"StartType": "Manual"},  # BITS
            {"StartType": "Auto"},  # CryptSvc
            {"StartType": "Auto"},  # TrustedInstaller
        ]
    )
    with patch("salt.utils.win_service.info", mock_service_info):
        expected = True
        result = win_wua.__virtual__()
        assert result == expected


def test__virtual__CryptSvc_disabled():
    """
    Test __virtual__ function when the CryptSvc service is disabled
    """
    mock_service_info = MagicMock(
        side_effect=[
            {"StartType": "Auto"},  # wuauserv
            {"StartType": "Auto"},  # msiserver
            {"StartType": "Auto"},  # BITS
            {"StartType": "Disabled"},  # CryptSvc
            {"StartType": "Auto"},  # TrustedInstaller
        ]
    )
    with patch("salt.utils.win_service.info", mock_service_info):
        expected = (
            False,
            "WUA: The Cryptographic Services service (CryptSvc) must not be"
            " disabled",
        )
        result = win_wua.__virtual__()
        assert result == expected


def test__virtual__CryptSvc_manual():
    """
    Test __virtual__ function when the CryptSvc service is disabled
    """
    mock_service_info = MagicMock(
        side_effect=[
            {"StartType": "Auto"},  # wuauserv
            {"StartType": "Auto"},  # msiserver
            {"StartType": "Auto"},  # BITS
            {"StartType": "Manual"},  # CryptSvc
            {"StartType": "Auto"},  # TrustedInstaller
        ]
    )
    with patch("salt.utils.win_service.info", mock_service_info):
        result = win_wua.__virtual__()
        assert result is True


def test__virtual__TrustedInstaller_disabled():
    """
    Test __virtual__ function when the TrustedInstaller service is disabled
    """
    mock_service_info = MagicMock(
        side_effect=[
            {"StartType": "Auto"},  # wuauserv
            {"StartType": "Auto"},  # msiserver
            {"StartType": "Auto"},  # BITS
            {"StartType": "Auto"},  # CryptSvc
            {"StartType": "Disabled"},  # TrustedInstaller
        ]
    )
    with patch("salt.utils.win_service.info", mock_service_info):
        expected = (
            False,
            "WUA: The Windows Module Installer service (TrustedInstaller) must not"
            " be disabled",
        )
        result = win_wua.__virtual__()
        assert result == expected


def test_installed(updates_list):
    """
    Test installed function default
    """
    expected = updates_list
    with patch("salt.utils.winapi.Com", autospec=True), patch(
        "win32com.client.Dispatch", autospec=True
    ), patch.object(
        salt.utils.win_update.WindowsUpdateAgent, "refresh", autospec=True
    ), patch.object(
        salt.utils.win_update, "Updates", autospec=True, return_value=Updates()
    ):
        result = win_wua.installed()
        assert result == expected


def test_installed_summary(updates_summary):
    """
    Test installed function with summary=True
    """
    expected = updates_summary
    # Remove all updates that are not installed
    with patch("salt.utils.winapi.Com", autospec=True), patch(
        "win32com.client.Dispatch", autospec=True
    ), patch.object(
        salt.utils.win_update.WindowsUpdateAgent, "refresh", autospec=True
    ), patch.object(
        salt.utils.win_update, "Updates", autospec=True, return_value=Updates()
    ):
        result = win_wua.installed(summary=True)
        assert result == expected


def test_installed_kbs_only(updates_list):
    """
    Test installed function with kbs_only=True
    """
    expected = set()
    for update in updates_list:
        expected.update(updates_list[update]["KBs"])
    expected = sorted(expected)
    # Remove all updates that are not installed
    with patch("salt.utils.winapi.Com", autospec=True), patch(
        "win32com.client.Dispatch", autospec=True
    ), patch.object(
        salt.utils.win_update.WindowsUpdateAgent, "refresh", autospec=True
    ), patch.object(
        salt.utils.win_update, "Updates", autospec=True, return_value=Updates()
    ):
        result = win_wua.installed(kbs_only=True)
        assert result == expected


# ------------------------------------------------------------------------
# reset_datastore / reset_catroot / reset
# ------------------------------------------------------------------------


def test_reset_datastore_happy_path(tmp_path, monkeypatch, wu_services):
    """
    Test reset_datastore renames an existing SoftwareDistribution directory
    """
    monkeypatch.setenv("WINDIR", str(tmp_path))
    sd_path = tmp_path / "SoftwareDistribution"
    sd_path.mkdir()

    with patch("time.time", return_value=1700000000.123):
        result = win_wua.reset_datastore()

    assert result["reboot_pending"] is False
    assert result["SoftwareDistribution"]["old_path"] == str(sd_path)
    assert (
        result["SoftwareDistribution"]["new_path"]
        == str(sd_path) + ".old.1700000000123"
    )
    assert result["SoftwareDistribution"]["purged"] is False
    assert result["SoftwareDistribution"]["result"] is True
    assert not sd_path.exists()
    assert os.path.isdir(result["SoftwareDistribution"]["new_path"])
    wu_services["stop"].assert_any_call("wuauserv")
    wu_services["start"].assert_any_call("wuauserv")


def test_reset_datastore_purge_old(tmp_path, monkeypatch, wu_services):
    """
    Test reset_datastore with purge_old=True deletes instead of renaming
    """
    monkeypatch.setenv("WINDIR", str(tmp_path))
    sd_path = tmp_path / "SoftwareDistribution"
    sd_path.mkdir()
    (sd_path / "file.txt").write_text("data")

    result = win_wua.reset_datastore(purge_old=True)

    assert result["SoftwareDistribution"]["new_path"] is None
    assert result["SoftwareDistribution"]["purged"] is True
    assert not sd_path.exists()


def test_reset_datastore_missing_dir(tmp_path, monkeypatch, wu_services):
    """
    Test reset_datastore when SoftwareDistribution doesn't exist: no-op
    """
    monkeypatch.setenv("WINDIR", str(tmp_path))

    result = win_wua.reset_datastore()

    assert result["SoftwareDistribution"]["new_path"] is None
    assert result["SoftwareDistribution"]["purged"] is False
    assert result["SoftwareDistribution"]["result"] is True


def test_reset_datastore_service_stop_fails(tmp_path, monkeypatch):
    """
    Test reset_datastore raises and does not touch the directory if a
    service fails to stop
    """
    monkeypatch.setenv("WINDIR", str(tmp_path))
    sd_path = tmp_path / "SoftwareDistribution"
    sd_path.mkdir()

    mock_stop = MagicMock(side_effect=[True, False, True, True])
    mock_start = MagicMock(return_value=True)
    with patch.dict(
        win_wua.__salt__, {"service.stop": mock_stop, "service.start": mock_start}
    ), patch("salt.utils.win_update.needs_reboot", autospec=True, return_value=False):
        with pytest.raises(CommandExecutionError):
            win_wua.reset_datastore()

    assert sd_path.exists()
    mock_start.assert_not_called()


def test_reset_datastore_rename_permission_error(tmp_path, monkeypatch, wu_services):
    """
    Test reset_datastore converts an OSError on rename to CommandExecutionError
    """
    monkeypatch.setenv("WINDIR", str(tmp_path))
    sd_path = tmp_path / "SoftwareDistribution"
    sd_path.mkdir()

    with patch("os.rename", side_effect=PermissionError("denied")):
        with pytest.raises(CommandExecutionError):
            win_wua.reset_datastore()

    # services should still be restarted even though the rename failed
    wu_services["start"].assert_any_call("wuauserv")


def test_reset_datastore_rename_collision(tmp_path, monkeypatch, wu_services):
    """
    Test reset_datastore retries the timestamp suffix if the target already
    exists
    """
    monkeypatch.setenv("WINDIR", str(tmp_path))
    sd_path = tmp_path / "SoftwareDistribution"
    sd_path.mkdir()
    colliding = tmp_path / "SoftwareDistribution.old.1700000000123"
    colliding.mkdir()

    with patch("time.time", side_effect=[1700000000.123, 1700000000.124]):
        result = win_wua.reset_datastore()

    assert (
        result["SoftwareDistribution"]["new_path"]
        == str(sd_path) + ".old.1700000000124"
    )


def test_reset_catroot_happy_path(tmp_path, monkeypatch, wu_services):
    """
    Test reset_catroot renames an existing catroot2 directory
    """
    monkeypatch.setenv("WINDIR", str(tmp_path))
    catroot_path = tmp_path / "System32" / "catroot2"
    catroot_path.mkdir(parents=True)

    with patch("time.time", return_value=1700000000.5):
        result = win_wua.reset_catroot()

    assert result["catroot2"]["old_path"] == str(catroot_path)
    assert result["catroot2"]["new_path"] == str(catroot_path) + ".old.1700000000500"
    assert not catroot_path.exists()


def test_reset_catroot_purge_old(tmp_path, monkeypatch, wu_services):
    """
    Test reset_catroot with purge_old=True deletes instead of renaming
    """
    monkeypatch.setenv("WINDIR", str(tmp_path))
    catroot_path = tmp_path / "System32" / "catroot2"
    catroot_path.mkdir(parents=True)

    result = win_wua.reset_catroot(purge_old=True)

    assert result["catroot2"]["new_path"] is None
    assert result["catroot2"]["purged"] is True
    assert not catroot_path.exists()


def test_reset_catroot_missing_dir(tmp_path, monkeypatch, wu_services):
    """
    Test reset_catroot when catroot2 doesn't exist: no-op
    """
    monkeypatch.setenv("WINDIR", str(tmp_path))

    result = win_wua.reset_catroot()

    assert result["catroot2"]["new_path"] is None
    assert result["catroot2"]["result"] is True


def test_reset_catroot_service_stop_fails(tmp_path, monkeypatch):
    """
    Test reset_catroot raises and does not touch the directory if a service
    fails to stop
    """
    monkeypatch.setenv("WINDIR", str(tmp_path))
    catroot_path = tmp_path / "System32" / "catroot2"
    catroot_path.mkdir(parents=True)

    mock_stop = MagicMock(side_effect=[True, True, False, True])
    mock_start = MagicMock(return_value=True)
    with patch.dict(
        win_wua.__salt__, {"service.stop": mock_stop, "service.start": mock_start}
    ), patch("salt.utils.win_update.needs_reboot", autospec=True, return_value=False):
        with pytest.raises(CommandExecutionError):
            win_wua.reset_catroot()

    assert catroot_path.exists()
    mock_start.assert_not_called()


def test_reset_services_stopped_and_started_once(tmp_path, monkeypatch, wu_services):
    """
    Test reset() stops/starts each service exactly once (not once per
    directory)
    """
    monkeypatch.setenv("WINDIR", str(tmp_path))
    sd_path = tmp_path / "SoftwareDistribution"
    sd_path.mkdir()
    catroot_path = tmp_path / "System32" / "catroot2"
    catroot_path.mkdir(parents=True)

    result = win_wua.reset()

    assert wu_services["stop"].call_count == len(win_wua._WU_SERVICES)
    assert wu_services["start"].call_count == len(win_wua._WU_SERVICES)
    assert "SoftwareDistribution" in result
    assert "catroot2" in result
    assert not sd_path.exists()
    assert not catroot_path.exists()


def test_reset_purge_old_propagates(tmp_path, monkeypatch, wu_services):
    """
    Test reset() propagates purge_old to both directories
    """
    monkeypatch.setenv("WINDIR", str(tmp_path))
    sd_path = tmp_path / "SoftwareDistribution"
    sd_path.mkdir()
    catroot_path = tmp_path / "System32" / "catroot2"
    catroot_path.mkdir(parents=True)

    result = win_wua.reset(purge_old=True)

    assert result["SoftwareDistribution"]["purged"] is True
    assert result["catroot2"]["purged"] is True


def test_reset_one_dir_missing(tmp_path, monkeypatch, wu_services):
    """
    Test reset() succeeds when only one of the two directories exists
    """
    monkeypatch.setenv("WINDIR", str(tmp_path))
    sd_path = tmp_path / "SoftwareDistribution"
    sd_path.mkdir()
    # catroot2 intentionally not created

    result = win_wua.reset()

    assert result["SoftwareDistribution"]["new_path"] is not None
    assert result["catroot2"]["new_path"] is None


def test_reset_stop_failure_aborts_before_any_rename(tmp_path, monkeypatch):
    """
    Test reset() raises before touching either directory if a service
    fails to stop
    """
    monkeypatch.setenv("WINDIR", str(tmp_path))
    sd_path = tmp_path / "SoftwareDistribution"
    sd_path.mkdir()
    catroot_path = tmp_path / "System32" / "catroot2"
    catroot_path.mkdir(parents=True)

    mock_stop = MagicMock(return_value=False)
    mock_start = MagicMock(return_value=True)
    with patch.dict(
        win_wua.__salt__, {"service.stop": mock_stop, "service.start": mock_start}
    ), patch("salt.utils.win_update.needs_reboot", autospec=True, return_value=False):
        with pytest.raises(CommandExecutionError):
            win_wua.reset()

    assert sd_path.exists()
    assert catroot_path.exists()
    mock_start.assert_not_called()


def test_reset_datastore_reboot_pending_surfaced_not_blocking(tmp_path, monkeypatch):
    """
    Test reset_datastore surfaces reboot_pending=True without blocking the
    reset
    """
    monkeypatch.setenv("WINDIR", str(tmp_path))
    sd_path = tmp_path / "SoftwareDistribution"
    sd_path.mkdir()

    with patch.dict(
        win_wua.__salt__,
        {
            "service.stop": MagicMock(return_value=True),
            "service.start": MagicMock(return_value=True),
        },
    ), patch("salt.utils.win_update.needs_reboot", autospec=True, return_value=True):
        result = win_wua.reset_datastore()

    assert result["reboot_pending"] is True
    assert not sd_path.exists()


# ------------------------------------------------------------------------
# get_cbs_log
# ------------------------------------------------------------------------


@pytest.fixture
def cbs_log(tmp_path, monkeypatch):
    monkeypatch.setenv("WINDIR", str(tmp_path))
    log_dir = tmp_path / "Logs" / "CBS"
    log_dir.mkdir(parents=True)
    log_path = log_dir / "CBS.log"
    return log_path


def test_get_cbs_log_default_tail(cbs_log):
    """
    Test get_cbs_log returns only the last 500 lines by default
    """
    lines = [f"line {i}" for i in range(600)]
    cbs_log.write_text("\n".join(lines), encoding="utf-8")

    result = win_wua.get_cbs_log()

    assert result.splitlines() == lines[-500:]


def test_get_cbs_log_tail_n(cbs_log):
    """
    Test get_cbs_log tail=N matches content.splitlines()[-N:]
    """
    lines = [f"line {i}" for i in range(50)]
    cbs_log.write_text("\n".join(lines), encoding="utf-8")

    result = win_wua.get_cbs_log(tail=10)

    assert result.splitlines() == lines[-10:]


def test_get_cbs_log_tail_none_returns_whole_file(cbs_log):
    """
    Test get_cbs_log tail=None returns the entire file
    """
    lines = [f"line {i}" for i in range(600)]
    cbs_log.write_text("\n".join(lines), encoding="utf-8")

    result = win_wua.get_cbs_log(tail=None)

    assert result.splitlines() == lines


def test_get_cbs_log_missing_file_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("WINDIR", str(tmp_path))

    with pytest.raises(CommandExecutionError):
        win_wua.get_cbs_log()


def test_get_cbs_log_out_file_writes_and_returns(cbs_log, tmp_path):
    """
    Test get_cbs_log writes to out_file and still returns the content
    """
    cbs_log.write_text("line 1\nline 2\n", encoding="utf-8")
    out_file = tmp_path / "out" / "cbs_tail.log"

    result = win_wua.get_cbs_log(out_file=str(out_file))

    assert result.splitlines() == ["line 1", "line 2"]
    assert out_file.read_text(encoding="utf-8") == result


def test_get_cbs_log_tail_less_than_one_raises(cbs_log):
    cbs_log.write_text("line 1\n", encoding="utf-8")

    with pytest.raises(CommandExecutionError):
        win_wua.get_cbs_log(tail=0)

    with pytest.raises(CommandExecutionError):
        win_wua.get_cbs_log(tail=-1)


def test_get_cbs_log_non_utf8_bytes_do_not_crash(cbs_log):
    with open(cbs_log, "wb") as fp_:
        fp_.write(b"good line\n\xff\xfebad bytes\nmore good\n")

    result = win_wua.get_cbs_log()

    assert "good line" in result
    assert "more good" in result


def test_get_cbs_log_pattern_filters_matches(cbs_log):
    """
    Test get_cbs_log pattern returns only matching lines (plus context)
    """
    lines = [
        "unrelated 1",
        "unrelated 2",
        "unrelated 3",
        "starting up",
        "doing stuff",
        "Package rejected: KB1234567",
        "cleanup",
        "trailing",
        "unrelated 4",
        "unrelated 5",
        "unrelated 6",
    ]
    cbs_log.write_text("\n".join(lines), encoding="utf-8")

    result = win_wua.get_cbs_log(pattern="rejected")

    assert "Package rejected: KB1234567" in result
    assert "unrelated" not in result


def test_get_cbs_log_pattern_list_ors(cbs_log):
    lines = [
        "far away alpha",
        "still far",
        "also far",
        "Failed to apply",
        "beta",
        "middle",
        "gamma superseded",
        "still going",
        "also far 2",
        "far away delta",
    ]
    cbs_log.write_text("\n".join(lines), encoding="utf-8")

    result = win_wua.get_cbs_log(pattern=["Failed", "superseded"])

    assert "Failed to apply" in result
    assert "gamma superseded" in result
    assert "far away" not in result


def test_get_cbs_log_pattern_max_matches_capped(cbs_log):
    lines = [f"Failed line {i}" for i in range(10)]
    cbs_log.write_text("\n".join(lines), encoding="utf-8")

    result = win_wua.get_cbs_log(pattern="Failed", max_matches=3)

    assert result.count("Failed line") == 3


# ------------------------------------------------------------------------
# get_windows_update_log
# ------------------------------------------------------------------------


def test_get_windows_update_log_happy_path(tmp_path):
    log_path = tmp_path / "WindowsUpdate.log"
    lines = [f"line {i}" for i in range(10)]
    log_path.write_text("\n".join(lines), encoding="utf-8")

    with patch(
        "salt.utils.win_pwsh.run_dict",
        autospec=True,
        return_value={"Log": str(log_path)},
    ) as mock_run_dict:
        result = win_wua.get_windows_update_log()

    assert result.splitlines() == lines
    assert mock_run_dict.call_count == 1


def test_get_windows_update_log_out_file_controls_logpath(tmp_path):
    out_file = tmp_path / "custom_wu.log"

    def fake_run_dict(cmd):
        assert str(out_file) in cmd
        out_file.write_text("line 1\nline 2\n", encoding="utf-8")
        return {"Log": str(out_file)}

    with patch(
        "salt.utils.win_pwsh.run_dict", autospec=True, side_effect=fake_run_dict
    ):
        result = win_wua.get_windows_update_log(out_file=str(out_file))

    assert result.splitlines() == ["line 1", "line 2"]


def test_get_windows_update_log_generates_temp_path_when_out_file_none(
    tmp_path, monkeypatch
):
    monkeypatch.setattr("tempfile.gettempdir", lambda: str(tmp_path))
    expected_path = tmp_path / "WindowsUpdate.log"

    def fake_run_dict(cmd):
        assert str(expected_path) in cmd
        expected_path.write_text("content\n", encoding="utf-8")
        return {"Log": str(expected_path)}

    with patch(
        "salt.utils.win_pwsh.run_dict", autospec=True, side_effect=fake_run_dict
    ):
        result = win_wua.get_windows_update_log()

    assert result.splitlines() == ["content"]


def test_get_windows_update_log_uses_log_key_from_run_dict(tmp_path, monkeypatch):
    """
    Test that when run_dict returns a "Log" path different from the one we
    requested, we read from the path run_dict actually reports.
    """
    monkeypatch.setattr("tempfile.gettempdir", lambda: str(tmp_path))
    actual_path = tmp_path / "actual.log"
    actual_path.write_text("actual content\n", encoding="utf-8")

    with patch(
        "salt.utils.win_pwsh.run_dict",
        autospec=True,
        return_value={"Log": str(actual_path)},
    ):
        result = win_wua.get_windows_update_log()

    assert result.splitlines() == ["actual content"]


def test_get_windows_update_log_run_dict_error_propagates():
    with patch(
        "salt.utils.win_pwsh.run_dict",
        autospec=True,
        side_effect=CommandExecutionError("boom"),
    ):
        with pytest.raises(CommandExecutionError):
            win_wua.get_windows_update_log()


def test_get_windows_update_log_missing_output_file_raises(tmp_path, monkeypatch):
    monkeypatch.setattr("tempfile.gettempdir", lambda: str(tmp_path))
    missing_path = tmp_path / "never_written.log"

    with patch(
        "salt.utils.win_pwsh.run_dict",
        autospec=True,
        return_value={"Log": str(missing_path)},
    ):
        with pytest.raises(CommandExecutionError):
            win_wua.get_windows_update_log()


def test_get_windows_update_log_tail_and_pattern_share_helper(tmp_path, monkeypatch):
    monkeypatch.setattr("tempfile.gettempdir", lambda: str(tmp_path))
    log_path = tmp_path / "WindowsUpdate.log"
    lines = [
        "far away alpha",
        "still far",
        "also far",
        "Failed to sync",
        "still far 2",
        "also far 2",
        "far away beta",
    ]
    log_path.write_text("\n".join(lines), encoding="utf-8")

    with patch(
        "salt.utils.win_pwsh.run_dict",
        autospec=True,
        return_value={"Log": str(log_path)},
    ):
        result = win_wua.get_windows_update_log(pattern="Failed")

    assert "Failed to sync" in result
    assert "far away" not in result
