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


@pytest.fixture(scope="function")
def setup_teardown_vars():
    log.debug("=== running setup_teardown_vars ===")
    try:

        subprocess_list = SubprocessList()

        with pytest.helpers.temp_directory() as tempdir:
            root_dir = os.path.join(tempdir, "schedule-unit-tests")
            sock_dir = os.path.join(root_dir, "test-socks")

            default_config = salt.config.minion_config(None)
            default_config["conf_dir"] = root_dir
            default_config["root_dir"] = root_dir
            default_config["sock_dir"] = sock_dir
            default_config["pki_dir"] = os.path.join(root_dir, "pki")
            default_config["cachedir"] = os.path.join(root_dir, "cache")

        with patch("salt.utils.schedule.clean_proc_dir", MagicMock(return_value=None)):
            functions = {"test.ping": ping}
            schedule = salt.utils.schedule.Schedule(
                copy.deepcopy(default_config),
                functions,
                returners={},
                new_instance=True,
            )

        schedule.opts["loop_interval"] = 1
        schedule._subprocess_list = subprocess_list

        yield {"schedule": schedule}

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
