import pytest

import salt.modules.systemd_service as systemd_service
import salt.utils.systemd
from tests.support.mock import MagicMock, patch

pytestmark = [
    pytest.mark.skip_unless_on_linux,
]


@pytest.fixture
def configure_loader_modules():
    return {systemd_service: {}}


@pytest.mark.parametrize(
    "service_name, expected",
    [
        ("salt-minion", True),
        ("salt-minion.service", True),
        ("other-service", False),
    ],
)
def test_salt_minion_service(service_name, expected):
    """
    Test the _salt_minion_service function to ensure it correctly identifies
    the salt-minion service name.
    """
    assert systemd_service._salt_minion_service(service_name) is expected


@pytest.mark.parametrize(
    "service_name, no_block, expected",
    [
        ("salt-minion", None, True),
        ("other-service", None, False),
        ("salt-minion", False, False),
        ("other-service", False, False),
        ("salt-minion", True, True),
        ("other-service", True, True),
    ],
)
def test_no_block_default(service_name, no_block, expected):
    """
    Test the _no_block_default function to ensure it returns the correct
    default value for the no_block argument based on the service name.
    """
    assert systemd_service._no_block_default(service_name, no_block) is expected


@pytest.mark.skipif(not salt.utils.systemd.booted(), reason="Requires systemd")
@pytest.mark.parametrize(
    "operation,expected_command",
    [
        ("restart", "restart"),
        ("stop", "stop"),
    ],
)
def test_operation_no_block_default(operation, expected_command, grains):
    """
    Test restart/stop functions to ensure they use the correct default value for
    no_block when operating on the salt-minion service.
    """

    if grains["osfinger"] == "Amazon Linux-2":
        pytest.skip("Amazon Linux 2 CI containers do not support systemd fully")

    mock_none = MagicMock(return_value=None)
    mock_true = MagicMock(return_value=True)
    mock_run_all_success = MagicMock(
        return_value={"retcode": 0, "stdout": "", "stderr": "", "pid": 12345}
    )

    with patch.dict(
        systemd_service.__salt__,
        {"cmd.run_all": mock_run_all_success, "config.get": mock_true},
    ) as mock_salt, patch.object(
        systemd_service, "_check_for_unit_changes", mock_none
    ), patch.object(
        systemd_service, "_check_unmask", mock_none
    ), patch(
        "salt.utils.path.which", lambda x: "/usr/bin/" + x
    ):
        # Get the function to test based on the operation parameter
        operation_func = getattr(systemd_service, operation)

        # Test salt-minion.service (should include --no-block)
        assert operation_func("salt-minion.service")
        mock_salt["cmd.run_all"].assert_called_with(
            [
                "/usr/bin/systemd-run",
                "--scope",
                "/usr/bin/systemctl",
                "--no-block",
                expected_command,
                "salt-minion.service",
            ],
            python_shell=False,
        )

        # Test other.service (should not include --no-block)
        assert operation_func("other.service")
        mock_salt["cmd.run_all"].assert_called_with(
            [
                "/usr/bin/systemd-run",
                "--scope",
                "/usr/bin/systemctl",
                expected_command,
                "other.service",
            ],
            python_shell=False,
        )
