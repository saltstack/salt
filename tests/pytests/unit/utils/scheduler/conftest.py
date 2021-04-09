"""
    tests.unit.utils.scheduler.base
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
"""


import copy
import logging
import os

import pytest
import salt.utils.platform
import salt.utils.schedule
from salt.modules.test import ping
from salt.utils.process import SubprocessList
from saltfactories.utils.processes import terminate_process
from tests.support.mock import MagicMock, patch

log = logging.getLogger(__name__)


@pytest.fixture
def root_dir():
    with pytest.helpers.temp_directory() as tempdir:
        root_dir = os.path.join(tempdir, "schedule-unit-tests")
        return root_dir


@pytest.fixture
def sock_dir(root_dir):
    sock_dir = os.path.join(root_dir, "test-socks")
    return sock_dir


@pytest.fixture
def default_config(root_dir, sock_dir):
    default_config = salt.config.minion_config(None)
    default_config["conf_dir"] = root_dir
    default_config["root_dir"] = root_dir
    default_config["sock_dir"] = sock_dir
    default_config["pki_dir"] = os.path.join(root_dir, "pki")
    default_config["cachedir"] = os.path.join(root_dir, "cache")

    return default_config


@pytest.fixture
def subprocess_list():
    subprocess_list = SubprocessList()
    return subprocess_list


@pytest.fixture
def schedule(subprocess_list, default_config):
    with patch("salt.utils.schedule.clean_proc_dir", MagicMock(return_value=None)):
        functions = {"test.ping": ping}
        schedule = salt.utils.schedule.Schedule(
            copy.deepcopy(default_config), functions, returners={}, new_instance=True,
        )
    schedule._subprocess_list = subprocess_list
    return schedule


@pytest.fixture()
def loop_interval(schedule):
    schedule.opts["loop_interval"] = 1


@pytest.fixture(scope="function")
def setup_teardown_vars(subprocess_list):
    try:
        yield
    finally:
        processes = subprocess_list.processes
        schedule.reset()
        del schedule
        for proc in processes:
            if proc.is_alive():
                terminate_process(proc.pid, kill_children=True, slow_stop=True)
        subprocess_list.cleanup()
        processes = subprocess_list.processes
        if processes:
            for proc in processes:
                if proc.is_alive():
                    terminate_process(proc.pid, kill_children=True, slow_stop=False)
            subprocess_list.cleanup()
        processes = subprocess_list.processes
        if processes:
            log.warning("Processes left running: %s", processes)

        del default_config
        del subprocess_list
