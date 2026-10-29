import asyncio

import pytest

import salt.utils.asynchronous
from salt.cli.batch_async import BatchAsync, batch_async_required
from tests.support.mock import AsyncMock, MagicMock, patch


@pytest.fixture
def batch(temp_salt_master, io_loop):
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

    channel = MagicMock()
    channel.use.return_value = channel
    channel.subscribe = AsyncMock()
    channel.master_event.fire_event_async = AsyncMock()
    channel.local_client.run_job_async = AsyncMock(return_value={"minions": []})
    with patch(
        "salt.cli.batch_async._get_shared_events_channel", return_value=channel
    ), patch("salt.cli.batch_async.batch_get_opts", return_value=opts), patch(
        "salt.cli.batch_async._destroy_unused_shared_events_channel", AsyncMock()
    ):
        instance = BatchAsync(
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
        yield instance
        salt.utils.asynchronous.aioloop(io_loop).run_until_complete(
            instance.close_safe()
        )


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


async def test_batch_size(batch):
    """
    Tests passing batch value as a number
    """
    batch.opts = {"batch": "2", "timeout": 5}
    batch.minions = {"foo", "bar"}
    await batch.start_batch()
    assert batch.batch_size == 2


@pytest.mark.parametrize("presence_timeout", [0.01, None])
async def test_batch_starts_after_presence_timeout(batch, presence_timeout):
    batch.batch_presence_ping_timeout = presence_timeout
    batch.opts["gather_job_timeout"] = 0.01
    batch.events_channel.local_client.run_job_async.return_value = {
        "minions": ["foo", "bar"]
    }
    started = []

    async def start_batch():
        started.append(True)

    batch.start_batch = start_batch
    await batch.start()
    assert started == [True]
    assert batch.targeted_minions == {"foo", "bar"}
    assert batch.events_channel.local_client.run_job_async.call_args.args[:4] == (
        "*",
        "test.ping",
        [],
        "glob",
    )


async def test_batch_fire_start_event(batch):
    batch.minions = {"foo", "bar"}
    batch.opts = {"batch": "2", "timeout": 5}
    with patch.object(
        batch, "events_channel", MagicMock(subscribe=AsyncMock())
    ), patch.object(
        batch.event,
        "fire_event_async",
        AsyncMock(return_value={}),
    ) as fire_event_mock:
        await batch.start_batch()
        assert fire_event_mock.call_args[0] == (
            {
                "available_minions": {"foo", "bar"},
                "down_minions": set(),
                "metadata": batch.metadata,
            },
            "salt/batch/1235/start",
        )


async def test_start_batch_calls_next(batch):
    batch.initialized = False
    future = asyncio.get_event_loop().create_future()
    future.set_result({})
    with patch.object(
        batch, "event", MagicMock(fire_event_async=AsyncMock())
    ), patch.object(
        batch, "events_channel", MagicMock(subscribe=AsyncMock())
    ), patch.object(
        batch, "run_next", return_value=future
    ) as run_next_mock:
        batch.events_channel.master_event.fire_event_async.return_value = future
        await batch.start_batch()
        assert batch.initialized
        run_next_mock.assert_called_once()


async def test_batch_fire_done_event(batch):
    batch.targeted_minions = {"foo", "baz", "bar"}
    batch.minions = {"foo", "bar"}
    batch.done_minions = {"foo"}
    batch.timedout_minions = {"bar"}
    with patch.object(
        batch, "events_channel", MagicMock(subscribe=AsyncMock())
    ), patch.object(
        batch.event,
        "fire_event_async",
        AsyncMock(return_value={}),
    ) as fire_event_mock:
        await batch.end_batch()
        assert fire_event_mock.call_args[0] == (
            {
                "available_minions": {"foo", "bar"},
                "done_minions": batch.done_minions,
                "down_minions": {"baz"},
                "timedout_minions": batch.timedout_minions,
                "metadata": batch.metadata,
            },
            "salt/batch/1235/done",
        )


async def test_batch_close_safe(batch):
    with patch.object(
        batch, "events_channel", MagicMock(subscribe=AsyncMock())
    ) as events_channel_mock, patch.object(
        batch, "event", MagicMock(fire_event_async=AsyncMock())
    ):
        await batch.close_safe()
        await batch.close_safe()
        assert batch.events_channel is None
        assert batch.event is None
        events_channel_mock.unsubscribe.assert_called_once()
        events_channel_mock.unuse.assert_called_once()


async def test_batch_next(batch):
    batch.opts["fun"] = "my.fun"
    batch.opts["arg"] = []
    batch.batch_size = 2
    future = asyncio.get_event_loop().create_future()
    future.set_result({})
    with patch("asyncio.sleep", return_value=future), patch.object(
        batch, "events_channel", MagicMock(subscribe=AsyncMock())
    ), patch.object(batch, "_get_next", return_value={"foo", "bar"}), patch.object(
        batch, "find_job", return_value=future
    ) as find_job_mock:
        batch.events_channel.local_client.run_job_async.return_value = future
        await batch.run_next()
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


async def test_batch__event_handler_ping_return(batch):
    batch.targeted_minions = {"foo"}
    with patch.object(
        batch.events_channel.local_client,
        "run_job_async",
        AsyncMock(return_value={"minions": ["foo"]}),
    ) as local_client_mock, patch.object(
        batch.events_channel.master_event,
        "fire_event_async",
        AsyncMock(return_value={}),
    ) as fire_event_async_mock:
        batch._create_task(batch.start())
        assert batch.minions == set()
        await batch._BatchAsync__event_handler(
            "salt/job/1234/ret/foo", {"id": "foo"}, "ping_return"
        )
        assert batch.minions == {"foo"}
        assert batch.done_minions == set()


async def test_batch__event_handler_call_start_batch_when_all_pings_return(batch):
    batch.targeted_minions = {"foo"}
    with patch.object(
        batch.events_channel.local_client,
        "run_job_async",
        AsyncMock(return_value={"minions": ["foo"]}),
    ) as local_client_mock, patch.object(
        batch, "start_batch", AsyncMock(return_value=None)
    ) as start_batch_mock:
        batch._create_task(batch.start())
        await batch._BatchAsync__event_handler(
            "salt/job/1234/ret/foo", {"id": "foo"}, "ping_return"
        )
        await asyncio.sleep(1)
        start_batch_mock.assert_called_once()


async def test_batch__event_handler_not_call_start_batch_when_not_all_pings_return(
    batch,
):
    batch.targeted_minions = {"foo", "bar"}
    with patch.object(
        batch.events_channel.local_client,
        "run_job_async",
        AsyncMock(return_value={"minions": ["foo", "bar"]}),
    ) as local_client_mock, patch.object(
        batch, "start_batch", AsyncMock(return_value=None)
    ) as start_batch_mock:
        batch._create_task(batch.start())
        await batch._BatchAsync__event_handler(
            "salt/job/1234/ret/foo", {"id": "foo"}, "ping_return"
        )
        await asyncio.sleep(1)
        start_batch_mock.assert_not_called()


async def test_batch__event_handler_batch_run_return(batch):
    future = asyncio.get_event_loop().create_future()
    future.set_result({})
    with patch.object(
        batch.events_channel.local_client,
        "run_job_async",
        AsyncMock(return_value={"minions": ["foo", "bar"]}),
    ) as local_client_mock, patch.object(
        batch, "schedule_next", AsyncMock(return_value=None)
    ) as schedule_next_mock:
        batch._create_task(batch.start())
        await asyncio.sleep(1)
        batch.active = {"foo"}
        await batch._BatchAsync__event_handler(
            "salt/job/1235/ret/foo", {"id": "foo"}, "batch_run"
        )
        assert batch.active == set()
        assert batch.done_minions == {"foo"}
        schedule_next_mock.assert_called_once()


async def test_batch__event_handler_find_job_return(batch):
    batch._create_task(batch.start())
    await batch._BatchAsync__event_handler(
        "salt/job/1236/ret/foo", {"id": "foo", "return": "deadbeaf"}, "find_job_return"
    )
    assert batch.find_job_returned == {"foo"}


async def test_batch_run_next_end_batch_when_no_next(batch):
    future = asyncio.get_event_loop().create_future()
    future.set_result({})
    with patch.object(batch, "_get_next", return_value={}), patch.object(
        batch, "end_batch", return_value=future
    ) as end_batch_mock:
        await batch.run_next()
        end_batch_mock.assert_called_once()


async def test_batch_find_job(batch):
    future = asyncio.get_event_loop().create_future()
    future.set_result({})
    batch.minions = {"foo", "bar"}
    with patch("asyncio.sleep", return_value=future), patch.object(
        batch, "check_find_job", return_value=future
    ) as check_find_job_mock, patch.object(batch, "jid_gen", return_value="1236"):
        batch.events_channel.local_client.run_job_async.return_value = future
        await batch.find_job({"foo", "bar"})
        assert check_find_job_mock.call_args[0] == (
            {"foo", "bar"},
            "1236",
        )


async def test_batch_find_job_with_done_minions(batch):
    batch.done_minions = {"bar"}
    future = asyncio.get_event_loop().create_future()
    future.set_result({})
    batch.minions = {"foo", "bar"}
    with patch("asyncio.sleep", return_value=future), patch.object(
        batch, "check_find_job", return_value=future
    ) as check_find_job_mock, patch.object(batch, "jid_gen", return_value="1236"):
        batch.events_channel.local_client.run_job_async.return_value = future
        await batch.find_job({"foo", "bar"})
        assert check_find_job_mock.call_args[0] == (
            {"foo"},
            "1236",
        )


async def test_batch_check_find_job_did_not_return(batch):
    batch.active = {"foo"}
    batch.find_job_returned = set()
    batch.batch_size = 2
    future = asyncio.get_event_loop().create_future()
    future.set_result({})
    with patch.object(batch, "find_job", return_value=future) as find_job_mock:
        await batch.check_find_job({"foo"}, jid="1234")
        assert batch.find_job_returned == set()
        assert batch.active == set()
        find_job_mock.assert_not_called()


async def test_batch_check_find_job_did_return(batch):
    batch.find_job_returned = {"foo"}
    future = asyncio.get_event_loop().create_future()
    future.set_result({})
    with patch.object(batch, "find_job", return_value=future) as find_job_mock:
        await batch.check_find_job({"foo"}, jid="1234")
        find_job_mock.assert_called_once_with({"foo"})


async def test_batch_check_find_job_multiple_states(batch):
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

    future = asyncio.get_event_loop().create_future()
    future.set_result({})

    with patch.object(
        batch, "schedule_next", AsyncMock(return_value=None)
    ), patch.object(batch, "find_job", return_value=future) as find_job_mock:
        await batch.check_find_job(not_done, jid="1234")

        # assert 'bar' removed from active
        assert batch.active == {"foo"}

        # assert 'bar' added to timedout_minions
        assert batch.timedout_minions == {"bar", "faz"}

        # assert 'find_job' schedueled again only for 'foo'
        find_job_mock.assert_called_once_with({"foo"})


async def test_only_on_run_next_is_scheduled(batch):
    future = asyncio.get_event_loop().create_future()
    future.set_result({})
    batch.scheduled = True
    with patch.object(batch, "run_next", return_value=future) as run_next_mock:
        await batch.schedule_next()
        run_next_mock.assert_not_called()


async def test_start_event_completes_before_dispatch(batch):
    publishing = asyncio.Event()
    release = asyncio.Event()

    async def fire_event(data, tag):
        publishing.set()
        await release.wait()

    batch.event.fire_event_async = fire_event
    with patch.object(batch, "run_next", AsyncMock()) as run_next:
        task = batch._create_task(batch.start_batch())
        await publishing.wait()
        run_next.assert_not_awaited()
        release.set()
        await task
        run_next.assert_awaited_once()


async def test_done_event_completes_before_channel_is_released(batch):
    publishing = asyncio.Event()
    release = asyncio.Event()
    channel = batch.events_channel

    async def fire_event(data, tag):
        publishing.set()
        await release.wait()

    batch.event.fire_event_async = fire_event
    task = batch._create_task(batch.end_batch())
    await publishing.wait()
    channel.unuse.assert_not_called()
    assert batch.event is not None
    release.set()
    await task
    channel.unuse.assert_called_once()
    assert batch.event is None


async def test_close_drains_pending_batch_jobs(batch):
    started = asyncio.Event()
    cleaned = asyncio.Event()

    async def job():
        try:
            started.set()
            await asyncio.Event().wait()
        finally:
            await asyncio.sleep(0)
            cleaned.set()

    task = batch._create_task(job())
    await started.wait()
    await batch.close_safe()
    assert cleaned.is_set()
    assert task.cancelled()
    assert batch.events_channel is None
    assert not asyncio.get_running_loop().is_closed()


async def test_start_failure_releases_shared_channel(batch):
    channel = batch.events_channel
    channel.local_client.run_job_async = AsyncMock(
        side_effect=OSError("publish failed")
    )
    with pytest.raises(OSError, match="publish failed"):
        await batch.start()
    channel.unuse.assert_called_once()
    assert batch.event is None


async def test_cancelled_start_releases_shared_channel(batch):
    channel = batch.events_channel
    started = asyncio.Event()

    async def publish(*args, **kwargs):
        started.set()
        await asyncio.Event().wait()

    channel.local_client.run_job_async = publish
    task = batch._create_task(batch.start())
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    channel.unuse.assert_called_once()
    assert batch.event is None


@pytest.fixture
def shared_channel(io_loop):
    from salt.cli.batch_async import SharedEventsChannel

    with patch("salt.client.get_local_client") as local, patch(
        "salt.utils.event.get_event"
    ) as event:
        event.return_value.subscriber._stream = MagicMock()
        event.return_value.subscriber.connected = False
        instance = SharedEventsChannel({"conf_file": "master"}, io_loop)
        yield instance
        salt.utils.asynchronous.aioloop(io_loop).run_until_complete(
            instance.destroy_unused()
        )


async def test_subscription_awaits_connection(shared_channel):
    subscriber = shared_channel.master_event.subscriber
    started = asyncio.Event()
    release = asyncio.Event()

    async def connect():
        started.set()
        await release.wait()
        subscriber.connected = True

    subscriber.connect = AsyncMock(side_effect=connect)
    task = asyncio.create_task(
        shared_channel.subscribe("123", "return", 1, AsyncMock())
    )
    await started.wait()
    assert not task.done()
    release.set()
    await task
    subscriber.connect.assert_awaited_once()


async def test_unsubscribe_removes_entire_job_id(shared_channel):
    shared_channel.master_event.subscriber.connected = True
    handler = AsyncMock()
    await shared_channel.subscribe("123", "return", 1, handler)
    await shared_channel.subscribe("456", "return", 1, handler)
    shared_channel.unsubscribe("123", "return", 1)
    assert "123" not in shared_channel._subscriptions
    assert shared_channel._subscribers[1] == {"456"}


async def test_destroy_drains_reconnect(shared_channel):
    subscriber = shared_channel.master_event.subscriber
    started = asyncio.Event()
    cleaned = asyncio.Event()

    async def connect():
        try:
            started.set()
            await asyncio.Event().wait()
        finally:
            cleaned.set()

    subscriber.connect = connect
    task = asyncio.create_task(
        shared_channel.subscribe("123", "return", 1, AsyncMock())
    )
    await started.wait()
    assert await shared_channel.destroy_unused() is True
    assert cleaned.is_set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert shared_channel.master_event is None


async def test_new_user_keeps_shared_channel_during_reconnect_cleanup(shared_channel):
    subscriber = shared_channel.master_event.subscriber
    started = asyncio.Event()
    cleaning = asyncio.Event()
    release = asyncio.Event()

    async def connect():
        try:
            started.set()
            await asyncio.Event().wait()
        finally:
            cleaning.set()
            await release.wait()

    subscriber.connect = connect
    pending = asyncio.create_task(
        shared_channel.subscribe("123", "return", 1, AsyncMock())
    )
    await started.wait()
    closing = asyncio.create_task(shared_channel.destroy_unused())
    await cleaning.wait()
    shared_channel.use("new batch")
    release.set()
    assert await closing is False
    assert shared_channel.master_event is not None
    with pytest.raises(asyncio.CancelledError):
        await pending
    shared_channel.unuse("new batch")
