import pytest
import tornado

from salt.cli.batch_async import BatchAsync
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
                MagicMock(side_effect=["1234", "1235", "1236"]),
                {
                    "tgt": "",
                    "fun": "",
                    "kwargs": {"batch": "", "batch_presence_ping_timeout": 1},
                },
            )
            yield batch


def test_ping_jid(batch):
    assert batch.ping_jid == "1234"


def test_batch_jid(batch):
    assert batch.batch_jid == "1235"


def test_find_job_jid(batch):
    assert batch.find_job_jid == "1236"


def test_batch_size(batch):
    """
    Tests passing batch value as a number
    """
    batch.opts = {"batch": "2", "timeout": 5}
    batch.minions = {"foo", "bar"}
    batch.start_batch()
    assert batch.batch_size == 2


def test_batch_start_on_batch_presence_ping_timeout(batch):
    # batch_async = BatchAsyncMock();
    batch.event = MagicMock()
    future = tornado.gen.Future()
    future.set_result({"minions": ["foo", "bar"]})
    batch.local.run_job_async.return_value = future
    with patch("tornado.gen.sleep", return_value=future):
        # ret = batch_async.start(batch)
        ret = batch.start()
        # assert start_batch is called later with batch_presence_ping_timeout as param
        assert batch.event.io_loop.spawn_callback.call_args[0] == (batch.start_batch,)
        # assert test.ping called
        assert batch.local.run_job_async.call_args[0] == ("*", "test.ping", [], "glob")
        # assert targeted_minions == all minions matched by tgt
        assert batch.targeted_minions == {"foo", "bar"}


def test_batch_start_on_gather_job_timeout(batch):
    # batch_async = BatchAsyncMock();
    batch.event = MagicMock()
    future = tornado.gen.Future()
    future.set_result({"minions": ["foo", "bar"]})
    batch.local.run_job_async.return_value = future
    batch.batch_presence_ping_timeout = None
    with patch("tornado.gen.sleep", return_value=future):
        # ret = batch_async.start(batch)
        ret = batch.start()
        # assert start_batch is called later with gather_job_timeout as param
        assert batch.event.io_loop.spawn_callback.call_args[0] == (batch.start_batch,)


def test_batch_fire_start_event(batch):
    batch.minions = {"foo", "bar"}
    batch.opts = {"batch": "2", "timeout": 5}
    batch.event = MagicMock()
    batch.metadata = {"mykey": "myvalue"}
    batch.start_batch()
    assert batch.event.fire_event.call_args[0] == (
        {
            "available_minions": {"foo", "bar"},
            "down_minions": set(),
            "metadata": batch.metadata,
        },
        "salt/batch/1235/start",
    )


def test_start_batch_calls_next(batch):
    batch.run_next = MagicMock(return_value=MagicMock())
    batch.event = MagicMock()
    batch.start_batch()
    assert batch.initialized
    assert batch.event.io_loop.spawn_callback.call_args[0] == (batch.run_next,)


def test_batch_fire_done_event(batch):
    batch.targeted_minions = {"foo", "baz", "bar"}
    batch.minions = {"foo", "bar"}
    batch.done_minions = {"foo"}
    batch.timedout_minions = {"bar"}
    batch.event = MagicMock()
    batch.metadata = {"mykey": "myvalue"}
    old_event = batch.event
    batch.end_batch()
    assert old_event.fire_event.call_args[0] == (
        {
            "available_minions": {"foo", "bar"},
            "done_minions": batch.done_minions,
            "down_minions": {"baz"},
            "timedout_minions": batch.timedout_minions,
            "metadata": batch.metadata,
        },
        "salt/batch/1235/done",
    )


def test_batch__del__(batch):
    batch = BatchAsync(MagicMock(), MagicMock(), MagicMock())
    event = MagicMock()
    batch.event = event
    batch.__del__()
    assert batch.local is None
    assert batch.event is None
    assert batch.ioloop is None


def test_batch_close_safe(batch):
    batch = BatchAsync(MagicMock(), MagicMock(), MagicMock())
    event = MagicMock()
    batch.event = event
    batch.patterns = {
        ("salt/job/1234/ret/*", "find_job_return"),
        ("salt/job/4321/ret/*", "find_job_return"),
    }
    batch.close_safe()
    assert batch.local is None
    assert batch.event is None
    assert batch.ioloop is None
    assert len(event.unsubscribe.mock_calls) == 2
    assert len(event.remove_event_handler.mock_calls) == 1


def test_batch_next(batch):
    batch.event = MagicMock()
    batch.opts["fun"] = "my.fun"
    batch.opts["arg"] = []
    batch._get_next = MagicMock(return_value={"foo", "bar"})
    batch.batch_size = 2
    future = tornado.gen.Future()
    future.set_result({"minions": ["foo", "bar"]})
    batch.local.run_job_async.return_value = future
    with patch("tornado.gen.sleep", return_value=future):
        batch.run_next()
        assert batch.local.run_job_async.call_args[0] == (
            {"foo", "bar"},
            "my.fun",
            [],
            "list",
        )
        assert batch.event.io_loop.spawn_callback.call_args[0] == (
            batch.find_job,
            {"foo", "bar"},
        )
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
    batch.event = MagicMock(
        unpack=MagicMock(return_value=("salt/job/1234/ret/foo", {"id": "foo"}))
    )
    batch.start()
    assert batch.minions == set()
    batch._BatchAsync__event_handler(MagicMock())
    assert batch.minions == {"foo"}
    assert batch.done_minions == set()


def test_batch__event_handler_call_start_batch_when_all_pings_return(batch):
    batch.targeted_minions = {"foo"}
    batch.event = MagicMock(
        unpack=MagicMock(return_value=("salt/job/1234/ret/foo", {"id": "foo"}))
    )
    batch.start()
    batch._BatchAsync__event_handler(MagicMock())
    assert batch.event.io_loop.spawn_callback.call_args[0] == (batch.start_batch,)


def test_batch__event_handler_not_call_start_batch_when_not_all_pings_return(batch):
    batch.targeted_minions = {"foo", "bar"}
    batch.event = MagicMock(
        unpack=MagicMock(return_value=("salt/job/1234/ret/foo", {"id": "foo"}))
    )
    batch.start()
    batch._BatchAsync__event_handler(MagicMock())
    assert len(batch.event.io_loop.spawn_callback.mock_calls) == 0


def test_batch__event_handler_batch_run_return(batch):
    batch.event = MagicMock(
        unpack=MagicMock(return_value=("salt/job/1235/ret/foo", {"id": "foo"}))
    )
    batch.start()
    batch.active = {"foo"}
    batch._BatchAsync__event_handler(MagicMock())
    assert batch.active == set()
    assert batch.done_minions == {"foo"}
    assert batch.event.io_loop.spawn_callback.call_args[0] == (batch.schedule_next,)


def test_batch__event_handler_find_job_return(batch):
    batch.event = MagicMock(
        unpack=MagicMock(
            return_value=(
                "salt/job/1236/ret/foo",
                {"id": "foo", "return": "deadbeaf"},
            )
        )
    )
    batch.start()
    batch.patterns.add(("salt/job/1236/ret/*", "find_job_return"))
    batch._BatchAsync__event_handler(MagicMock())
    assert batch.find_job_returned == {"foo"}


def test_batch_run_next_end_batch_when_no_next(batch):
    batch.end_batch = MagicMock()
    batch._get_next = MagicMock(return_value={})
    batch.run_next()
    assert len(batch.end_batch.mock_calls) == 1


def test_batch_find_job(batch):
    batch.event = MagicMock()
    future = tornado.gen.Future()
    future.set_result({})
    batch.local.run_job_async.return_value = future
    batch.minions = {"foo", "bar"}
    batch.jid_gen = MagicMock(return_value="1234")
    with patch("tornado.gen.sleep", return_value=future):
        batch.find_job({"foo", "bar"})
        assert batch.event.io_loop.spawn_callback.call_args[0] == (
            batch.check_find_job,
            {"foo", "bar"},
            "1234",
        )


def test_batch_find_job_with_done_minions(batch):
    batch.done_minions = {"bar"}
    batch.event = MagicMock()
    future = tornado.gen.Future()
    future.set_result({})
    batch.local.run_job_async.return_value = future
    batch.minions = {"foo", "bar"}
    batch.jid_gen = MagicMock(return_value="1234")
    with patch("tornado.gen.sleep", return_value=future):
        batch.find_job({"foo", "bar"})
        assert batch.event.io_loop.spawn_callback.call_args[0] == (
            batch.check_find_job,
            {"foo"},
            "1234",
        )


def test_batch_check_find_job_did_not_return(batch):
    batch.event = MagicMock()
    batch.active = {"foo"}
    batch.find_job_returned = set()
    batch.patterns = {("salt/job/1234/ret/*", "find_job_return")}
    batch.check_find_job({"foo"}, jid="1234")
    assert batch.find_job_returned == set()
    assert batch.active == set()
    assert len(batch.event.io_loop.add_callback.mock_calls) == 0


def test_batch_check_find_job_did_return(batch):
    batch.event = MagicMock()
    batch.find_job_returned = {"foo"}
    batch.patterns = {("salt/job/1234/ret/*", "find_job_return")}
    batch.check_find_job({"foo"}, jid="1234")
    assert batch.event.io_loop.spawn_callback.call_args[0] == (batch.find_job, {"foo"})


def test_batch_check_find_job_multiple_states(batch):
    batch.event = MagicMock()
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

    batch.patterns = {("salt/job/1234/ret/*", "find_job_return")}
    batch.check_find_job(not_done, jid="1234")

    # assert 'bar' removed from active
    assert batch.active == {"foo"}

    # assert 'bar' added to timedout_minions
    assert batch.timedout_minions == {"bar", "faz"}

    # assert 'find_job' schedueled again only for 'foo'
    assert batch.event.io_loop.spawn_callback.call_args[0] == (batch.find_job, {"foo"})


def test_only_on_run_next_is_scheduled(batch):
    batch.event = MagicMock()
    batch.scheduled = True
    batch.schedule_next()
    assert len(batch.event.io_loop.spawn_callback.mock_calls) == 0
