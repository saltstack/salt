"""
    tests.pytests.unit.beacons.test_ps
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    ps usage beacon test cases
"""
import pytest

import salt.beacons.ps as ps
from tests.support.mock import patch


class FakeProcess:
    def __init__(self, _name, pid):
        self._name = _name
        self.pid = pid

    def name(self):
        return self._name


@pytest.fixture
def configure_loader_modules():
    return {}


def test_non_list_config():
    config = {}

    ret = ps.validate(config)
    assert ret == (False, "Configuration for ps beacon must be a list.")


def test_empty_config():
    config = [{}]

    ret = ps.validate(config)
    assert ret == (False, "Configuration for ps beacon requires processes.")


def test_ps_running():
    with patch(
        "salt.utils.psutil_compat.process_iter", autospec=True, spec_set=True
    ) as mock_process_iter:
        mock_process_iter.return_value = [
            FakeProcess(_name="salt-master", pid=3),
            FakeProcess(_name="salt-minion", pid=4),
        ]
        config = [{"processes": {"salt-master": "running"}}]

        ret = ps.validate(config)
        assert ret == (True, "Valid beacon configuration")

        ret = ps.beacon(config)
        assert ret == [{"salt-master": "Running"}]


def test_ps_not_running():
    with patch(
        "salt.utils.psutil_compat.process_iter", autospec=True, spec_set=True
    ) as mock_process_iter:
        mock_process_iter.return_value = [
            FakeProcess(_name="salt-master", pid=3),
            FakeProcess(_name="salt-minion", pid=4),
        ]
        config = [{"processes": {"mysql": "stopped"}}]

        ret = ps.validate(config)
        assert ret == (True, "Valid beacon configuration")

        ret = ps.beacon(config)
        assert ret == [{"mysql": "Stopped"}]
