"""
Tests for the SyndicManager and Syndic classes in minion.py
"""

import collections

import pytest

import salt.exceptions
import salt.minion
from tests.support.mock import AsyncMock, MagicMock, call


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

    assert caplog.text.count("Unable to call") == 2
    assert syndic_manager._mark_master_dead.call_args_list.count(call(master1)) == 1
    assert syndic_manager._mark_master_dead.call_args_list.count(call(master2)) == 1
    assert syndic_manager.tries == collections.defaultdict(int)
    assert syndic_manager._syndics[master1].result()._return_pub_multi.call_count == 2
    assert syndic_manager._syndics[master2].result()._return_pub_multi.call_count == 1


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


@pytest.fixture
def syndic_opts():
    return {
        "conf_file": "conf/minion",
        "id": "syndic",
        "master": "127.0.0.1",
        "master_port": 4506,
        "master_uri": "tcp://127.0.0.1:4506",
        "acceptance_wait_time": 10,
        "acceptance_wait_time_max": 20,
        "syndic_failover": "ordered",
        "syndic_retries": 3,
        "pki_dir": "/tmp",
        "sock_dir": "/tmp",
        "cachedir": "/tmp",
        "auth_tries": 1,
        "auth_timeout": 5,
        "keysize": 2048,
        "__role": "syndic",
        "zmq_filtering": False,
        "zmq_monitor": False,
        "ipv6": False,
        "recon_default": 1000,
        "recon_max": 5000,
        "recon_randomize": False,
    }


async def test_syndic_reconnect_invalidates_auth(syndic_opts):
    """
    When Syndic.reconnect() is called and pub_channel has an auth attribute,
    the auth should be invalidated before the channel is closed.
    """
    syndic = salt.minion.Syndic.__new__(salt.minion.Syndic)
    syndic.opts = syndic_opts
    syndic.connected = True
    syndic.destroy = MagicMock()  # prevent incomplete __del__ teardown

    mock_auth = MagicMock()
    mock_pub_channel = MagicMock()
    mock_pub_channel.auth = mock_auth

    syndic.pub_channel = mock_pub_channel
    syndic.eval_master = AsyncMock(return_value=("127.0.0.1", MagicMock()))

    await syndic.reconnect()

    mock_auth.invalidate.assert_called_once()
    mock_pub_channel.on_recv.assert_called_with(None)
    mock_pub_channel.close.assert_called_once()


async def test_syndic_reconnect_without_auth_attribute(syndic_opts):
    """
    When Syndic.reconnect() is called and pub_channel has no auth attribute,
    reconnect should complete without error.
    """
    syndic = salt.minion.Syndic.__new__(salt.minion.Syndic)
    syndic.opts = syndic_opts
    syndic.connected = True
    syndic.destroy = MagicMock()  # prevent incomplete __del__ teardown

    mock_pub_channel = MagicMock(spec=["on_recv", "close"])

    syndic.pub_channel = mock_pub_channel
    syndic.eval_master = AsyncMock(return_value=("127.0.0.1", MagicMock()))

    await syndic.reconnect()

    mock_pub_channel.on_recv.assert_called_with(None)
    mock_pub_channel.close.assert_called_once()
