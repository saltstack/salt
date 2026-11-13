"""Owned request workers must survive successive SyncWrapper calls."""

import asyncio

import pytest

from salt.utils.asynchronous import SyncWrapper

pytestmark = [pytest.mark.core_test]


class QueueWorker:
    async_methods = ["send"]

    def __init__(self, mode):
        self.queue = asyncio.Queue()
        self.worker = None
        self.mode = mode
        self.stopped = False

    async def next_request(self):
        if self.mode == "wait_for":
            return await asyncio.wait_for(self.queue.get(), timeout=0.3)
        if self.mode == "gather":
            return (await asyncio.gather(self.queue.get()))[0]
        if self.mode == "shield":
            return await asyncio.shield(self.queue.get())
        return await self.queue.get()

    async def consume(self):
        try:
            while True:
                try:
                    reply, value = await self.next_request()
                except asyncio.TimeoutError:
                    continue
                reply.set_result(value)
        finally:
            self.stopped = True

    async def send(self, value):
        if self.worker is None:
            self.worker = asyncio.create_task(self.consume())
        reply = asyncio.get_running_loop().create_future()
        self.queue.put_nowait((reply, value))
        return await asyncio.wait_for(reply, timeout=1)


@pytest.mark.parametrize("mode", ["wait_for", "gather", "shield", "direct"])
@pytest.mark.parametrize("custom_factory", [False, True])
@pytest.mark.parametrize("materialize_dict", [False, True])
async def test_owned_worker_survives_dispatch(mode, custom_factory, materialize_dict):
    wrapper = SyncWrapper(QueueWorker, args=(mode,))
    if materialize_dict:
        vars(wrapper.obj)
    calls = []

    def task_factory(loop, coro, **kwargs):
        calls.append(coro)
        return asyncio.Task(coro, loop=loop, **kwargs)

    factory = task_factory if custom_factory else None
    wrapper.asyncio_loop.set_task_factory(factory)
    try:
        assert wrapper.send("first") == "first"
        assert not wrapper.obj.worker.done()
        assert wrapper.send("second") == "second"
        assert wrapper.asyncio_loop.get_task_factory() is factory
        if custom_factory:
            assert calls
        worker = wrapper.obj
    finally:
        wrapper.close()
    assert worker.worker.done()
    assert worker.stopped is True


class OrphanWorker:
    async_methods = ["start"]

    async def start(self):
        async def consume():
            await asyncio.wait_for(asyncio.Queue().get(), timeout=60)

        asyncio.create_task(consume())
        await asyncio.sleep(0)
        return True


async def test_unowned_worker_is_still_reaped():
    wrapper = SyncWrapper(OrphanWorker)
    try:
        assert wrapper.start() is True
        assert not asyncio.all_tasks(wrapper.asyncio_loop)
    finally:
        wrapper.close()


async def test_task_factory_restored_after_dispatch_error():
    class FailingCall:
        async_methods = ["fail"]

        async def fail(self):
            asyncio.create_task(asyncio.sleep(60))
            raise ValueError("wrapped call failed")

    def task_factory(loop, coro, **kwargs):
        return asyncio.Task(coro, loop=loop, **kwargs)

    wrapper = SyncWrapper(FailingCall)
    wrapper.asyncio_loop.set_task_factory(task_factory)
    try:
        with pytest.raises(ValueError, match="wrapped call failed"):
            wrapper.fail()
        assert wrapper.asyncio_loop.get_task_factory() is task_factory
        assert not asyncio.all_tasks(wrapper.asyncio_loop)
    finally:
        wrapper.close()
