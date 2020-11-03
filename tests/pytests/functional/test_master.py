"""
Test parts of salt/master.py
"""
import logging
import os
import time

import pytest  # pylint: disable=unused-import
import salt.config
import salt.master
from tests.support.helpers import slowTest

try:
    import psutil
    has_psutil = True
except ImportError:
    has_psutil = False


log = logging.getLogger(__name__)


@slowTest
def test_maintinence_memory_usage(tmpdir, check_time=300):
    opts = salt.config.master_config(os.path.join(tmpdir, "master"))
    opts["loop_interval"] = 1
    opts["schedule"] = {
        "test_job": {"function": "salt.cmd", "args": ["test.sleep", 1], "seconds": 1},
    }
    maint_proc = salt.master.Maintenance(opts)
    maint_proc.start()
    # Wait for two loop iterations since we'll naturally consume some memory
    # while initializing things.
    time.sleep(opts["loop_interval"] * 2)
    proc = psutil.Process(maint_proc.pid)
    first_mem_info = proc.memory_info()
    start = time.time()
    while time.time() - start < check_time:
        last_mem_info = proc.memory_info()
        log.debug(
            "Current RSS memory: %d vs Initial RSS memory: %d",
            last_mem_info.rss,
            first_mem_info.rss,
        )
        mem_diff = last_mem_info.rss - first_mem_info.rss
        if mem_diff > (first_mem_info.rss * 0.1):
            assert False, "Memory grew by 10%"
        time.sleep(1)
    proc.terminate()
    maint_proc.join()
