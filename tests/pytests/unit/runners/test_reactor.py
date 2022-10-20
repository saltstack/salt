"""
unit tests for the reactor runner
"""


import logging

import pytest

import salt.runners.reactor as reactor
from salt.exceptions import CommandExecutionError
from salt.utils.event import SaltEvent
from tests.support.mock import MagicMock, patch

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


@pytest.fixture
def configure_loader_modules():
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


def test_list():
    """
    test reactor.list runner
    """
    with pytest.raises(CommandExecutionError) as excinfo:
        ret = reactor.list_()
    assert excinfo.value.error == "Reactor system is not running."

    mock_opts = {}
    mock_opts = {"engines": []}
    with patch.dict(reactor.__opts__, mock_opts):
        with pytest.raises(CommandExecutionError) as excinfo:
            ret = reactor.list_()
        assert excinfo.value.error == "Reactor system is not running."

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
                assert {"test_event/*": ["/srv/reactors/reactor.sls"]} in ret

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
                assert {"test_event/*": ["/srv/reactors/reactor.sls"]} in ret


def test_add():
    """
    test reactor.add runner
    """
    with pytest.raises(CommandExecutionError) as excinfo:
        ret = reactor.add(
            "salt/cloud/*/destroyed", reactors="/srv/reactor/destroy/*.sls"
        )
    assert excinfo.value.error == "Reactor system is not running."

    mock_opts = {}
    mock_opts = {"engines": []}
    with patch.dict(reactor.__opts__, mock_opts):
        with pytest.raises(CommandExecutionError) as excinfo:
            ret = reactor.add(
                "salt/cloud/*/destroyed", reactors="/srv/reactor/destroy/*.sls"
            )
        assert excinfo.value.error == "Reactor system is not running."

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
                assert "status" in ret
                assert ret["status"]
                assert "Reactor added." == ret["comment"]

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


def test_delete():
    """
    test reactor.delete runner
    """
    with pytest.raises(CommandExecutionError) as excinfo:
        ret = reactor.delete("salt/cloud/*/destroyed")
    assert excinfo.value.error == "Reactor system is not running."

    mock_opts = {}
    mock_opts = {"engines": []}
    with patch.dict(reactor.__opts__, mock_opts):
        with pytest.raises(CommandExecutionError) as excinfo:
            ret = reactor.delete("salt/cloud/*/destroyed")
        assert excinfo.value.error == "Reactor system is not running."

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
                assert "status" in ret
                assert ret["status"]
                assert "Reactor deleted." == ret["comment"]

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


def test_is_leader():
    """
    test reactor.is_leader runner
    """
    with pytest.raises(CommandExecutionError) as excinfo:
        ret = reactor.is_leader()
    assert excinfo.value.error == "Reactor system is not running."

    mock_opts = {}
    mock_opts = {"engines": []}
    with patch.dict(reactor.__opts__, mock_opts):
        with pytest.raises(CommandExecutionError) as excinfo:
            ret = reactor.is_leader()
        assert excinfo.value.error == "Reactor system is not running."

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
                assert ret


def test_set_leader():
    """
    test reactor.set_leader runner
    """
    with pytest.raises(CommandExecutionError) as excinfo:
        ret = reactor.set_leader()
    assert excinfo.value.error == "Reactor system is not running."

    mock_opts = {}
    mock_opts = {"engines": []}
    with patch.dict(reactor.__opts__, mock_opts):
        with pytest.raises(CommandExecutionError) as excinfo:
            ret = reactor.set_leader()
        assert excinfo.value.error == "Reactor system is not running."

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
                assert ret
