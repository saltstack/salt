# -*- coding: utf-8 -*-
"""
    :codeauthor: Nicole Thomas <nicole@saltstack.com>
"""

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

import copy
import datetime
import logging
import os

# Import Salt Libs
import salt.config
from salt.utils.schedule import Schedule
from tests.support.mock import MagicMock, patch
from tests.support.runtests import RUNTIME_VARS

# Import Salt Testing Libs
from tests.support.unit import TestCase, skipIf

# pylint: disable=import-error,unused-import
try:
    import croniter

    _CRON_SUPPORTED = True
except ImportError:
    _CRON_SUPPORTED = False
# pylint: enable=import-error

log = logging.getLogger(__name__)


# pylint: disable=too-many-public-methods,invalid-name
class ScheduleTestCase(TestCase):
    """
    Unit tests for salt.utils.schedule module
    """

    @classmethod
    def setUpClass(cls):
        root_dir = os.path.join(RUNTIME_VARS.TMP, "schedule-unit-tests")
        default_config = salt.config.minion_config(None)
        default_config["conf_dir"] = default_config["root_dir"] = root_dir
        default_config["sock_dir"] = os.path.join(root_dir, "test-socks")
        default_config["pki_dir"] = os.path.join(root_dir, "pki")
        default_config["cachedir"] = os.path.join(root_dir, "cache")
        cls.default_config = default_config

    @classmethod
    def tearDownClass(cls):
        delattr(cls, "default_config")

    def setUp(self):
        with patch("salt.utils.schedule.clean_proc_dir", MagicMock(return_value=None)):
            self.schedule = Schedule(
                copy.deepcopy(self.default_config), {}, returners={}
            )
        self.addCleanup(delattr, self, "schedule")

    # delete_job tests

    def test_delete_job_exists(self):
        """
        Tests ensuring the job exists and deleting it
        """
        self.schedule.opts.update({"schedule": {"foo": "bar"}, "pillar": {}})
        self.assertIn("foo", self.schedule.opts["schedule"])
        self.schedule.delete_job("foo")
        self.assertNotIn("foo", self.schedule.opts["schedule"])

    def test_delete_job_in_pillar(self):
        """
        Tests ignoring deletion job from pillar
        """
        self.schedule.opts.update(
            {"pillar": {"schedule": {"foo": "bar"}}, "schedule": {}}
        )
        self.assertIn("foo", self.schedule.opts["pillar"]["schedule"])
        self.schedule.delete_job("foo")
        self.assertIn("foo", self.schedule.opts["pillar"]["schedule"])

    def test_delete_job_intervals(self):
        """
        Tests removing job from intervals
        """
        self.schedule.opts.update({"pillar": {}, "schedule": {}})
        self.schedule.intervals = {"foo": "bar"}
        self.schedule.delete_job("foo")
        self.assertNotIn("foo", self.schedule.intervals)

    def test_delete_job_prefix(self):
        """
        Tests ensuring jobs exists and deleting them by prefix
        """
        self.schedule.opts.update(
            {
                "schedule": {"foobar": "bar", "foobaz": "baz", "fooboo": "boo"},
                "pillar": {},
            }
        )
        ret = copy.deepcopy(self.schedule.opts)
        del ret["schedule"]["foobar"]
        del ret["schedule"]["foobaz"]
        self.schedule.delete_job_prefix("fooba")
        self.assertEqual(self.schedule.opts, ret)

    def test_delete_job_prefix_in_pillar(self):
        """
        Tests ignoring deletion jobs by prefix from pillar
        """
        self.schedule.opts.update(
            {
                "pillar": {
                    "schedule": {"foobar": "bar", "foobaz": "baz", "fooboo": "boo"}
                },
                "schedule": {},
            }
        )
        ret = copy.deepcopy(self.schedule.opts)
        self.schedule.delete_job_prefix("fooba")
        self.assertEqual(self.schedule.opts, ret)

    # add_job tests

    def test_add_job_data_not_dict(self):
        """
        Tests if data is a dictionary
        """
        data = "foo"
        self.assertRaises(ValueError, Schedule.add_job, self.schedule, data)

    def test_add_job_multiple_jobs(self):
        """
        Tests if more than one job is scheduled at a time
        """
        data = {"key1": "value1", "key2": "value2"}
        self.assertRaises(ValueError, Schedule.add_job, self.schedule, data)

    def test_add_job(self):
        """
        Tests adding a job to the schedule
        """
        data = {"foo": {"bar": "baz"}}
        ret = copy.deepcopy(self.schedule.opts)
        ret.update(
            {
                "schedule": {
                    "foo": {"bar": "baz", "enabled": True},
                    "hello": {"world": "peace", "enabled": True},
                },
                "pillar": {},
            }
        )
        self.schedule.opts.update(
            {"schedule": {"hello": {"world": "peace", "enabled": True}}, "pillar": {}}
        )
        Schedule.add_job(self.schedule, data)
        self.assertEqual(self.schedule.opts, ret)

    # enable_job tests

    def test_enable_job(self):
        """
        Tests enabling a job
        """
        self.schedule.opts.update({"schedule": {"name": {"enabled": "foo"}}})
        Schedule.enable_job(self.schedule, "name")
        self.assertTrue(self.schedule.opts["schedule"]["name"]["enabled"])

    def test_enable_job_pillar(self):
        """
        Tests ignoring enable a job from pillar
        """
        self.schedule.opts.update(
            {"pillar": {"schedule": {"name": {"enabled": False}}}}
        )
        Schedule.enable_job(self.schedule, "name", persist=False)
        self.assertFalse(self.schedule.opts["pillar"]["schedule"]["name"]["enabled"])

    # disable_job tests

    def test_disable_job(self):
        """
        Tests disabling a job
        """
        self.schedule.opts.update(
            {"schedule": {"name": {"enabled": "foo"}}, "pillar": {}}
        )
        Schedule.disable_job(self.schedule, "name")
        self.assertFalse(self.schedule.opts["schedule"]["name"]["enabled"])

    def test_disable_job_pillar(self):
        """
        Tests ignoring disable a job in pillar
        """
        self.schedule.opts.update(
            {"pillar": {"schedule": {"name": {"enabled": True}}}, "schedule": {}}
        )
        Schedule.disable_job(self.schedule, "name", persist=False)
        self.assertTrue(self.schedule.opts["pillar"]["schedule"]["name"]["enabled"])

    # modify_job tests

    def test_modify_job(self):
        """
        Tests modifying a job in the scheduler
        """
        schedule = {"foo": "bar"}
        self.schedule.opts.update({"schedule": {"name": "baz"}, "pillar": {}})
        ret = copy.deepcopy(self.schedule.opts)
        ret.update({"schedule": {"name": {"foo": "bar"}}})
        Schedule.modify_job(self.schedule, "name", schedule)
        self.assertEqual(self.schedule.opts, ret)

    def test_modify_job_not_exists(self):
        """
        Tests modifying a job in the scheduler if jobs not exists
        """
        schedule = {"foo": "bar"}
        self.schedule.opts.update({"schedule": {}, "pillar": {}})
        ret = copy.deepcopy(self.schedule.opts)
        ret.update({"schedule": {"name": {"foo": "bar"}}})
        Schedule.modify_job(self.schedule, "name", schedule)
        self.assertEqual(self.schedule.opts, ret)

    def test_modify_job_pillar(self):
        """
        Tests ignoring modification of job from pillar
        """
        schedule = {"foo": "bar"}
        self.schedule.opts.update(
            {"schedule": {}, "pillar": {"schedule": {"name": "baz"}}}
        )
        ret = copy.deepcopy(self.schedule.opts)
        Schedule.modify_job(self.schedule, "name", schedule, persist=False)
        self.assertEqual(self.schedule.opts, ret)

    maxDiff = None

    # enable_schedule tests

    def test_enable_schedule(self):
        """
        Tests enabling the scheduler
        """
        with patch(
            "salt.utils.schedule.Schedule.persist", MagicMock(return_value=None)
        ) as persist_mock:
            self.schedule.opts.update({"schedule": {"enabled": "foo"}, "pillar": {}})
            Schedule.enable_schedule(self.schedule)
            self.assertTrue(self.schedule.opts["schedule"]["enabled"])

        persist_mock.assert_called()

    # disable_schedule tests

    def test_disable_schedule(self):
        """
        Tests disabling the scheduler
        """
        with patch(
            "salt.utils.schedule.Schedule.persist", MagicMock(return_value=None)
        ) as persist_mock:
            self.schedule.opts.update({"schedule": {"enabled": "foo"}, "pillar": {}})
            Schedule.disable_schedule(self.schedule)
            self.assertFalse(self.schedule.opts["schedule"]["enabled"])

        persist_mock.assert_called()

    # reload tests

    def test_reload_update_schedule_key(self):
        """
        Tests reloading the schedule from saved schedule where both the
        saved schedule and self.schedule.opts contain a schedule key
        """
        saved = {"schedule": {"foo": "bar"}}
        ret = copy.deepcopy(self.schedule.opts)
        ret.update({"schedule": {"foo": "bar", "hello": "world"}})
        self.schedule.opts.update({"schedule": {"hello": "world"}})
        Schedule.reload(self.schedule, saved)
        self.assertEqual(self.schedule.opts, ret)

    def test_reload_update_schedule_no_key(self):
        """
        Tests reloading the schedule from saved schedule that does not
        contain a schedule key but self.schedule.opts does
        """
        saved = {"foo": "bar"}
        ret = copy.deepcopy(self.schedule.opts)
        ret.update({"schedule": {"foo": "bar", "hello": "world"}})
        self.schedule.opts.update({"schedule": {"hello": "world"}})
        Schedule.reload(self.schedule, saved)
        self.assertEqual(self.schedule.opts, ret)

    def test_reload_no_schedule_in_opts(self):
        """
        Tests reloading the schedule from saved schedule that does not
        contain a schedule key and neither does self.schedule.opts
        """
        saved = {"foo": "bar"}
        ret = copy.deepcopy(self.schedule.opts)
        ret["schedule"] = {"foo": "bar"}
        self.schedule.opts.pop("schedule", None)
        Schedule.reload(self.schedule, saved)
        self.assertEqual(self.schedule.opts, ret)

    def test_reload_schedule_in_saved_but_not_opts(self):
        """
        Tests reloading the schedule from saved schedule that contains
        a schedule key, but self.schedule.opts does not
        """
        saved = {"schedule": {"foo": "bar"}}
        ret = copy.deepcopy(self.schedule.opts)
        ret["schedule"] = {"foo": "bar"}
        self.schedule.opts.pop("schedule", None)
        Schedule.reload(self.schedule, saved)
        self.assertEqual(self.schedule.opts, ret)

    # eval tests

    def test_eval_schedule_is_not_dict(self):
        """
        Tests eval if the schedule is not a dictionary
        """
        self.schedule.opts.update({"schedule": "", "pillar": {"schedule": {}}})
        self.assertRaises(ValueError, Schedule.eval, self.schedule)

    def test_eval_schedule_is_not_dict_in_pillar(self):
        """
        Tests eval if the schedule from pillar is not a dictionary
        """
        self.schedule.opts.update({"schedule": {}, "pillar": {"schedule": ""}})
        self.assertRaises(ValueError, Schedule.eval, self.schedule)

    def test_eval_schedule_time(self):
        """
        Tests eval if the schedule setting time is in the future
        """
        self.schedule.opts.update({"pillar": {"schedule": {}}})
        self.schedule.opts.update(
            {"schedule": {"testjob": {"function": "test.true", "seconds": 60}}}
        )
        now = datetime.datetime.now()
        self.schedule.eval()
        self.assertTrue(
            self.schedule.opts["schedule"]["testjob"]["_next_fire_time"] > now
        )

    def test_eval_schedule_time_eval(self):
        """
        Tests eval if the schedule setting time is in the future plus splay
        """
        self.schedule.opts.update({"pillar": {"schedule": {}}})
        self.schedule.opts.update(
            {
                "schedule": {
                    "testjob": {"function": "test.true", "seconds": 60, "splay": 5}
                }
            }
        )
        now = datetime.datetime.now()
        self.schedule.eval()
        self.assertTrue(
            self.schedule.opts["schedule"]["testjob"]["_splay"] - now
            > datetime.timedelta(seconds=60)
        )

    @skipIf(not _CRON_SUPPORTED, "croniter module not installed")
    def test_eval_schedule_cron(self):
        """
        Tests eval if the schedule is defined with cron expression
        """
        self.schedule.opts.update({"pillar": {"schedule": {}}})
        self.schedule.opts.update(
            {"schedule": {"testjob": {"function": "test.true", "cron": "* * * * *"}}}
        )
        now = datetime.datetime.now()
        self.schedule.eval()
        self.assertTrue(
            self.schedule.opts["schedule"]["testjob"]["_next_fire_time"] > now
        )

    @skipIf(not _CRON_SUPPORTED, "croniter module not installed")
    def test_eval_schedule_cron_splay(self):
        """
        Tests eval if the schedule is defined with cron expression plus splay
        """
        self.schedule.opts.update({"pillar": {"schedule": {}}})
        self.schedule.opts.update(
            {
                "schedule": {
                    "testjob": {
                        "function": "test.true",
                        "cron": "* * * * *",
                        "splay": 5,
                    }
                }
            }
        )
        self.schedule.eval()
        self.assertTrue(
            self.schedule.opts["schedule"]["testjob"]["_splay"]
            > self.schedule.opts["schedule"]["testjob"]["_next_fire_time"]
        )

    def test_handle_func_schedule_minion_blackout(self):
        """
        Tests eval if the schedule from pillar is not a dictionary
        """
        self.schedule.opts.update({"pillar": {"schedule": {}}})
        self.schedule.opts.update({"grains": {"minion_blackout": True}})

        self.schedule.opts.update(
            {"schedule": {"testjob": {"function": "test.true", "seconds": 60}}}
        )
        data = {
            "function": "test.true",
            "_next_scheduled_fire_time": datetime.datetime(
                2018, 11, 21, 14, 9, 53, 903438
            ),
            "run": True,
            "name": "testjob",
            "seconds": 60,
            "_splay": None,
            "_seconds": 60,
            "jid_include": True,
            "maxrunning": 1,
            "_next_fire_time": datetime.datetime(2018, 11, 21, 14, 8, 53, 903438),
        }

        with patch.object(salt.utils.schedule, "log") as log_mock:
            with patch("salt.utils.process.daemonize"), patch("sys.platform", "linux2"):
                self.schedule.handle_func(False, "test.ping", data)
                self.assertTrue(log_mock.exception.called)
