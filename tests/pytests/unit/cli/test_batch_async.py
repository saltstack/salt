import pytest
import tornado

from salt.cli.batch_async import BatchAsync, batch_async_required
from tests.support.mock import MagicMock, patch


@pytest.fixture
def batch(temp_salt_master):
    opts = {
        "batch": "1",
        "conf_file": {},
        "tgt": "*",
        "timeout": 5,
        "gather_job_timeout": 5,
        "batch_presence_ping_timeout": 1,
        "transport": None,
        "sock_dir": "",
    }

    with patch("salt.client.get_local_client", MagicMock(return_value=MagicMock())):
        with patch("salt.cli.batch_async.batch_get_opts", MagicMock(return_value=opts)):
            batch = BatchAsync(
                opts,
                MagicMock(side_effect=["1234", "1235"]),
                {
                    "tgt": "",
                    "fun": "",
                    "kwargs": {
                        "batch": "",
                        "batch_presence_ping_timeout": 1,
                        "metadata": {"mykey": "myvalue"},
                    },
                },
            )
            yield batch


@pytest.mark.parametrize(
    "threshold,minions,batch,expected",
    [
        (1, 2, 200, True),
        (1, 500, 200, True),
        (0, 2, 200, False),
        (0, 500, 200, False),
        (-1, 2, 200, False),
        (-1, 500, 200, True),
        (-1, 9, 10, False),
        (-1, 11, 10, True),
        (10, 9, 8, False),
        (10, 9, 10, False),
        (10, 11, 8, True),
        (10, 11, 10, True),
    ],
)
def test_batch_async_required(threshold, minions, batch, expected):
    minions_list = [f"minion{i}.example.org" for i in range(minions)]
    batch_async_opts = {"batch_async": {"threshold": threshold}}
    extra = {"batch": batch}
    assert batch_async_required(batch_async_opts, minions_list, extra) == expected


def test_ping_jid(batch):
    assert batch.ping_jid == "1234"


def test_batch_jid(batch):
    assert batch.batch_jid == "1235"


def test_batch_size(batch):
    """
    Tests passing batch value as a number
    """
    batch.opts = {"batch": "2", "timeout": 5}
    batch.minions = {"foo", "bar"}
    batch.start_batch()
    assert batch.batch_size == 2


def test_batch_start_on_batch_presence_ping_timeout(batch):
    future_ret = tornado.gen.Future()
    future_ret.set_result({"minions": ["foo", "bar"]})
    future = tornado.gen.Future()
    future.set_result({})
    with patch.object(batch, "events_channel", MagicMock()), patch(
        "tornado.gen.sleep", return_value=future
    ), patch.object(batch, "start_batch", return_value=future) as start_batch_mock:
        batch.events_channel.local_client.run_job_async.return_value = future_ret
        ret = batch.start()
        # assert start_batch is called
        start_batch_mock.assert_called_once()
        # assert test.ping called
        assert batch.events_channel.local_client.run_job_async.call_args[0] == (
            "*",
            "test.ping",
            [],
            "glob",
        )
        # assert targeted_minions == all minions matched by tgt
        assert batch.targeted_minions == {"foo", "bar"}


def test_batch_start_on_gather_job_timeout(batch):
    future = tornado.gen.Future()
    future.set_result({})
    future_ret = tornado.gen.Future()
    future_ret.set_result({"minions": ["foo", "bar"]})
    batch.batch_presence_ping_timeout = None
    with patch.object(batch, "events_channel", MagicMock()), patch(
        "tornado.gen.sleep", return_value=future
    ), patch.object(
        batch, "start_batch", return_value=future
    ) as start_batch_mock, patch.object(
        batch, "batch_presence_ping_timeout", None
    ):
        batch.events_channel.local_client.run_job_async.return_value = future_ret
        # ret = batch_async.start(batch)
        ret = batch.start()
        # assert start_batch is called
        start_batch_mock.assert_called_once()


def test_batch_fire_start_event(batch):
    batch.minions = {"foo", "bar"}
    batch.opts = {"batch": "2", "timeout": 5}
    with patch.object(batch, "events_channel", MagicMock()):
        batch.start_batch()
        assert batch.events_channel.master_event.fire_event_async.call_args[0] == (
            {
                "available_minions": {"foo", "bar"},
                "down_minions": set(),
                "metadata": batch.metadata,
            },
            "salt/batch/1235/start",
        )


def test_start_batch_calls_next(batch):
    batch.initialized = False
    future = tornado.gen.Future()
    future.set_result({})
    with patch.object(batch, "event", MagicMock()), patch.object(
        batch, "events_channel", MagicMock()
    ), patch.object(batch, "run_next", return_value=future) as run_next_mock:
        batch.events_channel.master_event.fire_event_async.return_value = future
        batch.start_batch()
        assert batch.initialized
        run_next_mock.assert_called_once()


def test_batch_fire_done_event(batch):
    batch.targeted_minions = {"foo", "baz", "bar"}
    batch.minions = {"foo", "bar"}
    batch.done_minions = {"foo"}
    batch.timedout_minions = {"bar"}
    with patch.object(batch, "events_channel", MagicMock()):
        batch.end_batch()
        assert batch.events_channel.master_event.fire_event_async.call_args[0] == (
            {
                "available_minions": {"foo", "bar"},
                "done_minions": batch.done_minions,
                "down_minions": {"baz"},
                "timedout_minions": batch.timedout_minions,
                "metadata": batch.metadata,
            },
            "salt/batch/1235/done",
        )


def test_batch_close_safe(batch):
    with patch.object(
        batch, "events_channel", MagicMock()
    ) as events_channel_mock, patch.object(batch, "event", MagicMock()):
        batch.close_safe()
        batch.close_safe()
        assert batch.events_channel is None
        assert batch.event is None
        events_channel_mock.unsubscribe.assert_called_once()
        events_channel_mock.unuse.assert_called_once()


def test_batch_next(batch):
    batch.opts["fun"] = "my.fun"
    batch.opts["arg"] = []
    batch.batch_size = 2
    future = tornado.gen.Future()
    future.set_result({})
    with patch("tornado.gen.sleep", return_value=future), patch.object(
        batch, "events_channel", MagicMock()
    ), patch.object(batch, "_get_next", return_value={"foo", "bar"}), patch.object(
        batch, "find_job", return_value=future
    ) as find_job_mock:
        batch.events_channel.local_client.run_job_async.return_value = future
        batch.run_next()
        assert batch.events_channel.local_client.run_job_async.call_args[0] == (
            {"foo", "bar"},
            "my.fun",
            [],
            "list",
        )
        assert find_job_mock.call_args[0] == ({"foo", "bar"},)
        assert batch.active == {"bar", "foo"}


def test_next_batch(batch):
    batch.minions = {"foo", "bar"}
    batch.batch_size = 2
    assert batch._get_next() == {"foo", "bar"}


def test_next_batch_one_done(batch):
    batch.minions = {"foo", "bar"}
    batch.done_minions = {"bar"}
    batch.batch_size = 2
    assert batch._get_next() == {"foo"}


def test_next_batch_one_done_one_active(batch):
    batch.minions = {"foo", "bar", "baz"}
    batch.done_minions = {"bar"}
    batch.active = {"baz"}
    batch.batch_size = 2
    assert batch._get_next() == {"foo"}


def test_next_batch_one_done_one_active_one_timedout(batch):
    batch.minions = {"foo", "bar", "baz", "faz"}
    batch.done_minions = {"bar"}
    batch.active = {"baz"}
    batch.timedout_minions = {"faz"}
    batch.batch_size = 2
    assert batch._get_next() == {"foo"}


def test_next_batch_bigger_size(batch):
    batch.minions = {"foo", "bar"}
    batch.batch_size = 3
    assert batch._get_next() == {"foo", "bar"}


def test_next_batch_all_done(batch):
    batch.minions = {"foo", "bar"}
    batch.done_minions = {"foo", "bar"}
    batch.batch_size = 2
    assert batch._get_next() == set()


def test_next_batch_all_active(batch):
    batch.minions = {"foo", "bar"}
    batch.active = {"foo", "bar"}
    batch.batch_size = 2
    assert batch._get_next() == set()


def test_next_batch_all_timedout(batch):
    batch.minions = {"foo", "bar"}
    batch.timedout_minions = {"foo", "bar"}
    batch.batch_size = 2
    assert batch._get_next() == set()


def test_batch__event_handler_ping_return(batch):
    batch.targeted_minions = {"foo"}
    batch.start()
    assert batch.minions == set()
    batch._BatchAsync__event_handler(
        "salt/job/1234/ret/foo", {"id": "foo"}, "ping_return"
    )
    assert batch.minions == {"foo"}
    assert batch.done_minions == set()


def test_batch__event_handler_call_start_batch_when_all_pings_return(batch):
    batch.targeted_minions = {"foo"}
    future = tornado.gen.Future()
    future.set_result({})
    with patch.object(batch, "start_batch", return_value=future) as start_batch_mock:
        batch.start()
        batch._BatchAsync__event_handler(
            "salt/job/1234/ret/foo", {"id": "foo"}, "ping_return"
        )
        start_batch_mock.assert_called_once()


def test_batch__event_handler_not_call_start_batch_when_not_all_pings_return(batch):
    batch.targeted_minions = {"foo", "bar"}
    future = tornado.gen.Future()
    future.set_result({})
    with patch.object(batch, "start_batch", return_value=future) as start_batch_mock:
        batch.start()
        batch._BatchAsync__event_handler(
            "salt/job/1234/ret/foo", {"id": "foo"}, "ping_return"
        )
        start_batch_mock.assert_not_called()


def test_batch__event_handler_batch_run_return(batch):
    future = tornado.gen.Future()
    future.set_result({})
    with patch.object(
        batch, "schedule_next", return_value=future
    ) as schedule_next_mock:
        batch.start()
        batch.active = {"foo"}
        batch._BatchAsync__event_handler(
            "salt/job/1235/ret/foo", {"id": "foo"}, "batch_run"
        )
        assert batch.active == set()
        assert batch.done_minions == {"foo"}
        schedule_next_mock.assert_called_once()


def test_batch__event_handler_find_job_return(batch):
    batch.start()
    batch._BatchAsync__event_handler(
        "salt/job/1236/ret/foo", {"id": "foo", "return": "deadbeaf"}, "find_job_return"
    )
    assert batch.find_job_returned == {"foo"}


def test_batch_run_next_end_batch_when_no_next(batch):
    future = tornado.gen.Future()
    future.set_result({})
    with patch.object(
        batch, "_get_next", return_value={}
    ), patch.object(
        batch, "end_batch", return_value=future
    ) as end_batch_mock:
        batch.run_next()
        end_batch_mock.assert_called_once()


def test_batch_find_job(batch):
    future = tornado.gen.Future()
    future.set_result({})
    batch.minions = {"foo", "bar"}
    with patch("tornado.gen.sleep", return_value=future), patch.object(
        batch, "check_find_job", return_value=future
    ) as check_find_job_mock, patch.object(
        batch, "jid_gen", return_value="1236"
    ):
        batch.events_channel.local_client.run_job_async.return_value = future
        batch.find_job({"foo", "bar"})
        assert check_find_job_mock.call_args[0] == (
            {"foo", "bar"},
            "1236",
        )


def test_batch_find_job_with_done_minions(batch):
    batch.done_minions = {"bar"}
    future = tornado.gen.Future()
    future.set_result({})
    batch.minions = {"foo", "bar"}
    with patch("tornado.gen.sleep", return_value=future), patch.object(
        batch, "check_find_job", return_value=future
    ) as check_find_job_mock, patch.object(
        batch, "jid_gen", return_value="1236"
    ):
        batch.events_channel.local_client.run_job_async.return_value = future
        batch.find_job({"foo", "bar"})
        assert check_find_job_mock.call_args[0] == (
            {"foo"},
            "1236",
        )


def test_batch_check_find_job_did_not_return(batch):
    batch.active = {"foo"}
    batch.find_job_returned = set()
    future = tornado.gen.Future()
    future.set_result({})
    with patch.object(batch, "find_job", return_value=future) as find_job_mock:
        batch.check_find_job({"foo"}, jid="1234")
        assert batch.find_job_returned == set()
        assert batch.active == set()
        find_job_mock.assert_not_called()


def test_batch_check_find_job_did_return(batch):
    batch.find_job_returned = {"foo"}
    future = tornado.gen.Future()
    future.set_result({})
    with patch.object(batch, "find_job", return_value=future) as find_job_mock:
        batch.check_find_job({"foo"}, jid="1234")
        find_job_mock.assert_called_once_with({"foo"})


def test_batch_check_find_job_multiple_states(batch):
    # currently running minions
    batch.active = {"foo", "bar"}

    # minion is running and find_job returns
    batch.find_job_returned = {"foo"}

    # minion started running but find_job did not return
    batch.timedout_minions = {"faz"}

    # minion finished
    batch.done_minions = {"baz"}

    # both not yet done but only 'foo' responded to find_job
    not_done = {"foo", "bar"}

    future = tornado.gen.Future()
    future.set_result({})

    with patch.object(batch, "schedule_next", return_value=future), patch.object(
        batch, "find_job", return_value=future
    ) as find_job_mock:
        batch.check_find_job(not_done, jid="1234")

        # assert 'bar' removed from active
        assert batch.active == {"foo"}

        # assert 'bar' added to timedout_minions
        assert batch.timedout_minions == {"bar", "faz"}

        # assert 'find_job' schedueled again only for 'foo'
        find_job_mock.assert_called_once_with({"foo"})


def test_only_on_run_next_is_scheduled(batch):
    future = tornado.gen.Future()
    future.set_result({})
    batch.scheduled = True
    with patch.object(batch, "run_next", return_value=future) as run_next_mock:
        batch.schedule_next()
        run_next_mock.assert_not_called()
