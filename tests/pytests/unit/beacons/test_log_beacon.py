"""
    tests.pytests.unit.beacons.test_log_beacon
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    log beacon test cases
"""
import pytest

import salt.beacons.log_beacon as log_beacon
from tests.support.mock import mock_open, patch


@pytest.fixture
def configure_loader_modules():
    return {log_beacon: {"__context__": {"log.loc": 2}, "__salt__": {}}}


@pytest.fixture
def stub_log_entry():
    return (
        "Jun 29 12:58:51 hostname sshd[6536]: pam_unix(sshd:session): session opened"
        " for user username by (uid=0)\n"
    )


def test_non_list_config():
    config = {}

    ret = log_beacon.validate(config)
    assert ret == (False, "Configuration for log beacon must be a list.")


def test_empty_config():
    config = [{}]

    ret = log_beacon.validate(config)
    assert ret == (False, "Configuration for log beacon must contain file option.")


def test_log_match(stub_log_entry):
    with patch("salt.utils.files.fopen", mock_open(read_data=stub_log_entry)):
        config = [
            {"file": "/var/log/auth.log", "tags": {"sshd": {"regex": ".*sshd.*"}}}
        ]

        ret = log_beacon.validate(config)
        assert ret == (True, "Valid beacon configuration")

        _expected_return = [
            {
                "error": "",
                "match": "yes",
                "raw": stub_log_entry.rstrip("\n"),
                "tag": "sshd",
            }
        ]
        ret = log_beacon.beacon(config)
        assert ret == _expected_return
