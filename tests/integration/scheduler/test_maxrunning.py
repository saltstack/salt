# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import

import copy
import logging
import os

import dateutil.parser as dateutil_parser

# Import Salt libs
import salt.utils.schedule
from salt.modules.test import ping

# Import Salt Testing libs
from tests.support.case import ModuleCase
from tests.support.mixins import SaltReturnAssertsMixin
from tests.support.mock import MagicMock, patch
from tests.support.runtests import RUNTIME_VARS

try:
    import croniter  # pylint: disable=W0611

    HAS_CRONITER = True
except ImportError:
    HAS_CRONITER = False

log = logging.getLogger(__name__)
ROOT_DIR = os.path.join(RUNTIME_VARS.TMP, "schedule-unit-tests")
SOCK_DIR = os.path.join(ROOT_DIR, "test-socks")

DEFAULT_CONFIG = salt.config.minion_config(None)
DEFAULT_CONFIG["conf_dir"] = ROOT_DIR
DEFAULT_CONFIG["root_dir"] = ROOT_DIR
DEFAULT_CONFIG["sock_dir"] = SOCK_DIR
DEFAULT_CONFIG["pki_dir"] = os.path.join(ROOT_DIR, "pki")
DEFAULT_CONFIG["cachedir"] = os.path.join(ROOT_DIR, "cache")


class SchedulerMaxRunningTest(ModuleCase, SaltReturnAssertsMixin):
    """
    Validate the pkg module
    """

    def setUp(self):
        with patch("salt.utils.schedule.clean_proc_dir", MagicMock(return_value=None)):
            functions = {"test.ping": ping}
            self.schedule = salt.utils.schedule.Schedule(
                copy.deepcopy(DEFAULT_CONFIG), functions, returners={}
            )
        self.schedule.opts["loop_interval"] = 1

    def tearDown(self):
        self.schedule.reset()

    def test_maxrunning_minion(self):
        """
        verify that scheduled job runs
        """
        self.schedule.opts["__role"] = "minion"

        job = {
            "schedule": {
                "maxrunning_minion": {
                    "function": "test.ping",
                    "seconds": 10,
                    "maxrunning": 1,
                }
            }
        }

        job_data = {
            "function": "test.ping",
            "run": True,
            "name": "maxrunning_minion",
            "seconds": 10,
            "_seconds": 10,
            "jid_include": True,
            "maxrunning": 1,
        }

        # Add the job to the scheduler
        self.schedule.opts.update(job)

        running_data = [
            {
                "fun_args": [],
                "jid": "20181018165923360935",
                "schedule": "maxrunning_minion",
                "pid": 15338,
                "fun": "test.ping",
                "id": "host",
            }
        ]

        run_time = dateutil_parser.parse("11/29/2017 4:00pm")

        with patch("salt.utils.minion.running", MagicMock(return_value=running_data)):
            with patch(
                "salt.utils.process.os_is_running", MagicMock(return_value=True)
            ):
                ret = self.schedule._check_max_running(
                    "test.ping", job_data, self.schedule.opts, now=run_time
                )
        self.assertIn("_skip_reason", ret)
        self.assertEqual("maxrunning", ret["_skip_reason"])
        self.assertEqual(False, ret["run"])

    def test_maxrunning_master(self):
        """
        verify that scheduled job runs
        """
        self.schedule.opts["__role"] = "master"

        job = {
            "schedule": {
                "maxrunning_master": {
                    "function": "state.orch",
                    "args": ["test.orch_test"],
                    "minutes": 1,
                    "maxrunning": 1,
                }
            }
        }

        job_data = {
            "function": "state.orch",
            "fun_args": ["test.orch_test"],
            "run": True,
            "name": "maxrunning_master",
            "minutes": 1,
            "jid_include": True,
            "maxrunning": 1,
        }

        # Add the job to the scheduler
        self.schedule.opts.update(job)

        running_data = [
            {
                "fun_args": ["test.orch_test"],
                "jid": "20181018165923360935",
                "schedule": "maxrunning_master",
                "pid": 15338,
                "fun": "state.orch",
                "id": "host",
            }
        ]

        run_time = dateutil_parser.parse("11/29/2017 4:00pm")

        with patch(
            "salt.utils.master.get_running_jobs", MagicMock(return_value=running_data)
        ):
            with patch(
                "salt.utils.process.os_is_running", MagicMock(return_value=True)
            ):
                ret = self.schedule._check_max_running(
                    "state.orch", job_data, self.schedule.opts, now=run_time
                )
        self.assertIn("_skip_reason", ret)
        self.assertEqual("maxrunning", ret["_skip_reason"])
        self.assertEqual(False, ret["run"])
