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

log = logging.getLogger(__name__)
ROOT_DIR = os.path.join(RUNTIME_VARS.TMP, "schedule-unit-tests")
SOCK_DIR = os.path.join(ROOT_DIR, "test-socks")

DEFAULT_CONFIG = salt.config.minion_config(None)
DEFAULT_CONFIG["conf_dir"] = ROOT_DIR
DEFAULT_CONFIG["root_dir"] = ROOT_DIR
DEFAULT_CONFIG["sock_dir"] = SOCK_DIR
DEFAULT_CONFIG["pki_dir"] = os.path.join(ROOT_DIR, "pki")
DEFAULT_CONFIG["cachedir"] = os.path.join(ROOT_DIR, "cache")


class SchedulerSkipTest(ModuleCase, SaltReturnAssertsMixin):
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

    def test_skip(self):
        """
        verify that scheduled job is skipped at the specified time
        """
        job_name = "test_skip"
        job = {
            "schedule": {
                job_name: {
                    "function": "test.ping",
                    "when": ["11/29/2017 4pm", "11/29/2017 5pm"],
                }
            }
        }

        # Add job to schedule
        self.schedule.opts.update(job)

        run_time = dateutil_parser.parse("11/29/2017 4:00pm")
        self.schedule.skip_job(
            job_name,
            {
                "time": run_time.strftime("%Y-%m-%dT%H:%M:%S"),
                "time_fmt": "%Y-%m-%dT%H:%M:%S",
            },
        )

        # Run 11/29/2017 at 4pm
        self.schedule.eval(now=run_time)
        ret = self.schedule.job_status(job_name)
        self.assertNotIn("_last_run", ret)
        self.assertEqual(ret["_skip_reason"], "skip_explicit")
        self.assertEqual(ret["_skipped_time"], run_time)

        # Run 11/29/2017 at 5pm
        run_time = dateutil_parser.parse("11/29/2017 5:00pm")
        self.schedule.eval(now=run_time)
        ret = self.schedule.job_status(job_name)
        self.assertEqual(ret["_last_run"], run_time)

    def test_skip_during_range(self):
        """
        verify that scheduled job is skipped during the specified range
        """
        job_name = "test_skip_during_range"
        job = {
            "schedule": {
                job_name: {
                    "function": "test.ping",
                    "hours": "1",
                    "skip_during_range": {
                        "start": "11/29/2017 2pm",
                        "end": "11/29/2017 3pm",
                    },
                }
            }
        }

        # Add job to schedule
        self.schedule.opts.update(job)

        # eval at 1:30pm to prime.
        run_time = dateutil_parser.parse("11/29/2017 1:30pm")
        self.schedule.eval(now=run_time)
        ret = self.schedule.job_status(job_name)

        # eval at 2:30pm, will not run during range.
        run_time = dateutil_parser.parse("11/29/2017 2:30pm")
        self.schedule.eval(now=run_time)
        ret = self.schedule.job_status(job_name)
        self.assertNotIn("_last_run", ret)
        self.assertEqual(ret["_skip_reason"], "in_skip_range")
        self.assertEqual(ret["_skipped_time"], run_time)

        # eval at 3:30pm, will run.
        run_time = dateutil_parser.parse("11/29/2017 3:30pm")
        self.schedule.eval(now=run_time)
        ret = self.schedule.job_status(job_name)
        self.assertEqual(ret["_last_run"], run_time)

    def test_skip_during_range_invalid_datestring(self):
        """
        verify that scheduled job is not not and returns the right error string
        """
        run_time = dateutil_parser.parse("11/29/2017 2:30pm")

        job_name1 = "skip_during_range_invalid_datestring1"
        job1 = {
            "schedule": {
                job_name1: {
                    "function": "test.ping",
                    "hours": "1",
                    "_next_fire_time": run_time,
                    "skip_during_range": {"start": "25pm", "end": "3pm"},
                }
            }
        }

        job_name2 = "skip_during_range_invalid_datestring2"
        job2 = {
            "schedule": {
                job_name2: {
                    "function": "test.ping",
                    "hours": "1",
                    "_next_fire_time": run_time,
                    "skip_during_range": {"start": "2pm", "end": "25pm"},
                }
            }
        }

        # Add job1 to schedule
        self.schedule.opts.update(job1)

        # Eval
        self.schedule.eval(now=run_time)

        # Check the first job
        ret = self.schedule.job_status(job_name1)
        _expected = (
            "Invalid date string for start in "
            "skip_during_range. Ignoring "
            "job {0}."
        ).format(job_name1)
        self.assertEqual(ret["_error"], _expected)

        # Clear out schedule
        self.schedule.opts["schedule"] = {}

        # Add job2 to schedule
        self.schedule.opts.update(job2)

        # Eval
        self.schedule.eval(now=run_time)

        # Check the second job
        ret = self.schedule.job_status(job_name2)
        _expected = (
            "Invalid date string for end in " "skip_during_range. Ignoring " "job {0}."
        ).format(job_name2)
        self.assertEqual(ret["_error"], _expected)

    def test_skip_during_range_global(self):
        """
        verify that scheduled job is skipped during the specified range
        """
        job_name = "skip_during_range_global"
        job = {
            "schedule": {
                "skip_during_range": {
                    "start": "11/29/2017 2:00pm",
                    "end": "11/29/2017 3:00pm",
                },
                job_name: {"function": "test.ping", "hours": "1"},
            }
        }

        # Add job to schedule
        self.schedule.opts.update(job)

        # eval at 1:30pm to prime.
        run_time = dateutil_parser.parse("11/29/2017 1:30pm")
        self.schedule.eval(now=run_time)
        ret = self.schedule.job_status(job_name)

        # eval at 2:30pm, will not run during range.
        run_time = dateutil_parser.parse("11/29/2017 2:30pm")
        self.schedule.eval(now=run_time)
        ret = self.schedule.job_status(job_name)
        self.assertNotIn("_last_run", ret)
        self.assertEqual(ret["_skip_reason"], "in_skip_range")
        self.assertEqual(ret["_skipped_time"], run_time)

        # eval at 3:30pm, will run.
        run_time = dateutil_parser.parse("11/29/2017 3:30pm")
        self.schedule.eval(now=run_time)
        ret = self.schedule.job_status(job_name)
        self.assertEqual(ret["_last_run"], run_time)

    def test_run_after_skip_range(self):
        """
        verify that scheduled job is skipped during the specified range
        """
        job_name = "skip_run_after_skip_range"
        job = {
            "schedule": {
                job_name: {
                    "function": "test.ping",
                    "when": "11/29/2017 2:30pm",
                    "run_after_skip_range": True,
                    "skip_during_range": {
                        "start": "11/29/2017 2pm",
                        "end": "11/29/2017 3pm",
                    },
                }
            }
        }

        # Add job to schedule
        self.schedule.opts.update(job)

        # eval at 2:30pm, will not run during range.
        run_time = dateutil_parser.parse("11/29/2017 2:30pm")
        self.schedule.eval(now=run_time)
        ret = self.schedule.job_status(job_name)
        self.assertNotIn("_last_run", ret)
        self.assertEqual(ret["_skip_reason"], "in_skip_range")
        self.assertEqual(ret["_skipped_time"], run_time)

        # eval at 3:00:01pm, will run.
        run_time = dateutil_parser.parse("11/29/2017 3:00:01pm")
        self.schedule.eval(now=run_time)
        ret = self.schedule.job_status(job_name)
        self.assertEqual(ret["_last_run"], run_time)

    def test_run_seconds_skip(self):
        """
        verify that scheduled job is skipped during the specified range
        """
        job_name = "run_seconds_skip"
        job = {"schedule": {job_name: {"function": "test.ping", "seconds": "10"}}}

        # Add job to schedule
        self.schedule.opts.update(job)

        # eval at 2:00pm, to prime the scheduler
        run_time = dateutil_parser.parse("11/29/2017 2:00pm")
        self.schedule.eval(now=run_time)
        ret = self.schedule.job_status(job_name)

        # eval at 2:00:10pm
        run_time = dateutil_parser.parse("11/29/2017 2:00:10pm")
        self.schedule.eval(now=run_time)
        ret = self.schedule.job_status(job_name)

        # Skip at 2:00:20pm
        run_time = dateutil_parser.parse("11/29/2017 2:00:20pm")
        self.schedule.skip_job(
            job_name,
            {
                "time": run_time.strftime("%Y-%m-%dT%H:%M:%S"),
                "time_fmt": "%Y-%m-%dT%H:%M:%S",
            },
        )
        self.schedule.eval(now=run_time)
        ret = self.schedule.job_status(job_name)
        self.assertIn("_next_fire_time", ret)
        self.assertEqual(ret["_skip_reason"], "skip_explicit")
        self.assertEqual(ret["_skipped_time"], run_time)

        # Run at 2:00:30pm
        run_time = dateutil_parser.parse("11/29/2017 2:00:30pm")
        self.schedule.eval(now=run_time)
        ret = self.schedule.job_status(job_name)
        self.assertIn("_last_run", ret)
