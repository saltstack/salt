"""
    tests.pytests.unit.beacons.test_ps
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    ps usage beacon test cases
"""
from contextlib import contextmanager

import pytest

import salt.beacons.ps as ps
from tests.support.mock import patch


class FakeProcess:
    def __init__(self, _name, _username, _create_time, pid):
        self._name = _name
        self._username = _username
        self.pid = pid
        self._create_time = _create_time

    def name(self):
        return self._name

    def username(self):
        return self._username

    def create_time(self):
        return self._create_time

    @contextmanager
    def oneshot(self):
        yield (self.pid, self._username, self._create_time)


__accepted_statuses__ = ["sleeping", "idle", "running", "stopped"]


@pytest.fixture
def configure_loader_modules():
    return {}


def test_non_dict_config():
    config = []

    ret = ps.validate(config)
    assert ret == (
        False,
        "Configuration for ps beacon must be a dictionary with key 'processes' that contains a list.",
    )


def test_empty_config():
    config = {}

    ret = ps.validate(config)
    assert ret == (False, "Configuration for ps beacon requires processes.")


def test_ps_running():
    with patch(
        "salt.utils.psutil_compat.process_iter", autospec=True, spec_set=True
    ) as mock_process_iter:
        mock_process_iter.return_value = [
            FakeProcess(
                _name="salt-master",
                pid=3,
                _username="DOMAIN\\username1",
                _create_time=1307289803.47,
            ),
            FakeProcess(
                _name="salt-minion",
                pid=4,
                _username="DOMAIN\\username2",
                _create_time=1306289803.47,
            ),
        ]
        config = {"processes": [{"salt-master": {"status": "running"}}]}

        ret = ps.validate(config)
        assert ret == (True, "Valid beacon configuration")

        ret = ps.beacon(config)
        assert ret == [
            {
                "salt-master": {
                    "status": "running",
                    "instances": [(3, "DOMAIN\\username1", 1307289803.47)],
                }
            }
        ]


def test_ps_running_but_not_running():
    with patch(
        "salt.utils.psutil_compat.process_iter", autospec=True, spec_set=True
    ) as mock_process_iter:
        mock_process_iter.return_value = [
            FakeProcess(
                _name="salt-minion",
                pid=4,
                _username="DOMAIN\\username2",
                _create_time=1306289803.47,
            ),
        ]
        config = {"processes": [{"salt-master": {"status": "running"}}]}

        ret = ps.validate(config)
        assert ret == (True, "Valid beacon configuration")

        ret = ps.beacon(config)
        assert ret == []


def test_nultiple_ps_running():
    with patch(
        "salt.utils.psutil_compat.process_iter", autospec=True, spec_set=True
    ) as mock_process_iter:
        mock_process_iter.return_value = [
            FakeProcess(
                _name="salt-master",
                pid=3,
                _username="DOMAIN\\username1",
                _create_time=1307289803.47,
            ),
            FakeProcess(
                _name="salt-minion",
                pid=4,
                _username="DOMAIN\\username2",
                _create_time=1306289803.47,
            ),
        ]
        config = {
            "processes": [
                {"salt-master": {"status": "running"}},
                {"salt-minion": {"status": "running"}},
            ]
        }

        ret = ps.validate(config)
        assert ret == (True, "Valid beacon configuration")

        ret = ps.beacon(config)
        assert ret == [
            {
                "salt-master": {
                    "status": "running",
                    "instances": [(3, "DOMAIN\\username1", 1307289803.47)],
                }
            },
            {
                "salt-minion": {
                    "status": "running",
                    "instances": [(4, "DOMAIN\\username2", 1306289803.47)],
                },
            },
        ]


def test_nultiple_ps_running_but_not_running():
    with patch(
        "salt.utils.psutil_compat.process_iter", autospec=True, spec_set=True
    ) as mock_process_iter:
        mock_process_iter.return_value = [
            FakeProcess(
                _name="redis",
                pid=3,
                _username="DOMAIN\\username1",
                _create_time=1307289803.47,
            ),
            FakeProcess(
                _name="mysql",
                pid=4,
                _username="DOMAIN\\username2",
                _create_time=1306289803.47,
            ),
        ]
        config = {
            "processes": [
                {"salt-master": {"status": "running"}},
                {"salt-minion": {"status": "running"}},
            ]
        }

        ret = ps.validate(config)
        assert ret == (True, "Valid beacon configuration")

        ret = ps.beacon(config)
        assert ret == []


def test_nultiple_ps_select_by_username_running():
    with patch(
        "salt.utils.psutil_compat.process_iter", autospec=True, spec_set=True
    ) as mock_process_iter:
        mock_process_iter.return_value = [
            FakeProcess(
                _name="w3svc.exe",
                pid=3,
                _username="DOMAIN\\username1",
                _create_time=1307289803.47,
            ),
            FakeProcess(
                _name="w3svc.exe",
                pid=4,
                _username="DOMAIN\\username2",
                _create_time=1306289803.47,
            ),
            FakeProcess(
                _name="powershell.exe",
                pid=56,
                _username="DOMAIN\\username5",
                _create_time=1306269803.47,
            ),
        ]
        config = {
            "processes": [
                {"w3svc.exe": {"status": "running", "username": "DOMAIN\\username2"}},
                {"powershell.exe": {"status": "running"}},
            ]
        }

        ret = ps.validate(config)
        assert ret == (True, "Valid beacon configuration")

        ret = ps.beacon(config)
        assert ret == [
            {
                "powershell.exe": {
                    "status": "running",
                    "instances": [(56, "DOMAIN\\username5", 1306269803.47)],
                },
            },
            {
                "w3svc.exe": {
                    "status": "running",
                    "instances": [(4, "DOMAIN\\username2", 1306289803.47)],
                }
            },
        ]


def test_nultiple_instances_of_ps_running():
    with patch(
        "salt.utils.psutil_compat.process_iter", autospec=True, spec_set=True
    ) as mock_process_iter:
        mock_process_iter.return_value = [
            FakeProcess(
                _name="w3svc.exe",
                pid=3,
                _username="DOMAIN\\username1",
                _create_time=1307289803.47,
            ),
            FakeProcess(
                _name="w3svc.exe",
                pid=4,
                _username="DOMAIN\\username2",
                _create_time=1306289803.47,
            ),
            FakeProcess(
                _name="powershell.exe",
                pid=56,
                _username="DOMAIN\\username5",
                _create_time=1306269803.47,
            ),
        ]
        config = {
            "processes": [
                {"w3svc.exe": {"status": "running"}},
                {"powershell.exe": {"status": "running"}},
            ]
        }

        ret = ps.validate(config)
        assert ret == (True, "Valid beacon configuration")

        ret = ps.beacon(config)
        assert ret == [
            {
                "powershell.exe": {
                    "status": "running",
                    "instances": [(56, "DOMAIN\\username5", 1306269803.47)],
                },
            },
            {
                "w3svc.exe": {
                    "status": "running",
                    "instances": [
                        (3, "DOMAIN\\username1", 1307289803.47),
                        (4, "DOMAIN\\username2", 1306289803.47),
                    ],
                }
            },
        ]


def test_ps_not_running():
    with patch(
        "salt.utils.psutil_compat.process_iter", autospec=True, spec_set=True
    ) as mock_process_iter:
        mock_process_iter.return_value = [
            FakeProcess(
                _name="salt-master",
                pid=3,
                _username="DOMAIN\\username1",
                _create_time=1307289803.47,
            ),
            FakeProcess(
                _name="salt-minion",
                pid=4,
                _username="DOMAIN\\username2",
                _create_time=1306289803.47,
            ),
        ]
        config = {"processes": [{"mysql": {"status": "stopped"}}]}

        ret = ps.validate(config)
        assert ret == (True, "Valid beacon configuration")

        ret = ps.beacon(config)
        assert ret == [{"mysql": {"status": "stopped", "instances": []}}]


def test_multiple_ps_not_running():
    with patch(
        "salt.utils.psutil_compat.process_iter", autospec=True, spec_set=True
    ) as mock_process_iter:
        mock_process_iter.return_value = [
            FakeProcess(
                _name="salt-master",
                pid=3,
                _username="DOMAIN\\username1",
                _create_time=1307289803.47,
            ),
            FakeProcess(
                _name="salt-minion",
                pid=4,
                _username="DOMAIN\\username2",
                _create_time=1306289803.47,
            ),
        ]
        config = {
            "processes": [
                {"mysql": {"status": "stopped"}},
                {"redis": {"status": "stopped"}},
            ]
        }

        ret = ps.validate(config)
        assert ret == (True, "Valid beacon configuration")

        ret = ps.beacon(config)
        assert ret == [
            {"mysql": {"status": "stopped", "instances": []}},
            {"redis": {"status": "stopped", "instances": []}},
        ]


def test_ps_not_running_but_is_running():
    with patch(
        "salt.utils.psutil_compat.process_iter", autospec=True, spec_set=True
    ) as mock_process_iter:
        mock_process_iter.return_value = [
            FakeProcess(
                _name="redis",
                pid=45,
                _username="DOMAIN\\username2",
                _create_time=1304289803.47,
            ),
        ]
        config = {"processes": [{"redis": {"status": "stopped"}}]}

        ret = ps.validate(config)
        assert ret == (True, "Valid beacon configuration")

        ret = ps.beacon(config)
        assert ret == []


def test_invalid_status_config():
    config = {"processes": [{"mysql": {"status": "oop"}}]}

    ret = ps.validate(config)
    assert ret == (
        False,
        f"Status not supported, currently supported are {', '.join(__accepted_statuses__)}.",
    )
