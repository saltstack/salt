"""Scheduler callers await completion before continuing startup or reporting."""

import asyncio
from types import SimpleNamespace

import pytest

import salt.master
import salt.metaproxy.deltaproxy
import salt.minion
from tests.support.mock import AsyncMock, MagicMock


@pytest.mark.parametrize("entry", ["minion", "master"])
async def test_scheduler_entry_waits_for_evaluation_before_updating_interval(entry):
    started = asyncio.Event()
    release = asyncio.Event()
    schedule = SimpleNamespace(loop_interval=60, cleanup_subprocesses=MagicMock())

    async def evaluate():
        started.set()
        await release.wait()
        schedule.loop_interval = 1

    schedule.eval = evaluate
    owner = SimpleNamespace(schedule=schedule, loop_interval=60)
    call = (
        salt.minion.MinionBase.process_schedule(owner, 60)
        if entry == "minion"
        else salt.master.Maintenance.handle_schedule(owner)
    )
    task = asyncio.create_task(call)
    try:
        await started.wait()
        assert not task.done()
        schedule.cleanup_subprocesses.assert_not_called()
        release.set()
        result = await task
        assert (result if entry == "minion" else owner.loop_interval) == 1
        if entry == "master":
            schedule.cleanup_subprocesses.assert_called_once_with()
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def test_scheduler_before_connect_finishes_before_connection_and_tune_in():
    started = asyncio.Event()
    release = asyncio.Event()
    events = []

    async def setup(**kwargs):
        assert kwargs == {"before_connect": True}
        started.set()
        await release.wait()
        events.append("schedule")

    minion = SimpleNamespace(
        opts={"scheduler_before_connect": True, "acceptance_wait_time": 1},
        setup_scheduler=setup,
        connect_master=AsyncMock(side_effect=lambda **kwargs: events.append("connect")),
        tune_in=AsyncMock(side_effect=lambda: events.append("tune_in")),
    )
    manager = SimpleNamespace(minions=[])
    task = asyncio.create_task(
        salt.minion.MinionManager._connect_minion(manager, minion)
    )
    try:
        await started.wait()
        minion.connect_master.assert_not_awaited()
        minion.tune_in.assert_not_awaited()
        release.set()
        await task
        assert events == ["schedule", "connect", "tune_in"]
        assert manager.minions == [minion]
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def test_manage_schedule_awaits_run_job():
    started = asyncio.Event()
    release = asyncio.Event()

    async def run_job(name):
        assert name == "ping-master"
        started.set()
        await release.wait()

    minion = SimpleNamespace(schedule=SimpleNamespace(run_job=run_job))
    task = asyncio.create_task(
        salt.minion.Minion.manage_schedule(
            minion, "manage_schedule", {"func": "run_job", "name": "ping-master"}
        )
    )
    try:
        await started.wait()
        assert not task.done()
        release.set()
        await task
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


@pytest.mark.parametrize("parallel", [False, True])
async def test_subproxy_startup_keeps_scheduler_callbacks_on_managers_loop(
    monkeypatch, parallel
):
    owner = salt.minion.ProxyMinion.__new__(salt.minion.ProxyMinion)
    owner.opts = {"proxy": {"parallel_startup": parallel}}
    loops = []

    async def setup_scheduler():
        await asyncio.sleep(0)
        loops.append(asyncio.get_running_loop())

    proxies = [
        SimpleNamespace(
            setup_scheduler=setup_scheduler,
            setup_beacons=MagicMock(),
            add_periodic_callback=MagicMock(),
            cleanup_subprocesses=MagicMock(),
            _state_run=MagicMock(),
        )
        for _ in range(2)
    ]
    owner.deltaproxy_objs = dict(enumerate(proxies))
    parent_tune_in = AsyncMock()
    monkeypatch.setattr(salt.minion.Minion, "tune_in", parent_tune_in)

    await salt.metaproxy.deltaproxy.tune_in(owner)

    assert loops == [asyncio.get_running_loop()] * 2
    for proxy in proxies:
        proxy.add_periodic_callback.assert_called_once_with(
            "cleanup", proxy.cleanup_subprocesses
        )
        proxy._state_run.assert_called_once_with()
    parent_tune_in.assert_awaited_once_with()
