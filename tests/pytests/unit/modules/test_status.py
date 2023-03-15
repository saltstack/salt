import pytest

import salt.modules.status as status
from salt.exceptions import CommandExecutionError
from tests.support.mock import Mock, patch


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
