"""
    tests.unit.utils.scheduler.base
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
"""

import copy
import logging

import pytest
from pytestshellutils.utils.processes import terminate_process

import salt.utils.platform
import salt.utils.schedule
from salt.modules.test import ping
from salt.utils.process import SubprocessList
from tests.support.mock import MagicMock, patch

log = logging.getLogger(__name__)


@pytest.fixture(scope="function")
def schedule(tmp_path):
    subprocess_list = None
    try:

        subprocess_list = SubprocessList()

        root_dir = tmp_path / "schedule-unit-tests"
        sock_dir = str(root_dir / "test-socks")

        default_config = salt.config.minion_config(None)
        default_config["conf_dir"] = str(root_dir)
        default_config["root_dir"] = str(root_dir)
        default_config["sock_dir"] = sock_dir
        default_config["pki_dir"] = str(root_dir / "pki")
        default_config["cachedir"] = str(root_dir / "cache")

        with patch("salt.utils.schedule.clean_proc_dir", MagicMock(return_value=None)):
            functions = {"test.ping": ping}
            _schedule = salt.utils.schedule.Schedule(
                copy.deepcopy(default_config),
                functions,
                returners={},
                new_instance=True,
            )

        _schedule.opts["loop_interval"] = 1
        _schedule._subprocess_list = subprocess_list

        yield _schedule

    finally:
        if subprocess_list:
            processes = subprocess_list.processes
            _schedule.reset()
            del _schedule
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
