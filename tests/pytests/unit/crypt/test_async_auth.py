"""Concurrent authentication belongs to its awaiting request callers."""

import asyncio

import pytest

import salt.crypt
from tests.support.mock import AsyncMock, MagicMock


@pytest.fixture
def auth(io_loop):
    instance = object.__new__(salt.crypt.AsyncAuth)
    instance.io_loop = salt.utils.asynchronous.aioloop(io_loop)
    instance._authenticate_waiters = {}
    return instance


async def test_concurrent_callers_share_authentication(auth):
    started = asyncio.Event()
    release = asyncio.Event()

    async def authenticate():
        started.set()
        await release.wait()
        return True

    auth._authenticate = AsyncMock(side_effect=authenticate)
    first = asyncio.create_task(auth.authenticate())
    await started.wait()
    second = asyncio.create_task(auth.authenticate())
    await asyncio.sleep(0)
    assert not auth.authenticated
    release.set()
    assert await asyncio.gather(first, second) == [True, True]
    auth._authenticate.assert_awaited_once()
    assert auth.authenticated
    assert auth._authenticate_waiters == {}


async def test_cancel_one_waiter_keeps_peer_authentication(auth):
    started = asyncio.Event()
    release = asyncio.Event()

    async def authenticate():
        started.set()
        await release.wait()
        return True

    auth._authenticate = AsyncMock(side_effect=authenticate)
    first = asyncio.create_task(auth.authenticate())
    await started.wait()
    second = asyncio.create_task(auth.authenticate())
    await asyncio.sleep(0)
    first.cancel()
    with pytest.raises(asyncio.CancelledError):
        await first
    assert not auth._authenticate_future.cancelled()
    release.set()
    assert await second is True
    auth._authenticate.assert_awaited_once()


async def test_last_cancelled_waiter_drains_authentication(auth):
    started = asyncio.Event()
    cleaned = asyncio.Event()

    async def authenticate():
        try:
            started.set()
            await asyncio.Event().wait()
        finally:
            # Model the request channel's awaited __aexit__.
            await asyncio.sleep(0)
            cleaned.set()

    auth._authenticate = AsyncMock(side_effect=authenticate)
    waiter = asyncio.create_task(auth.authenticate())
    await started.wait()
    task = auth._authenticate_future
    waiter.cancel()
    with pytest.raises(asyncio.CancelledError):
        await waiter
    assert cleaned.is_set()
    assert task.cancelled()
    assert not auth.authenticated
    assert not hasattr(auth, "_authenticate_future")
    auth._authenticate = AsyncMock(return_value=True)
    assert await auth.authenticate() is True


async def test_unexpected_authentication_error_reaches_all_waiters(auth):
    started = asyncio.Event()
    release = asyncio.Event()

    async def authenticate():
        started.set()
        await release.wait()
        raise OSError("connection lost")

    auth._authenticate = AsyncMock(side_effect=authenticate)
    first = asyncio.create_task(auth.authenticate())
    await started.wait()
    second = asyncio.create_task(auth.authenticate())
    await asyncio.sleep(0)
    release.set()
    results = await asyncio.wait_for(
        asyncio.gather(first, second, return_exceptions=True), 1
    )
    assert all(isinstance(result, OSError) for result in results)
    assert not auth.authenticated
    auth._authenticate.assert_awaited_once()
    auth._authenticate = AsyncMock(return_value=True)
    assert await auth.authenticate() is True


async def test_callback_runs_after_authentication(auth):
    auth._authenticate = AsyncMock(return_value=True)
    callback = MagicMock()
    assert await auth.authenticate(callback=callback) is True
    await asyncio.sleep(0)
    callback.assert_called_once_with(True)


async def test_cancelled_authentication_is_not_authenticated(auth):
    auth._authenticate_future = asyncio.get_running_loop().create_future()
    auth._authenticate_future.cancel()
    assert not auth.authenticated


async def test_singleton_uses_underlying_asyncio_loop(minion_opts, io_loop):
    from tests.support.mock import patch

    with patch.object(salt.crypt.AsyncAuth, "get_keys"):
        explicit = salt.crypt.AsyncAuth(minion_opts, io_loop=io_loop)
        implicit = salt.crypt.AsyncAuth(minion_opts)
        assert explicit is implicit
        assert explicit.io_loop is asyncio.get_running_loop()


async def test_authentication_waits_for_credential_event(minion_opts):
    from tests.support.mock import patch

    loop = asyncio.get_running_loop()
    minion_opts["auth_events"] = True
    minion_opts["acceptance_wait_time"] = 0
    with patch.object(salt.crypt.AsyncAuth, "get_keys"):
        instance = salt.crypt.AsyncAuth(minion_opts, io_loop=loop)
    instance.sign_in = AsyncMock(
        return_value={
            "aes": salt.crypt.Crypticle.generate_key_string(),
            "session": salt.crypt.Crypticle.generate_key_string(),
        }
    )
    publishing = asyncio.Event()
    published = asyncio.Event()

    async def fire_event(data, tag):
        publishing.set()
        await published.wait()

    with patch("salt.channel.client.AsyncReqChannel.factory") as channel, patch(
        "salt.utils.event.get_event"
    ) as event:
        event.return_value.__enter__.return_value.fire_event_async = fire_event
        waiter = asyncio.create_task(instance.authenticate())
        await publishing.wait()
        assert not waiter.done()
        assert not instance.authenticated
        assert event.call_args.kwargs["io_loop"] is loop
        published.set()
        assert await waiter is True
        channel.return_value.__aexit__.assert_awaited_once()
        assert instance.authenticated


async def test_cancel_new_attempt_while_old_waiter_is_resuming(auth):
    from tests.support.mock import patch

    old_complete = asyncio.Event()
    release_old = asyncio.Event()
    new_started = asyncio.Event()
    new_cleaned = asyncio.Event()
    shield = asyncio.shield

    async def hold_completed_attempt(future):
        result = await shield(future)
        old_complete.set()
        await release_old.wait()
        return result

    async def new_attempt():
        try:
            new_started.set()
            await asyncio.Event().wait()
        finally:
            new_cleaned.set()

    auth._authenticate = AsyncMock(return_value=True)
    with patch("asyncio.shield", hold_completed_attempt):
        old_waiter = asyncio.create_task(auth.authenticate())
        await old_complete.wait()
        auth._authenticate = AsyncMock(side_effect=new_attempt)
        new_waiter = asyncio.create_task(auth.authenticate())
        await new_started.wait()
        new_waiter.cancel()
        with pytest.raises(asyncio.CancelledError):
            await new_waiter
        assert new_cleaned.is_set()
        release_old.set()
        assert await old_waiter is True
    assert auth._authenticate_waiters == {}
