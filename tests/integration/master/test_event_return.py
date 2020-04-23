# -*- coding: utf-8 -*-
"""
tests.integration.master.test_event_return
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    This test module is meant to cover the issue being fixed by:

        https://github.com/saltstack/salt/pull/54731
"""
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

import logging
import os
import shutil
import subprocess
import time

# Import 3rd-party libs
import pytest

# Import Salt libs
import salt.ext.six as six
from salt.utils.nb_popen import NonBlockingPopen

# Import Salt Testing libs
from tests.support.case import TestCase
from tests.support.cli_scripts import ScriptPathMixin
from tests.support.helpers import get_unused_localhost_port
from tests.support.mixins import AdaptedConfigurationTestCaseMixin
from tests.support.processes import terminate_process

log = logging.getLogger(__name__)


class TestEventReturn(AdaptedConfigurationTestCaseMixin, ScriptPathMixin, TestCase):
    @classmethod
    def setUpClass(cls):
        overrides = {
            "publish_port": get_unused_localhost_port(),
            "ret_port": get_unused_localhost_port(),
            "tcp_master_pub_port": get_unused_localhost_port(),
            "tcp_master_pull_port": get_unused_localhost_port(),
            "tcp_master_publish_pull": get_unused_localhost_port(),
            "tcp_master_workers": get_unused_localhost_port(),
            "runtests_conn_check_port": get_unused_localhost_port(),
            "runtests_log_port": get_unused_localhost_port(),
        }
        overrides["pytest_engine_port"] = overrides["runtests_conn_check_port"]
        temp_config = AdaptedConfigurationTestCaseMixin.get_temp_config(
            "master", **overrides
        )
        cls.root_dir = temp_config["root_dir"]
        cls.config_dir = os.path.dirname(temp_config["conf_file"])
        if temp_config["transport"] == "tcp":
            pytest.skip("Test only applicable to the ZMQ transport")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root_dir)
        cls.root_dir = cls.config_dir = None

    def test_master_startup(self):
        proc = NonBlockingPopen(
            [self.get_script_path("master"), "-c", self.config_dir, "-l", "info"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        out = six.b("")
        err = six.b("")

        # Testing this should never be longer than 1 minute
        max_time = time.time() + 60
        try:
            while True:
                if time.time() > max_time:
                    assert False, "Max timeout ocurred"
                time.sleep(0.5)
                _out = proc.recv()
                _err = proc.recv_err()
                if _out:
                    out += _out
                if _err:
                    err += _err

                if six.b("DeprecationWarning: object() takes no parameters") in out:
                    self.fail(
                        "'DeprecationWarning: object() takes no parameters' was seen in output"
                    )

                if six.b("TypeError: object() takes no parameters") in out:
                    self.fail(
                        "'TypeError: object() takes no parameters' was seen in output"
                    )

                if six.b("Setting up the master communication server") in out:
                    # We got past the place we need, stop the process
                    break

                if out is None and err is None:
                    break

                if proc.poll() is not None:
                    break
        finally:
            terminate_process(proc.pid, kill_children=True)
