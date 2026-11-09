"""
Tests for the SyndicManager and Syndic classes in minion.py
"""

import asyncio
import collections

import pytest

import salt.exceptions
import salt.minion
from tests.support.mock import MagicMock, call


def _syndic_manager(opts=None):
    if not opts:
        opts = {
            "conf_file": "conf/minion",
            "acceptance_wait_time": 10,
            "acceptance_wait_time_max": 20,
            "syndic_failover": "ordered",
            "syndic_retries": 3,
        }
    syndic_manager = salt.minion.SyndicManager(opts)
    syndic_manager._syndics = {
        "master1": MagicMock(),
        "master2": MagicMock(),
    }
    syndic_manager.pub_futures = {}
    return syndic_manager


def test_forward_events_return_pub_syndic_with_exception(caplog):
    """
    Test _return_pub_syndic when an exception is thrown 10 times.
    """
    syndic_manager = _syndic_manager()
    master1, master2 = "master1", "master2"
    tries = 0
    for _master in [master1, master2]:
        syndic_manager._syndics[_master].done.return_value = True
        syndic_manager._syndics[_master].exception.return_value = False

    syndic_manager.job_rets = {
        master1: {
            "salt/job/1234/ret/salt-minion": {
                "__fun__": "test.ping",
                "__jid__": "1234",
                "__load__": {"cmd": "publish", "tgt": "salt-minion"},
            }
        },
        master2: {
            "salt/job/5678/ret/salt-minion2": {
                "__fun__": "test.ping",
                "__jid__": "5678",
                "__load__": {"cmd": "publish", "tgt": "salt-minion2"},
            }
        },
    }
    syndic_manager._mark_master_dead = MagicMock()
    while tries < 10:
        for _master in [master1, master2]:
            syndic_manager.pub_futures[_master] = (
                MagicMock(side_effect=[salt.exceptions.SaltClientTimeout]),
                [4],
            )

        syndic_manager._forward_events()
        tries += 1

    assert caplog.text.count("Unable to call") == 5
    assert syndic_manager._mark_master_dead.call_args_list.count(call(master1)) == 3
    assert syndic_manager._mark_master_dead.call_args_list.count(call(master2)) == 2
    assert syndic_manager.tries == collections.defaultdict(int)
    assert syndic_manager._syndics[_master].result()._return_pub_multi.call_count == 1


def test_forward_events_return_pub_syndic_with_exception_once(caplog):
    """
    Test _return_pub_syndic when an exception is thrown 1 time.
    """
    syndic_manager = _syndic_manager()
    master1, master2 = "master1", "master2"
    tries = 0
    for _master in [master1, master2]:
        syndic_manager._syndics[_master].done.return_value = True
        syndic_manager._syndics[_master].exception.return_value = False
        syndic_manager._syndics[
            _master
        ].result.return_value.return_pub_multi.return_value = MagicMock()
    syndic_manager.pub_futures[master1] = (
        MagicMock(side_effect=[salt.exceptions.SaltClientTimeout]),
        [4],
    )

    syndic_manager.job_rets = {
        master1: {
            "salt/job/1234/ret/salt-minion": {
                "__fun__": "test.ping",
                "__jid__": "1234",
                "__load__": {"cmd": "publish", "tgt": "salt-minion"},
            }
        },
        master2: {
            "salt/job/5678/ret/salt-minion2": {
                "__fun__": "test.ping",
                "__jid__": "5678",
                "__load__": {"cmd": "publish", "tgt": "salt-minion2"},
            }
        },
    }

    mock_multi = MagicMock()
    mock_multi.done.return_value = True
    mock_multi.exception.return_value = False
    syndic_manager._mark_master_dead = MagicMock()
    while tries < 10:
        if tries >= 1:
            syndic_manager.pub_futures[master1] = (
                mock_multi,
                [4],
            )
        syndic_manager._forward_events()
        tries += 1

    # Only master1 fails (once). master2's first send succeeds and is stored as a
    # completed Future, so it is never marked dead.
    assert caplog.text.count("Unable to call") == 1
    assert syndic_manager._mark_master_dead.call_args_list.count(call(master1)) == 1
    assert syndic_manager._mark_master_dead.call_args_list.count(call(master2)) == 0
    assert syndic_manager.tries == collections.defaultdict(int)
    assert syndic_manager._syndics[master1].result()._return_pub_multi.call_count == 1
    assert syndic_manager._syndics[master2].result()._return_pub_multi.call_count == 2


def test_forward_events_return_pub_syndic_exception_syndic_retries_set(caplog):
    """
    Test _return_pub_syndic when an exception is thrown 10 times
    and syndic_retries is set to 5
    """
    opts = {
        "conf_file": "conf/minion",
        "acceptance_wait_time": 10,
        "acceptance_wait_time_max": 20,
        "syndic_failover": "ordered",
        "syndic_retries": 5,
    }

    syndic_manager = _syndic_manager(opts)
    master1, master2 = "master1", "master2"
    master1, master2 = "master1", "master2"
    tries = 0
    for _master in [master1, master2]:
        syndic_manager._syndics[_master].done.return_value = True
        syndic_manager._syndics[_master].exception.return_value = False

    syndic_manager.job_rets = {
        master1: {
            "salt/job/1234/ret/salt-minion": {
                "__fun__": "test.ping",
                "__jid__": "1234",
                "__load__": {"cmd": "publish", "tgt": "salt-minion"},
            }
        },
        master2: {
            "salt/job/5678/ret/salt-minion2": {
                "__fun__": "test.ping",
                "__jid__": "5678",
                "__load__": {"cmd": "publish", "tgt": "salt-minion2"},
            }
        },
    }
    syndic_manager._mark_master_dead = MagicMock()
    while tries < 10:
        for _master in [master1, master2]:
            syndic_manager.pub_futures[_master] = (
                MagicMock(side_effect=[salt.exceptions.SaltClientTimeout]),
                [4],
            )

        syndic_manager._forward_events()
        tries += 1

    assert caplog.text.count("Unable to call") == 9
    assert syndic_manager._mark_master_dead.call_args_list.count(call(master1)) == 5
    assert syndic_manager._mark_master_dead.call_args_list.count(call(master2)) == 4
    assert syndic_manager.tries == collections.defaultdict(int)
    assert syndic_manager._syndics[_master].result()._return_pub_multi.call_count == 1


def test_delayed_queue_prevents_memory_leak():
    """
    Test that self.delayed doesn't grow indefinitely when masters repeatedly fail
    """
    syndic_manager = _syndic_manager()

    syndic_manager.job_rets = {
        "master1": {
            "salt/job/1234/ret/salt-minion": {
                "__fun__": "test.ping",
                "__jid__": "1234",
                "__load__": {"cmd": "publish", "tgt": "salt-minion"},
            }
        },
        "master2": {
            "salt/job/5678/ret/salt-minion2": {
                "__fun__": "test.ping",
                "__jid__": "5678",
                "__load__": {"cmd": "publish", "tgt": "salt-minion2"},
            }
        },
    }

    syndic_manager._mark_master_dead = MagicMock()

    for master in syndic_manager._syndics:
        syndic_manager._syndics[master].done.return_value = True
        syndic_manager._syndics[master].exception.return_value = False

    initial_delayed_size = len(syndic_manager.delayed)

    for cycle in range(10):
        for master in syndic_manager._syndics:
            syndic_manager.pub_futures[master] = (
                MagicMock(side_effect=[salt.exceptions.SaltClientTimeout]),
                [{"test_data": f"cycle_{cycle}"}],
            )

        syndic_manager._forward_events()

    # After retry exhaustion, delayed should be cleared (not growing indefinitely)
    final_delayed_size = len(syndic_manager.delayed)

    assert final_delayed_size <= initial_delayed_size + (
        3 * len(syndic_manager._syndics)
    )


def _job_rets(master):
    return {
        master: {
            "salt/job/1234/ret/salt-minion": {
                "__fun__": "test.ping",
                "__jid__": "1234",
                "__load__": {"cmd": "publish", "tgt": "salt-minion"},
            }
        }
    }


@pytest.mark.parametrize("reply", ["ok", {"ret": True}, None])
def test_return_pub_syndic_stores_future_on_success(reply):
    """
    _return_pub_multi(sync=True) returns the reply, not a Future. Repeated
    _forward_events calls must not raise (issue #70588).
    """
    syndic_manager = _syndic_manager()
    syndic_manager._syndics.pop("master2")
    syndic = syndic_manager._syndics["master1"]
    syndic.done.return_value = True
    syndic.exception.return_value = False
    syndic.result.return_value._return_pub_multi.return_value = reply

    for _ in range(3):
        syndic_manager.job_rets = _job_rets("master1")
        syndic_manager._forward_events()

    future, _data = syndic_manager.pub_futures["master1"]
    assert future.done()
    assert future.exception() is None
    assert future.result() == reply
    assert syndic.result().return_pub_multi.call_count == 0
    assert syndic.result()._return_pub_multi.call_count == 3


def test_return_pub_syndic_timeout_is_retried(caplog):
    """
    A timeout ("" from _return_pub_multi) must go through the retry path
    instead of leaving a str in pub_futures (issue #70588).
    """
    syndic_manager = _syndic_manager()
    syndic_manager._syndics.pop("master2")
    syndic = syndic_manager._syndics["master1"]
    syndic.done.return_value = True
    syndic.exception.return_value = False
    syndic.result.return_value._return_pub_multi.return_value = ""
    syndic_manager._mark_master_dead = MagicMock()

    syndic_manager.job_rets = _job_rets("master1")
    syndic_manager._forward_events()
    assert isinstance(
        syndic_manager.pub_futures["master1"][0].exception(),
        salt.exceptions.SaltReqTimeoutError,
    )

    syndic_manager.job_rets = _job_rets("master1")
    syndic_manager._forward_events()  # must not raise
    assert "Unable to call" in caplog.text
    syndic_manager._mark_master_dead.assert_called_once_with("master1")
    assert syndic_manager.tries["master1"] == 1


def test_return_pub_syndic_exception_is_retried():
    """
    An exception raised by _return_pub_multi is recorded on the stored Future.
    """
    syndic_manager = _syndic_manager()
    syndic_manager._syndics.pop("master2")
    syndic = syndic_manager._syndics["master1"]
    syndic.done.return_value = True
    syndic.exception.return_value = False
    syndic.result.return_value._return_pub_multi.side_effect = (
        salt.exceptions.SaltClientError("boom")
    )

    syndic_manager.job_rets = _job_rets("master1")
    syndic_manager._return_pub_syndic(
        list(syndic_manager.job_rets["master1"].values()), master_id="master1"
    )
    assert isinstance(
        syndic_manager.pub_futures["master1"][0].exception(),
        salt.exceptions.SaltClientError,
    )


def test_mark_master_dead_schedules_reconnect():
    """
    Syndic.reconnect is a coroutine. _mark_master_dead must store something with
    done()/exception()/result(), not the bare coroutine (issue #70588).
    """
    loop = asyncio.new_event_loop()
    try:
        syndic_manager = _syndic_manager()
        syndic_manager.io_loop = loop
        syndic = MagicMock()

        async def reconnect():
            return syndic

        syndic.reconnect = reconnect
        connected = loop.create_future()
        connected.set_result(syndic)
        syndic_manager._syndics["master1"] = connected

        syndic_manager._mark_master_dead("master1")

        entry = syndic_manager._syndics["master1"]
        assert not asyncio.iscoroutine(entry)
        assert not entry.done()
        assert loop.run_until_complete(entry) is syndic
        assert entry.done()
        assert entry.exception() is None
    finally:
        loop.close()
