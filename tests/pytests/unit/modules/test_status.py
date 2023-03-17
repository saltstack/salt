import pytest

import salt.modules.status as status
from salt.exceptions import CommandExecutionError
from tests.support.mock import MagicMock, Mock, patch


@pytest.fixture
def configure_loader_modules():
    return {status: {}}


def test_boot_time_aix():
    mock = Mock()

    mock.return_value = {"stdout": "7-20:46:46", "retcode": 0}
    with patch.dict(status.__salt__, {"cmd.run_all": mock}):
        uptime = status._get_boot_time_aix()
        assert uptime == 679606

    mock.return_value = {"stdout": "20:46:46", "retcode": 0}
    with patch.dict(status.__salt__, {"cmd.run_all": mock}):
        uptime = status._get_boot_time_aix()
        assert uptime == 74806

    mock.return_value = {"stdout": "   01:32:37", "retcode": 0}
    with patch.dict(status.__salt__, {"cmd.run_all": mock}):
        uptime = status._get_boot_time_aix()
        assert uptime == 5557

    mock.return_value = {"stdout": "00:12", "retcode": 0}
    with patch.dict(status.__salt__, {"cmd.run_all": mock}):
        uptime = status._get_boot_time_aix()
        assert uptime == 12

    mock.return_value = {"stdout": "foo", "retcode": 0}
    with patch.dict(status.__salt__, {"cmd.run_all": mock}):
        with pytest.raises(CommandExecutionError):
            status._get_boot_time_aix()

    mock.return_value = {"stdout": "", "retcode": 1}
    with patch.dict(status.__salt__, {"cmd.run_all": mock}):
        with pytest.raises(CommandExecutionError):
            status._get_boot_time_aix()


def test_custom():
    mock = MagicMock()
    mock2 = MagicMock()

    mock.return_value = {
        "days": 2,
        "seconds": 249719,
        "since_iso": "2023-02-27T06:19:01.590002",
        "since_t": 1677478741,
        "time": "21:21",
        "users": 2,
    }
    # test pass correct info with correct config
    mock2.return_value = {"status.uptime.custom": ["days"]}
    with patch.dict(status.__salt__, {"config.dot_vals": mock2}):
        with patch.dict(status.__salt__, {"status.uptime": mock}):
            assert status.custom() == {"days": 2}

    # test pass correct info with incorrect config
    mock2.return_value = {"status.fail.custom": ["days"]}
    with patch.dict(status.__salt__, {"config.dot_vals": mock2}):
        with patch.dict(status.__salt__, {"status.uptime": mock}):
            assert status.custom() == {}

    # test incorrect info with correct config
    mock2.return_value = {"status.uptime.custom": ["day"]}
    with patch.dict(status.__salt__, {"config.dot_vals": mock2}):
        with patch.dict(status.__salt__, {"status.uptime": mock}):
            assert status.custom() == {"day": "UNKNOWN"}
