"""Native event sessions retain filtering and await their own cleanup."""

import asyncio
import weakref
from types import SimpleNamespace

import pytest

import salt.utils.asynchronous
from salt.utils.event import SaltEvent
from tests.support.mock import patch


@pytest.fixture
def session(io_loop, tmp_path):
    loop = salt.utils.asynchronous.aioloop(io_loop)
    event = SaltEvent(
        "master",
        opts={"id": "master", "sock_dir": str(tmp_path)},
        listen=False,
        io_loop=loop,
    )
    queue = asyncio.Queue()
    state = {"closed": False}

    async def recv(timeout=None):
        if timeout == 0:
            try:
                return queue.get_nowait()
            except asyncio.QueueEmpty:
                return None
        return await queue.get()

    async def close():
        state["closed"] = True

    event.subscriber = SimpleNamespace(recv=recv, close_async=close)
    event.cpub = True
    yield event, queue, state
    loop.run_until_complete(event.destroy_async())


@pytest.mark.parametrize(
    "match_type,tag",
    [
        ("startswith", "salt/job/"),
        ("endswith", "/ret/minion"),
        ("find", "/123/"),
        ("regex", r"salt/job/\d+/ret/.*"),
        ("fnmatch", "salt/job/*/ret/*"),
    ],
)
async def test_async_read_uses_existing_tag_matchers(session, match_type, tag):
    event, queue, _ = session
    queue.put_nowait(event.pack("unrelated", {"ignored": True}))
    queue.put_nowait(event.pack("salt/job/123/ret/minion", {"return": False}))
    assert await event.get_event_async(tag=tag, match_type=match_type) == {
        "return": False
    }


async def test_async_read_caches_subscribed_unwanted_events(session):
    event, queue, _ = session
    event.subscribe("wanted/")
    queue.put_nowait(event.pack("wanted/1", {"result": 1}))
    queue.put_nowait(event.pack("other/1", {"result": 2}))
    assert await event.get_event_async(tag="other/") == {"result": 2}
    assert await event.get_event_async(tag="wanted/", no_block=True, full=True) == {
        "tag": "wanted/1",
        "data": {"result": 1},
    }
    assert not event.pending_events


async def test_read_timeout_releases_reader_and_preserves_session(session):
    event, queue, state = session
    assert await event.get_event_async(wait=0.01) is None
    assert not event._event_read_tasks
    assert not state["closed"]
    queue.put_nowait(event.pack("next", {"result": True}))
    assert await event.get_event_async() == {"result": True}


async def test_waiting_reader_timeout_does_not_cancel_active_reader(session):
    event, queue, _ = session
    active = asyncio.create_task(event.get_event_async(wait=0, tag="first"))
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    assert await event.get_event_async(wait=0.01, tag="second") is None
    assert not active.done()
    queue.put_nowait(event.pack("first", {"result": 1}))
    assert await active == {"result": 1}


async def test_nonblocking_read_does_not_wait_for_active_reader(session):
    event, queue, _ = session
    active = asyncio.create_task(event.get_event_async(wait=0))
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    assert await asyncio.wait_for(event.get_event_async(no_block=True), 1) is None
    assert not active.done()
    queue.put_nowait(event.pack("next", {"result": True}))
    assert await active == {"result": True}


async def test_context_waits_for_queued_publication(session):
    event, _, state = session
    started, release = asyncio.Event(), asyncio.Event()

    async def publish():
        started.set()
        await release.wait()

    publication = asyncio.create_task(publish())
    event._publish_tasks.add(publication)

    async def context():
        async with event:
            pass

    closing = asyncio.create_task(context())
    await started.wait()
    await asyncio.sleep(0)
    assert not closing.done()
    assert not state["closed"]
    release.set()
    await closing
    assert publication.done()
    assert state["closed"]
    assert not asyncio.get_running_loop().is_closed()


async def test_exception_context_cancels_publication_without_masking_error(session):
    event, _, state = session
    started, cleaned = asyncio.Event(), asyncio.Event()

    async def publish():
        try:
            started.set()
            await asyncio.Event().wait()
        finally:
            cleaned.set()

    event._publish_tasks.add(asyncio.create_task(publish()))
    with pytest.raises(ValueError, match="caller failed"):
        async with event:
            await started.wait()
            raise ValueError("caller failed")
    assert cleaned.is_set()
    assert state["closed"]


async def test_external_destroy_finishes_reader_context_without_deadlock(session):
    event, _, state = session
    reading = asyncio.Event()

    async def reader():
        async with event:
            reading.set()
            await event.get_event_async(wait=0)

    task = asyncio.create_task(reader())
    await reading.wait()
    await asyncio.sleep(0)
    await asyncio.wait_for(event.destroy_async(), 1)
    with pytest.raises(asyncio.CancelledError):
        await task
    assert state["closed"]
    assert not event._event_read_tasks


async def test_async_read_skips_malformed_payload(session):
    event, queue, _ = session
    queue.put_nowait(b"tag\n\n\x81")
    queue.put_nowait(event.pack("valid", {"return": 0}))
    assert await event.get_event_async() == {"return": 0}


async def test_startup_error_closes_subscriber(session):
    event, _, state = session

    async def fail():
        raise OSError("connection failed")

    event._connect_task = asyncio.create_task(fail())
    with pytest.raises(OSError, match="connection failed"):
        async with event:
            pass
    assert state["closed"]
    assert event.subscriber is None


async def test_publication_error_still_releases_session(session):
    event, _, state = session

    async def fail():
        raise OSError("send failed")

    event._publish_tasks.add(asyncio.create_task(fail()))
    with pytest.raises(OSError, match="send failed"):
        async with event:
            pass
    assert state["closed"]


async def test_fork_reset_drops_tasks_without_touching_parent_resources(session):
    event, _, state = session
    task = SimpleNamespace(cancel=lambda: pytest.fail("inherited task was cancelled"))
    event._connect_task = task
    with patch.object(SaltEvent, "_instances", weakref.WeakSet([event])):
        SaltEvent._after_fork_in_child()
    assert event.subscriber is None
    assert event._connect_task is None
    assert not state["closed"]


@pytest.mark.parametrize("asynchronous", [False, True])
async def test_sync_and_async_fire_share_payload_preparation(session, asynchronous):
    event, _, _ = session
    messages = []

    async def publish(message):
        messages.append(message)

    event.pusher = SimpleNamespace(publish=publish, close=lambda: None)
    event.cpush = True
    event.opts["subproxy"] = True
    data = {"value": False}
    if asynchronous:
        await event.fire_event_async(data, "test/payload")
    else:
        assert event.fire_event(data, "test/payload") is True
    await event.destroy_async()
    tag, payload = event.unpack(messages[0])
    assert tag == "test/payload"
    assert payload["value"] is False
    assert payload["proxy_target"] == "master"
    assert "_stamp" in payload


@pytest.mark.parametrize("asynchronous", [False, True])
async def test_legacy_event_mode_preserves_payload_preparation(tmp_path, asynchronous):
    messages = []
    event = SaltEvent(
        "master",
        opts={"sock_dir": str(tmp_path), "master_async_mworker": False},
        listen=False,
    )
    event.pusher = SimpleNamespace(publish=messages.append, close=lambda: None)
    event.cpush = True
    try:
        if asynchronous:
            await event.fire_event_async({"value": 0}, "legacy/payload")
        else:
            assert event.fire_event({"value": 0}, "legacy/payload") is True
        tag, data = event.unpack(messages[0])
        assert tag == "legacy/payload"
        assert data["value"] == 0
        assert "_stamp" in data
    finally:
        event.destroy()
