"""
unit tests for the reactor runner
"""


import logging

import salt.runners.reactor as reactor
from salt.exceptions import CommandExecutionError
from salt.utils.event import SaltEvent
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase

log = logging.getLogger(__name__)


class MockEvent:
    """
    Mock event class
    """

    flag = None

    def __init__(self):
        self.full = None

    def get_event(self, wait, tag):
        """
        Mock get_event method
        """
        data = []
        return {"tag": tag, "data": data}

    def fire_event(self, data, tag):
        """
        Mock get_event method
        """
        return {"tag": tag, "data": data}


class ReactorTest(TestCase, LoaderModuleMockMixin):
    """
    Validate the reactor runner
    """

    def setup_loader_modules(self):
        return {
            reactor: {
                "__opts__": {
                    "reactor": [],
                    "engines": [],
                    "id": "master_id",
                    "sock_dir": "/var/run/salt/master",
                    "transport": "zeromq",
                },
                "__jid_event__": MockEvent(),
            }
        }

    def test_list(self):
        """
        test reactor.list runner
        """
        with self.assertRaises(CommandExecutionError) as excinfo:
            ret = reactor.list_()
        self.assertEqual(excinfo.exception.strerror, "Reactor system is not running.")

        mock_opts = {}
        mock_opts = {"engines": []}
        with patch.dict(reactor.__opts__, mock_opts):
            with self.assertRaises(CommandExecutionError) as excinfo:
                ret = reactor.list_()
            self.assertEqual(
                excinfo.exception.strerror, "Reactor system is not running."
            )

        mock_opts = {}
        mock_opts["engines"] = [
            {
                "reactor": {
                    "refresh_interval": 60,
                    "worker_threads": 10,
                    "worker_hwm": 10000,
                }
            }
        ]
        event_returns = {
            "reactors": [{"test_event/*": ["/srv/reactors/reactor.sls"]}],
            "_stamp": "2020-09-04T16:51:52.577711",
        }

        with patch.dict(reactor.__opts__, mock_opts):
            with patch.object(SaltEvent, "get_event", return_value=event_returns):
                with patch("salt.utils.master.get_master_key") as get_master_key:
                    get_master_key.retun_value = MagicMock(retun_value="master_key")
                    ret = reactor.list_()
                    self.assertIn({"test_event/*": ["/srv/reactors/reactor.sls"]}, ret)

        event_returns = {
            "_stamp": "2020-09-04T16:51:52.577711",
        }

        with patch.dict(reactor.__opts__, mock_opts):
            with patch.object(SaltEvent, "get_event", return_value=event_returns):
                with patch("salt.utils.master.get_master_key") as get_master_key:
                    get_master_key.retun_value = MagicMock(retun_value="master_key")
                    ret = reactor.list_()
                    assert ret is None

        mock_opts = {}
        mock_opts["reactor"] = [{"test_event/*": ["/srv/reactors/reactor.sls"]}]
        with patch.dict(reactor.__opts__, mock_opts):
            with patch.dict(reactor.__opts__, mock_opts):
                event_returns = {
                    "reactors": [{"test_event/*": ["/srv/reactors/reactor.sls"]}],
                    "_stamp": "2020-09-04T16:51:52.577711",
                }

            with patch.object(SaltEvent, "get_event", return_value=event_returns):
                with patch("salt.utils.master.get_master_key") as get_master_key:
                    get_master_key.retun_value = MagicMock(retun_value="master_key")
                    ret = reactor.list_()
                    self.assertIn({"test_event/*": ["/srv/reactors/reactor.sls"]}, ret)

    def test_add(self):
        """
        test reactor.add runner
        """
        with self.assertRaises(CommandExecutionError) as excinfo:
            ret = reactor.add(
                "salt/cloud/*/destroyed", reactors="/srv/reactor/destroy/*.sls"
            )
        self.assertEqual(excinfo.exception.strerror, "Reactor system is not running.")

        mock_opts = {}
        mock_opts = {"engines": []}
        with patch.dict(reactor.__opts__, mock_opts):
            with self.assertRaises(CommandExecutionError) as excinfo:
                ret = reactor.add(
                    "salt/cloud/*/destroyed", reactors="/srv/reactor/destroy/*.sls"
                )
            self.assertEqual(
                excinfo.exception.strerror, "Reactor system is not running."
            )

        mock_opts = {}
        mock_opts["engines"] = [
            {
                "reactor": {
                    "refresh_interval": 60,
                    "worker_threads": 10,
                    "worker_hwm": 10000,
                }
            }
        ]

        event_returns = {
            "reactors": [{"test_event/*": ["/srv/reactors/reactor.sls"]}],
            "result": {"status": True, "comment": "Reactor added."},
            "_stamp": "2020-09-04T17:45:33.206408",
        }

        with patch.dict(reactor.__opts__, mock_opts):
            with patch.object(SaltEvent, "get_event", return_value=event_returns):
                with patch("salt.utils.master.get_master_key") as get_master_key:
                    get_master_key.retun_value = MagicMock(retun_value="master_key")
                    ret = reactor.add("test_event/*", "/srv/reactor/reactor.sls")
                    self.assertIn("status", ret)
                    self.assertTrue(ret["status"])
                    self.assertEqual("Reactor added.", ret["comment"])

        event_returns = {
            "reactors": [{"test_event/*": ["/srv/reactors/reactor.sls"]}],
            "_stamp": "2020-09-04T17:45:33.206408",
        }

        with patch.dict(reactor.__opts__, mock_opts):
            with patch.object(SaltEvent, "get_event", return_value=event_returns):
                with patch("salt.utils.master.get_master_key") as get_master_key:
                    get_master_key.retun_value = MagicMock(retun_value="master_key")
                    ret = reactor.add("test_event/*", "/srv/reactor/reactor.sls")
                    assert ret is None

    def test_delete(self):
        """
        test reactor.delete runner
        """
        with self.assertRaises(CommandExecutionError) as excinfo:
            ret = reactor.delete("salt/cloud/*/destroyed")
        self.assertEqual(excinfo.exception.strerror, "Reactor system is not running.")

        mock_opts = {}
        mock_opts = {"engines": []}
        with patch.dict(reactor.__opts__, mock_opts):
            with self.assertRaises(CommandExecutionError) as excinfo:
                ret = reactor.delete("salt/cloud/*/destroyed")
            self.assertEqual(
                excinfo.exception.strerror, "Reactor system is not running."
            )

        mock_opts = {}
        mock_opts["engines"] = [
            {
                "reactor": {
                    "refresh_interval": 60,
                    "worker_threads": 10,
                    "worker_hwm": 10000,
                }
            }
        ]

        event_returns = {
            "reactors": [{"bot/*": ["/srv/reactors/bot.sls"]}],
            "result": {"status": True, "comment": "Reactor deleted."},
            "_stamp": "2020-09-04T18:15:41.586552",
        }

        with patch.dict(reactor.__opts__, mock_opts):
            with patch.object(SaltEvent, "get_event", return_value=event_returns):
                with patch("salt.utils.master.get_master_key") as get_master_key:
                    get_master_key.retun_value = MagicMock(retun_value="master_key")
                    ret = reactor.delete("test_event/*")
                    self.assertIn("status", ret)
                    self.assertTrue(ret["status"])
                    self.assertEqual("Reactor deleted.", ret["comment"])

        event_returns = {
            "reactors": [{"bot/*": ["/srv/reactors/bot.sls"]}],
            "_stamp": "2020-09-04T18:15:41.586552",
        }

        with patch.dict(reactor.__opts__, mock_opts):
            with patch.object(SaltEvent, "get_event", return_value=event_returns):
                with patch("salt.utils.master.get_master_key") as get_master_key:
                    get_master_key.retun_value = MagicMock(retun_value="master_key")
                    ret = reactor.delete("test_event/*")
                    assert ret is None

    def test_is_leader(self):
        """
        test reactor.is_leader runner
        """
        with self.assertRaises(CommandExecutionError) as excinfo:
            ret = reactor.is_leader()
        self.assertEqual(excinfo.exception.strerror, "Reactor system is not running.")

        mock_opts = {}
        mock_opts = {"engines": []}
        with patch.dict(reactor.__opts__, mock_opts):
            with self.assertRaises(CommandExecutionError) as excinfo:
                ret = reactor.is_leader()
            self.assertEqual(
                excinfo.exception.strerror, "Reactor system is not running."
            )

        mock_opts = {}
        mock_opts["engines"] = [
            {
                "reactor": {
                    "refresh_interval": 60,
                    "worker_threads": 10,
                    "worker_hwm": 10000,
                }
            }
        ]

        event_returns = {"result": True, "_stamp": "2020-09-04T18:32:10.004490"}

        with patch.dict(reactor.__opts__, mock_opts):
            with patch.object(SaltEvent, "get_event", return_value=event_returns):
                with patch("salt.utils.master.get_master_key") as get_master_key:
                    get_master_key.retun_value = MagicMock(retun_value="master_key")
                    ret = reactor.is_leader()
                    self.assertTrue(ret)

    def test_set_leader(self):
        """
        test reactor.set_leader runner
        """
        with self.assertRaises(CommandExecutionError) as excinfo:
            ret = reactor.set_leader()
        self.assertEqual(excinfo.exception.strerror, "Reactor system is not running.")

        mock_opts = {}
        mock_opts = {"engines": []}
        with patch.dict(reactor.__opts__, mock_opts):
            with self.assertRaises(CommandExecutionError) as excinfo:
                ret = reactor.set_leader()
            self.assertEqual(
                excinfo.exception.strerror, "Reactor system is not running."
            )

        mock_opts = {}
        mock_opts["engines"] = [
            {
                "reactor": {
                    "refresh_interval": 60,
                    "worker_threads": 10,
                    "worker_hwm": 10000,
                }
            }
        ]

        event_returns = {"result": True, "_stamp": "2020-09-04T18:32:10.004490"}

        with patch.dict(reactor.__opts__, mock_opts):
            with patch.object(SaltEvent, "get_event", return_value=event_returns):
                with patch("salt.utils.master.get_master_key") as get_master_key:
                    get_master_key.retun_value = MagicMock(retun_value="master_key")
                    ret = reactor.set_leader()
                    self.assertTrue(ret)
