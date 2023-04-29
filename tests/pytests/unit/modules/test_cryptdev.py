import pytest

import salt.modules.cryptdev as cryptdev
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules(minion_opts):
    return {cryptdev: {"__opts__": minion_opts}}


def test_active(caplog):
    with patch.dict(
        cryptdev.__salt__,
        {"cmd.run_stdout": MagicMock(return_value="my-device       (253, 1)\n")},
    ):
        assert cryptdev.active() == {
            "my-device": {
                "devname": "my-device",
                "major": "253",
                "minor": "1",
            }
        }

    # debien output when no devices setup.
    with patch.dict(cryptdev.__salt__, {"cmd.run_stdout": MagicMock(return_value="")}):
        caplog.clear()
        assert cryptdev.active() == {}
        assert "dmsetup output does not match expected format" in caplog.text

    # centos output of dmsetup when no devices setup.
    with patch.dict(
        cryptdev.__salt__,
        {"cmd.run_stdout": MagicMock(return_value="No devices found")},
    ):
        caplog.clear()
        assert cryptdev.active() == {}
        assert "dmsetup output does not match expected format" in caplog.text
